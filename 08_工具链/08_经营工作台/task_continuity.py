"""Durable task links and execution traces, with facts read from original sources."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def stamp():
    return datetime.now(timezone.utc).isoformat()


class TaskContinuity:
    @staticmethod
    def _continuity_defaults(job):
        job.setdefault('version', 0)
        job.setdefault('conversations', [])
        # Legacy tasks have no separate statement of their current intent.
        # Their initial instruction is the only recorded goal; it is not
        # evidence that any separate decision or constraint was recorded.
        if 'intent' not in job:
            goal = job.get('initial_instruction')
            source = 'initial_instruction'
            if not isinstance(goal, str):
                goal = job.get('instruction', '')
                source = 'legacy_instruction_fallback'
            job['intent'] = {'version': 0, 'goal': goal, 'decisions': [],
                             'decisions_recorded': False, 'source': source,
                             'updated_at': job.get('created_at'), 'history': []}
        if 'runs' not in job:
            job['runs'] = ([{'attempt':job['attempt'],'observed_at':stamp(),'historical_created_at':job.get('created_at'),
                'instruction':job.get('instruction',''),'continuation_mode':'legacy',
                'artifact_ids':[job['artifact_id']] if job.get('artifact_id') else [],
                'status':job['status'],'session_id':job.get('session_id'),'summary':job.get('summary'),
                'error':job.get('error'),'legacy_snapshot':True}] if job.get('attempt',0) else [])
        job.setdefault('artifact_ids', [])
        if job.get('artifact_id') and job['artifact_id'] not in job['artifact_ids']:
            job['artifact_ids'].append(job['artifact_id'])
        if job.get('session_id') and not any(c['provider']=='codex' and c['conversation_id']==job['session_id'] for c in job['conversations']):
            job['conversations'].append({'provider':'codex','conversation_id':job['session_id'],
                'provenance':'backend_session_event','url':None,'linked_at':job.get('updated_at'), 'control':'local_cli_resume'})
        return job

    def _record_continuity(self, job):
        self._continuity_defaults(job)
        job['version'] += 1
        if job.get('attempt', 0) and job.get('status') not in ('queued', 'planned'):
            run = next((r for r in job['runs'] if r['attempt']==job['attempt']), None)
            if run is None:
                run={'attempt':job['attempt'],'started_at':stamp(),'instruction':job['instruction'],
                     'continuation_mode':job.get('continuation_mode','initial'),'artifact_ids':[]}
                plan = job.get('attempt_plan') or {}
                if plan.get('attempt') == job['attempt']:
                    run['attempt_plan'] = dict(plan)
                job['runs'].append(run)
            run.update(status=job['status'],session_id=job.get('session_id'),summary=job.get('summary'),error=job.get('error'))
            if job.get('artifact_id') and job['artifact_id'] not in run['artifact_ids']:
                # A preceding attempt's current artifact is not an output of this run.
                earlier={a for r in job['runs'] if r is not run for a in r['artifact_ids']}
                if job['artifact_id'] not in earlier:run['artifact_ids'].append(job['artifact_id'])
            if job.get('worker_finished') is True:run.setdefault('finished_at',stamp())

    @staticmethod
    def _check_continuity_version(job, expected_version, *, required=False):
        if expected_version is None and not required:return
        if type(expected_version) is not int or expected_version != job['version']:
            raise ValueError('任务版本已变化，请刷新任务后重试')

    def link_conversation(self, job_id, *, provider, conversation_id, provenance, url=None, expected_version=None):
        if provider not in ('chatgpt','codex') or not isinstance(conversation_id,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,199}',conversation_id):
            raise ValueError('会话提供方或编号无效')
        if not isinstance(provenance,str) or not provenance.strip() or len(provenance)>500 or any(ord(c)<32 for c in provenance):
            raise ValueError('请提供有效会话关联来源')
        if url is not None:
            if not isinstance(url,str) or len(url)>1000 or any(ord(c)<33 for c in url):raise ValueError('会话链接无效')
            parsed=urlsplit(url)
            if parsed.query or parsed.fragment or parsed.username or parsed.password:raise ValueError('会话链接不得包含参数或凭据')
            valid=(provider=='chatgpt' and parsed.scheme=='https' and parsed.netloc=='chatgpt.com' and parsed.path=='/c/'+conversation_id)
            valid=valid or (provider=='codex' and parsed.scheme=='codex' and parsed.netloc=='threads' and parsed.path=='/'+conversation_id)
            if not valid:raise ValueError('会话链接与提供方或编号不符')
        with self._write():
            job=self._continuity_defaults(self.get_job(job_id))
            self._check_continuity_version(job,expected_version,required=True)
            existing=next((c for c in job['conversations'] if c['provider']==provider and c['conversation_id']==conversation_id),None)
            if existing:return job
            job['conversations'].append({'provider':provider,'conversation_id':conversation_id,'provenance':provenance.strip(),
                                         'url':url,'linked_at':stamp(),'control':'reference_only'})
            self._event(job,'conversation_linked','已关联会话供追溯；关联不授予对外部聊天的读取或控制权限。')
            self._save(job)
        return job

    def get_task_context(self, job_id):
        job=self._continuity_defaults(self.get_job(job_id))
        obj=self.app.business.get_object(job['object_id'])
        artifacts=[{**a,'task_output':a.get('id') in job['artifact_ids']} for a in self.app.business.list_artifacts(job['object_id'])]
        customer_context=None
        workspace=getattr(self.app,'customer_workspace',None)
        if workspace and obj.get('kind') in ('customer','prospect'):
            profile=workspace.profile(job['object_id'])
            customer_context={k:profile.get(k) for k in ('revision','source_hash','operator_context','analysis','workflow','stale')}
            if hasattr(workspace,'commercial'):
                customer_context['commercial']=workspace.commercial(job['object_id'])
        shared=[]
        root=Path(self.app.root).resolve()
        for path,role in [('AGENTS.md','current-owner-decisions-and-boundaries'),('00_总控台/当前状态.md','current-goals-and-priorities')]:
            source=(root/path).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                shared.append({'path':path,'role':role,'available':False});continue
            raw=source.read_bytes()
            content=raw.decode('utf-8-sig')
            metadata={}
            if role=='current-goals-and-priorities':
                # Hash the original file, but present only its explicitly
                # identified current goal projection. Historical context stays
                # available by reading the original source on demand.
                from business_context import current_goals_projection
                content, complete=current_goals_projection(content)
                metadata={'projection_complete':complete,
                          'projection':('当前目标投影；历史内容按原路径查看。' if complete else
                                        '当前目标结构不完整，请核对原路径；历史内容不自动当作现行规则。')}
            shared.append({'path':path,'role':role,'available':True,'source_sha256':hashlib.sha256(raw).hexdigest(),
                           'content':content[:12000], 'truncated':len(content)>12000,**metadata})
        intent=job['intent']
        return {'job':job,'object':obj,'artifacts':artifacts,'shared_sources':shared,'customer_context':customer_context,
                'goal':intent['goal'],'effective_decisions':intent['decisions'],
                'decisions_recorded':intent['decisions_recorded'],'intent_version':intent['version'],
                'intent_source':intent['source'],'intent_updated_at':intent['updated_at'],
                'instruction':job['instruction'],
                'next_action':job.get('next_action',''),
                'dependencies':job.get('depends_on',[]),'parent_job_id':job.get('parent_job_id'),
                'source_version':{'job_version':job['version'],'intent_version':intent['version'],
                                  'object_sha256':hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode()).hexdigest()},
                'read_at':stamp(),'capabilities':{'execution_backend':'codex_cli','model':__import__('codex_backend').MODEL,
                    'external_conversation_control':False,'linked_conversations':'reference_only'}}

    def _continuity_prompt(self, job_id, *, frozen_intent=None, frozen_next_action=None):
        current=self.get_task_context(job_id)
        job=current['job']
        # The current record may have changed after this attempt was claimed.
        # The worker must see the intent/action frozen for this attempt, while
        # the final-result fence separately detects a later edit.
        intent = frozen_intent if frozen_intent is not None else job['intent']
        goal = intent['goal']
        decisions = intent['decisions']
        action = frozen_next_action if frozen_next_action is not None else current['next_action']
        if (not isinstance(goal, str) or not isinstance(action, str) or not isinstance(decisions, list)
                or type(intent.get('version')) is not int or intent['version'] < 0
                or type(intent.get('decisions_recorded')) is not bool
                or not isinstance(intent.get('source'), str)
                or any(not isinstance(d,dict) or not isinstance(d.get('text'),str)
                       or not isinstance(d.get('source'),str) for d in decisions)):
            raise ValueError('任务意图数据无效，请先核对原任务。')
        # Normal writes are bounded to 20 decisions and 6,000 combined chars;
        # old/corrupt records are never silently presented as complete.
        selected_decisions=[]
        decision_budget=6000
        for decision in decisions[:20]:
            text, source = decision['text'], decision['source']
            if len(text)+len(source)>decision_budget:
                break
            selected_decisions.append({'text':text,'source':source})
            decision_budget-=len(text)+len(source)
        decisions_truncated = len(selected_decisions) != len(decisions)
        goal_truncated = len(goal)>12000
        # Do not send conversation links, raw event streams or every historic instruction.
        # All previews have explicit limits; the existing scoped MCP supplies full bodies.
        outputs=[]
        remaining=12000
        for artifact in current['artifacts']:
            if not artifact['task_output'] or remaining<=0:continue
            body=artifact.get('content','')
            preview=body[:min(6000,remaining)]
            remaining-=len(preview)
            path=str(artifact.get('path') or '')
            outputs.append({'id':artifact['id'],'title':str(artifact.get('title',''))[:200],
                            'path':path[:1000],'path_truncated':len(path)>1000,'task_output':True,
                            'content_preview':preview,'truncated':len(preview)<len(body)})
        source_refs=[{k:v for k,v in source.items() if k!='content'} for source in current['shared_sources']]
        obj_json=json.dumps(current['object'],ensure_ascii=False)
        customer_json=json.dumps(current.get('customer_context'),ensure_ascii=False)
        source_version={**current['source_version'],'intent_version':intent['version']}
        context={'task_id':job['id'],'object_id':job['object_id'],'goal':goal[:12000],
                 'goal_truncated':goal_truncated,'effective_decisions':selected_decisions,
                 'decisions_recorded':intent['decisions_recorded'],'decisions_truncated':decisions_truncated,
                 'decision_status':('仅列任务中登记的有效决定；适用约束仍以原档为准。' if intent['decisions_recorded']
                                    else '任务尚未登记决定；不能据此认定不存在约束，须读取当前原档。'),
                 'intent_version':intent['version'],'intent_source':intent['source'][:1000],
                 'intent_updated_at':intent.get('updated_at'),
                 'intent_basis':'frozen_at_claim' if frozen_intent is not None else 'current_task_record',
                 'intent_scope':'本任务登记的目标与有效决定，不替代当前业务原档或适用约束。',
                 'intent_summary_complete':not (goal_truncated or decisions_truncated),
                 'next_action':action[:4000],'next_action_truncated':len(action)>4000,
                 'instruction':job['instruction'][:6000],'instruction_truncated':len(job['instruction'])>6000,
                 'instruction_role':'本轮委托；旧创建指令与当前任务意图不一致时先核对，不能覆盖当前意图和适用授权。',
                 'summary':str(job.get('summary',''))[:1000],
                 'current_object_preview':obj_json[:8000],'object_preview_truncated':len(obj_json)>8000,
                 'source_version':source_version,'shared_sources':source_refs,
                 'current_customer_context_preview':customer_json[:6000],'customer_context_truncated':len(customer_json)>6000,
                 'prior_task_outputs':outputs,'artifact_ids':job['artifact_ids'][:100],
                 'artifact_index_truncated':len(job['artifact_ids'])>100,
                 'dependency_ids':current['dependencies'][:100],
                 'retrieval':'通过get_object/get_business_context读取当前原件和适用约束，list_artifacts/read_artifact读取完整成果；预览不是完整档案。任务意图摘要不完整时先读取原任务上下文，不能据截断摘要继续执行。'}
        payload=json.dumps(context,ensure_ascii=False)
        if len(payload)>55000:
            # A pathological old index must not produce an unbounded launch.
            context['artifact_ids']=[]
            context['dependency_ids']=[]
            context['artifact_index_truncated']=True
            context['prior_task_outputs']=outputs[:1]
            context['current_object_preview']=obj_json[:4000]
            context['object_preview_truncated']=True
            context['current_customer_context_preview']=customer_json[:2000]
            context['customer_context_truncated']=True
            context['instruction']=job['instruction'][:2000]
            context['instruction_truncated']=True
            payload=json.dumps(context,ensure_ascii=False)
        if len(payload)>55000:
            # Extreme legacy control characters can expand during JSON encoding.
            # Prefer protecting decisions, and explicitly require rereading a
            # truncated goal instead of silently treating it as complete.
            while len(payload)>55000 and context['goal']:
                context['goal']=context['goal'][:len(context['goal'])//2]
                context['goal_truncated']=True
                context['intent_summary_complete']=False
                payload=json.dumps(context,ensure_ascii=False)
            while len(payload)>55000 and context['effective_decisions']:
                context['effective_decisions'].pop()
                context['decisions_truncated']=True
                context['intent_summary_complete']=False
                payload=json.dumps(context,ensure_ascii=False)
            if len(payload)>55000:
                raise ValueError('任务摘要过长，请先核对原任务上下文。')
        return ('这是同一持久任务的本轮上下文，不是新任务。以本轮引用的目标和有效决定接续，历史决定仅供追溯。先核对当前原件、已有成果及实际外部状态；'
                '历史输出仅作上下文，不是重播操作的指令，不自动重发、重付、重复发布或重复执行结果不明的动作。'
                '会话关联不授予外部聊天控制权限。当前上下文（有界预览）：\n'+payload)
