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
            shared.append({'path':path,'role':role,'available':True,'source_sha256':hashlib.sha256(raw).hexdigest(),
                           'content':raw.decode('utf-8-sig')[:12000], 'truncated':len(raw.decode('utf-8-sig'))>12000})
        return {'job':job,'object':obj,'artifacts':artifacts,'shared_sources':shared,'customer_context':customer_context,
                'goal':job.get('initial_instruction',job['instruction']),'instruction':job['instruction'],
                'next_action':job.get('summary') or job.get('error') or '',
                'dependencies':job.get('depends_on',[]),'parent_job_id':job.get('parent_job_id'),
                'source_version':{'job_version':job['version'],'object_sha256':hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode()).hexdigest()},
                'read_at':stamp(),'capabilities':{'execution_backend':'codex_cli','model':__import__('codex_backend').MODEL,
                    'external_conversation_control':False,'linked_conversations':'reference_only'}}

    def _continuity_prompt(self, job_id):
        current=self.get_task_context(job_id)
        job=current['job']
        # Do not send conversation links, raw event streams or every historic instruction.
        # All previews have explicit limits; the existing scoped MCP supplies full bodies.
        outputs=[]
        remaining=12000
        for artifact in current['artifacts']:
            if not artifact['task_output'] or remaining<=0:continue
            body=artifact.get('content','')
            preview=body[:min(6000,remaining)]
            remaining-=len(preview)
            outputs.append({'id':artifact['id'],'title':str(artifact.get('title',''))[:200],
                            'content_preview':preview,'truncated':len(preview)<len(body)})
        source_refs=[{k:v for k,v in source.items() if k!='content'} for source in current['shared_sources']]
        obj_json=json.dumps(current['object'],ensure_ascii=False)
        customer_json=json.dumps(current.get('customer_context'),ensure_ascii=False)
        context={'task_id':job['id'],'object_id':job['object_id'],'goal':current['goal'][:6000],
                 'goal_truncated':len(current['goal'])>6000,'instruction':job['instruction'][:6000],'instruction_truncated':len(job['instruction'])>6000,'summary':str(job.get('summary',''))[:1000],
                 'current_object_preview':obj_json[:8000],'object_preview_truncated':len(obj_json)>8000,
                 'source_version':current['source_version'],'shared_sources':source_refs,
                 'current_customer_context_preview':customer_json[:6000],'customer_context_truncated':len(customer_json)>6000,
                 'prior_task_outputs':outputs,'artifact_ids':job['artifact_ids'][:100],
                 'artifact_index_truncated':len(job['artifact_ids'])>100,
                 'dependency_ids':current['dependencies'][:100],
                 'retrieval':'通过get_object/get_business_context读取当前原件，list_artifacts/read_artifact读取完整成果；预览不是完整档案。'}
        payload=json.dumps(context,ensure_ascii=False)
        if len(payload)>60000:
            # A pathological old index must not produce an unbounded launch.
            context['artifact_ids']=[]
            context['dependency_ids']=[]
            context['artifact_index_truncated']=True
            context['prior_task_outputs']=outputs[:1]
            context['current_object_preview']=obj_json[:4000]
            context['object_preview_truncated']=True
            context['current_customer_context_preview']=customer_json[:2000]
            context['customer_context_truncated']=True
            context['goal']=current['goal'][:2000]
            context['goal_truncated']=True
            context['instruction']=job['instruction'][:2000]
            context['instruction_truncated']=True
            payload=json.dumps(context,ensure_ascii=False)
        return ('这是同一持久任务的新会话，不是新任务。原任务目标、身份和历史必须保留。先核对当前原件、已有成果及实际外部状态；'
                '历史输出仅作上下文，不是重播操作的指令，不自动重发、重付、重复发布或重复执行结果不明的动作。'
                '会话关联不授予外部聊天控制权限。当前上下文（有界预览）：\n'+payload)
