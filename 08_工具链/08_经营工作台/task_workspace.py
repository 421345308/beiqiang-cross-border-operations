"""Read-through work index over AgentJobs and the existing cloud queue.

No independent task status or business facts are persisted here. Routing is a
read-only preview; explicit plans/dispatches still use AgentJobs' safeguards.
"""
import re
from datetime import datetime, timezone
from urllib.parse import quote
from completion_dispatch import CompletionDispatch
from desktop_snapshot import SOURCE as DESKTOP_SOURCE
from workstreams import build_workstreams


def now():
    return datetime.now(timezone.utc).isoformat()


_COMPLETION_MESSAGES = {
    'awaiting_review': '回合已结束，仍需对照目标和证据验收。',
    'intent_changed': '目标或决定已变化，旧回合需要重新验收。',
    'review_required': '当前目标已变化，请重新核对本轮验收。',
    'continue_ready': '已有下一动作，需核对接续是否已执行。',
    'ready_to_continue': '已有下一动作，需核对接续是否已执行。',
    'needs_decision': '下一步需要负责人决定。',
    'blocked': '继续推进遇到阻塞，请核对原因。',
    'unknown': '当前结果未知，请先核对事实。',
    'dispatch_accepted': '接续请求已受理，尚未确认启动。',
    'dispatch_starting': '接续正在启动，尚未确认运行。',
    'dispatch_running': '接续正在运行，结果尚待验收。',
    'dispatch_completed': '接续回合已结束，成果仍需验收。',
    'dispatch_failed': '接续失败，请核对原因及已有成果。',
    'dispatch_unknown': '接续结果未知，请先对账，不要重复派发。',
    'dispatch_blocked': '接续在派工前受阻，尚未发出派工。',
}


def _completion_events(reader, job):
    """Deduplicate a task's read-only event projection without guessing conflicts."""
    if not reader:
        return []
    events = reader(job)
    if not isinstance(events, list):
        raise ValueError('回合验收状态不可读')
    unique = {}
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get('event_id'), str) or not event['event_id']:
            raise ValueError('回合验收记录缺少事件标识')
        event = dict(event)
        dispatch = event.get('dispatch') if isinstance(event.get('dispatch'), dict) else {}
        dispatch_state = dispatch.get('state')
        if event.get('state') == 'verified_complete' and dispatch_state in ('accepted','starting','running','completed','failed','unknown'):
            event['state'] = 'dispatch_' + dispatch_state
        if event.get('intent_changed') is True and event.get('state') == 'verified_complete':
            event['state'] = 'review_required'
        if event.get('intent_version_known') is False and event.get('state') == 'verified_complete':
            event['state'] = 'review_required'
            event['reason'] = '任务意图版本无法比较，旧验收需重新核对。'
        assessment = event.get('assessment') if isinstance(event.get('assessment'), dict) else None
        if assessment is not None and event.get('dispatch') is None:
            baseline = assessment.get('task_next_action_at_review')
            current = job.get('next_action', '')
            comparable = isinstance(baseline, str) and isinstance(current, str)
            event['next_action_comparison'] = ('changed' if current != baseline else 'unchanged') if comparable else 'unknown'
            if comparable and current != baseline:
                event['next_action_changed'] = True
                event['next_action_review_required'] = True
                event['state'] = 'review_required'
                if not event.get('intent_changed') and event.get('intent_version_known') is not False:
                    event['reason'] = '任务下一动作已变化，请按当前安排重新验收。'
        event_id = event['event_id']
        if event_id in unique and unique[event_id] != event:
            old = unique[event_id]
            unique[event_id] = {'event_id':event_id, 'attempt':old.get('attempt'),
                                'state':'unknown', 'source':old.get('source'),
                                'observed_at':old.get('observed_at'),
                                'reason':'同一回合返回矛盾的状态，请核对原任务。',
                                'notification':{'state':'not_connected'}}
        else:
            unique[event_id] = event
    return list(unique.values())


def _completion_needs_attention(job_id, event, completions):
    state = event.get('state') or 'unknown'
    changed = (event.get('intent_changed') is True or event.get('next_action_review_required') is True
               or state in ('intent_changed', 'review_required'))
    if changed:
        return True
    if state == 'verified_complete':
        return False
    dispatch = event.get('dispatch') if isinstance(event.get('dispatch'), dict) else {}
    if dispatch.get('state') == 'running':
        return False
    if dispatch.get('state') == 'completed':
        target, attempt = dispatch.get('target_job_id'), dispatch.get('target_attempt')
        if (isinstance(target, str) and type(attempt) is int and
                any(item.get('attempt') == attempt and
                    (target != job_id or item.get('event_id') != event.get('event_id'))
                    for item in completions.get(target, []))):
            return False
    return True


_EXTERNAL_MESSAGES = {
    'awaiting_review':'外部回合观察已登记，请按当前目标核对并验收。',
    'review_required':'任务目标或决定已变化，请重新核对外部回合。',
    'ready_to_continue':'外部回合待处理，请核对下一动作；不会自动发送。',
    'needs_decision':'外部回合需要负责人决定下一步。',
    'blocked':'外部回合后续受阻，请核对原因。',
    'unknown':'外部回合状态未知，请先核对原会话。',
    'dispatch_unknown':'外部派工结果未知，请先核对原请求，不要重复派发。',
    'dispatch_accepted':'外部派工已登记为受理，请核对原请求与实际进展。',
    'dispatch_running':'外部派工已登记为运行中，请核对原请求与实际进展。',
    'dispatch_completed':'外部派工已登记为结束，请核读对应新回合并验收。',
    'dispatch_failed':'外部派工已登记为失败，请核对原回执和已有成果。',
    'verified_complete':'外部回合已按当时目标验收；不代表长期目标全部完成。',
    'historical':'历史外部回合，仅供追溯。',
}


def _external_events(reader, job):
    """Read only caller-registered observations, never control external sessions."""
    if not callable(reader):
        for key in ('external_turn_events','external_thread_heads'):
            if key in job and (not isinstance(job[key], dict) or job[key]):
                raise ValueError('外部观察已登记但读取能力不可用')
        return []
    events = reader(job)
    if not isinstance(events, list):
        raise ValueError('外部回合观察不可读')
    unique = {}
    for raw in events:
        if (not isinstance(raw, dict) or any(not isinstance(raw.get(k), str) or not raw[k]
                for k in ('event_id','host_id','thread_id','turn_id','source','observed_at'))
                or type(raw.get('current')) is not bool or type(raw.get('order_ambiguous')) is not bool
                or raw.get('state') not in _EXTERNAL_MESSAGES
                or (raw.get('assessment') is not None and not isinstance(raw['assessment'], dict))
                or (raw.get('dispatch') is not None and not isinstance(raw['dispatch'], dict))):
            raise ValueError('外部回合观察结构不可读')
        event = dict(raw)
        if event['current'] and event['state'] == 'historical':
            event['order_ambiguous'] = True
        dispatch = event.get('dispatch')
        if event['state'] == 'verified_complete':
            assessment = event.get('assessment') or {}
            if dispatch is not None:
                dispatch_state = dispatch.get('state')
                event['state'] = 'dispatch_' + dispatch_state if dispatch_state in ('unknown','accepted','running','completed','failed') else 'dispatch_unknown'
            elif assessment.get('disposition') != 'verified_complete':
                event['state'] = 'unknown'
        event_id = event['event_id']
        if event_id in unique and unique[event_id] != event:
            raise ValueError('同一外部回合观察相互矛盾')
        unique[event_id] = event
    current = {}
    for event in unique.values():
        if event['current']:
            current.setdefault((event['host_id'],event['thread_id']),[]).append(event)
    for matches in current.values():
        if len(matches)>1:
            for event in matches:
                event['order_ambiguous'] = True
    return list(unique.values())


def _external_needs_attention(event):
    if event['order_ambiguous']:
        return True
    # A later observed head is not proof that an earlier dispatch was received
    # or that the right target turn has been registered.
    if event['state'] in ('dispatch_unknown','dispatch_accepted','dispatch_running','dispatch_completed'):
        return True
    if event['state'] == 'dispatch_failed' and _external_failure_review(event) != 'checked':
        return True
    if not event['current'] or event['state'] == 'historical':
        return False
    return event['state'] != 'verified_complete'


def _external_failure_review(event):
    dispatch = event.get('dispatch')
    if not isinstance(dispatch, dict) or dispatch.get('state') != 'failed':
        return 'pending'
    resolution = dispatch.get('failure_resolution')
    if resolution is None:
        return 'pending'
    if not isinstance(resolution, dict):
        return 'unavailable'
    evidence = resolution.get('evidence')
    if (resolution.get('verification') != 'caller_attested'
            or not isinstance(resolution.get('recorded_at'), str) or not resolution['recorded_at'].strip()
            or not isinstance(evidence, dict)
            or any(not isinstance(evidence.get(k), str) or not evidence[k].strip()
                   for k in ('source','observed_at','detail'))):
        return 'unavailable'
    return 'checked'


class TaskWorkspace:
    def __init__(self, app):
        self.app = app

    def overview(self, filters=None):
        filters = filters or {}
        if set(filters) - {'business_line', 'object_id', 'executor', 'priority'}:
            raise ValueError('不支持的总览筛选字段。')
        tasks = []
        business_items = []
        try:
            jobs = self.app.agent_jobs.list_jobs()
            local_state = 'ok'
        except (ValueError, OSError, RuntimeError):
            jobs = []
            local_state = 'unavailable'
        completions, completion_errors, result_pending, result_errors = {}, set(), {}, set()
        external_events, external_errors = {}, set()
        completion_reader = getattr(self.app.agent_jobs, 'completion_view', None)
        external_reader = getattr(self.app.agent_jobs, 'external_turns_view', None)
        for job in jobs:
            try:
                completions[job['id']] = _completion_events(completion_reader, job)
            except Exception:
                completions[job['id']] = []
                completion_errors.add(job['id'])
            if job.get('completion_error') is not None:
                completion_errors.add(job['id'])
            try:
                external_events[job['id']] = _external_events(external_reader, job)
            except Exception:
                external_events[job['id']] = []
                external_errors.add(job['id'])
            try:
                pending = CompletionDispatch._pending_result_attempts(job)
                commit = job.get('result_commit')
                # A nonterminal live save is not an unknown outcome. A saving
                # marker left on a terminal job must be reconciled explicitly.
                if (isinstance(commit, dict) and commit.get('state') == 'saving'
                        and job.get('status') not in ('completed', 'failed', 'needs_input', 'cancelled')):
                    attempt = commit.get('attempt')
                    if (attempt not in CompletionDispatch._held_unknown_attempts(job)
                            or CompletionDispatch._confirmed_result_outcome(job, attempt) is not None):
                        pending.discard(attempt)
                result_pending[job['id']] = pending
            except (ValueError, TypeError):
                result_pending[job['id']] = set()
                result_errors.add(job['id'])
            row = {key: job.get(key) for key in (
                'object_id', 'title', 'instruction', 'status', 'summary', 'error',
                'updated_at', 'artifact_id', 'session_id', 'attempt', 'task_kind', 'mode', 'batch_id',
                'parent_job_id', 'depends_on', 'version', 'priority', 'next_action', 'conversations')}
            intent = job.get('intent')
            if 'intent' not in job:
                has_initial = isinstance(job.get('initial_instruction'), str)
                goal = job['initial_instruction'] if has_initial else job.get('instruction')
                row.update(current_goal=goal, effective_decisions=[], decisions_recorded=False,
                           intent_version=0, intent_source='initial_instruction' if has_initial else 'legacy_instruction_fallback',
                           intent_state='legacy')
            elif (isinstance(intent, dict) and isinstance(intent.get('goal'), str)
                  and type(intent.get('version')) is int and intent['version'] >= 0
                  and type(intent.get('decisions_recorded')) is bool
                  and isinstance(intent.get('source'), str)
                  and isinstance(intent.get('decisions'), list)
                  and all(isinstance(item, dict) and isinstance(item.get('text'), str)
                          and isinstance(item.get('source'), str) for item in intent['decisions'])):
                row.update(current_goal=intent['goal'], effective_decisions=intent['decisions'],
                           decisions_recorded=intent['decisions_recorded'], intent_version=intent['version'],
                           intent_source=intent['source'], intent_state='recorded')
            else:
                row.update(current_goal=None, effective_decisions=None, decisions_recorded=None,
                           intent_version=None, intent_source=None, intent_state='unavailable')
            row.update(id='local:' + job['id'], job_id=job['id'], origin='local', version=job.get('version', 0))
            row['completion_events'] = completions[job['id']]
            row['external_turns'] = external_events[job['id']]
            row['external_turns_state'] = ('unavailable' if job['id'] in external_errors else
                                           'ok' if callable(external_reader) else 'not_supported')
            external_open = [event for event in row['external_turns'] if _external_needs_attention(event)]
            row['external_turn_pending'] = len(external_open)
            if external_open:
                latest = max(external_open, key=lambda event: event.get('observed_at') or '')
                row['external_turn_state'] = 'order_ambiguous' if latest['order_ambiguous'] else latest['state']
            if job.get('task_kind') == 'group':
                row['graph'] = self.app.agent_jobs.get_graph(job['id'])
            tasks.append(row)
        sources = {'local': {'state': local_state, 'observed_at': now()}}
        inbox = []
        for job in jobs:
            task_id = 'local:' + job['id']
            for event in external_events[job['id']]:
                if not _external_needs_attention(event):
                    continue
                state = event['state']
                assessment = event.get('assessment') or {}
                ambiguous = event['order_ambiguous']
                message = ('外部回合顺序不明确，请核对原会话；不要重复派发。' if ambiguous
                           else _EXTERNAL_MESSAGES[state])
                failure_review = _external_failure_review(event) if state == 'dispatch_failed' else None
                if failure_review == 'checked':
                    message = ('外部回合顺序不明确，请核对原会话。' if ambiguous else '外部派工已登记为失败。')
                    message += ' 失败影响已由调用方登记核对，按当前目标选择下一步。'
                elif failure_review == 'unavailable':
                    message = '失败影响核对记录不可读，请先核对原回执和可能的副作用，不要重发。'
                elif failure_review == 'pending':
                    message = '外部派工已登记为失败，请先核对原回执和可能的副作用，不要重发。'
                if event.get('source_stale') is True:
                    message += ' 旧观察，需正式重新读取；不能据此判断当前状态。'
                action = (job.get('next_action') if ambiguous or state == 'review_required' or failure_review == 'checked'
                          else assessment.get('next_action') or job.get('next_action'))
                intent = job.get('intent') if isinstance(job.get('intent'), dict) else {}
                goal = intent.get('goal') if 'intent' in job else job.get('initial_instruction',job.get('instruction'))
                inbox.append({'id':'external-turn:'+job['id']+':'+event['event_id'],
                    'event_id':event['event_id'], 'task_id':task_id,'kind':'external_turn_review','group':'act',
                    'title':job.get('title') or '本机工作', 'judgment':message,
                    'severity':'high' if ambiguous or state in ('review_required','blocked','unknown','dispatch_unknown') or failure_review in ('pending','unavailable') else 'normal',
                    'state':state, 'current_goal':goal if isinstance(goal,str) else None,
                    'failure_review_state':failure_review,
                    'next_action':action or '', 'object_id':job.get('object_id'),
                    'action':{'type':'open_task','job_id':job['id'],'task_id':task_id,'label':'查看外部会话观察'},
                    'source':event.get('source'),'observed_at':event.get('observed_at'),
                    'source_stale':event.get('source_stale'),
                    'updated_at':event.get('observed_at') or job.get('updated_at'),
                    'notification':{'state':'not_connected'}})
            if job['id'] in external_errors:
                inbox.append({'id':'external-turn-unavailable:'+job['id'],'task_id':task_id,
                    'kind':'external_turn_unavailable','group':'act','title':job.get('title') or '本机工作',
                    'judgment':'外部回合观察不可读，请核对原任务和原会话；不要重复派发。',
                    'severity':'high','object_id':job.get('object_id'),
                    'action':{'type':'open_task','job_id':job['id'],'task_id':task_id,'label':'核对外部观察'},
                    'source':'调用方登记的外部会话观察','updated_at':job.get('updated_at'),
                    'notification':{'state':'not_connected'}})
            for attempt in sorted(result_pending[job['id']]):
                inbox.append({'id':f'result-unknown:{job["id"]}:{attempt}', 'task_id':task_id,
                    'attempt':attempt, 'kind':'result_outcome_unknown', 'group':'act',
                    'title':job.get('title') or '本机工作',
                    'judgment':f'第 {attempt} 轮成果保存结果不明，请先核对实际记录和回执，不要重做。',
                    'severity':'high', 'state':'outcome_unknown', 'object_id':job.get('object_id'),
                    'action':{'type':'open_task','job_id':job['id'],'task_id':task_id,'label':'核对成果保存结果'},
                    'source':'AgentJobs 成果保存记录', 'updated_at':job.get('updated_at'),
                    'notification':{'state':'not_connected'}})
            if job['id'] in result_errors:
                inbox.append({'id':'result-unavailable:'+job['id'], 'task_id':task_id,
                    'kind':'result_outcome_unknown', 'group':'act','title':job.get('title') or '本机工作',
                    'judgment':'成果保存记录不可读，请先核对原任务和回执，不要重做。',
                    'severity':'high', 'state':'unknown', 'object_id':job.get('object_id'),
                    'action':{'type':'open_task','job_id':job['id'],'task_id':task_id,'label':'核对任务'},
                    'source':'AgentJobs 成果保存记录', 'updated_at':job.get('updated_at'),
                    'notification':{'state':'not_connected'}})
            open_events = [event for event in completions[job['id']]
                           if _completion_needs_attention(job['id'], event, completions)]
            for event in open_events:
                state = event.get('state') or 'unknown'
                dispatch_blocked = event.get('dispatch_blocked') if isinstance(event.get('dispatch_blocked'), dict) and not event.get('dispatch') else None
                if dispatch_blocked:
                    state = 'dispatch_blocked'
                assessment = event.get('assessment') if isinstance(event.get('assessment'), dict) else {}
                stale_intent = state == 'intent_changed' or event.get('intent_changed') is True
                stale = state == 'review_required' or stale_intent or event.get('next_action_review_required') is True
                action = job.get('next_action') if stale or event.get('next_action_changed') else assessment.get('next_action') or job.get('next_action')
                message = event.get('reason') or _COMPLETION_MESSAGES.get(state, _COMPLETION_MESSAGES['unknown'])
                if stale_intent and state not in ('intent_changed','review_required'):
                    message += ' 任务目标或决定已变化，仍需重新验收。'
                if event.get('next_action_changed') is True and not event.get('reason'):
                    message += (' 任务下一动作已变化，仍需重新验收。' if event.get('next_action_review_required')
                                else ' 任务下一动作已变化；原派工回执保持不变。')
                if dispatch_blocked and isinstance(dispatch_blocked.get('reason'), str) and dispatch_blocked['reason'].strip():
                    message += ' ' + dispatch_blocked['reason'].strip()
                if not stale and isinstance(assessment.get('gap'), str) and assessment['gap'].strip():
                    message += ' ' + assessment['gap'].strip()
                intent = job.get('intent') if isinstance(job.get('intent'), dict) else {}
                goal = (intent.get('goal') if 'intent' in job else
                        job.get('initial_instruction', job.get('instruction')))
                inbox.append({'id':'completion:'+job['id']+':'+event['event_id'],
                    'event_id':event['event_id'], 'task_id':task_id, 'kind':'completion_review', 'group':'act',
                    'title':job.get('title') or '本机工作', 'judgment':message,
                    'severity':'high' if stale or state in ('dispatch_unknown','intent_changed','review_required') else 'normal',
                    'state':state, 'current_goal':goal if isinstance(goal, str) else None,
                    'next_action':action or '', 'object_id':job.get('object_id'),
                    'action':{'type':'open_task','job_id':job['id'],'task_id':task_id,'label':'查看验收与接续'},
                    'source':event.get('source'), 'observed_at':event.get('observed_at'),
                    'updated_at':event.get('observed_at') or job.get('updated_at'),
                    'notification':event.get('notification')})
            if job['id'] in completion_errors:
                failure = job.get('completion_error') if isinstance(job.get('completion_error'), dict) else {}
                inbox.append({'id':'completion-unavailable:'+job['id'], 'task_id':task_id,
                    'kind':'completion_unavailable', 'group':'act','title':job.get('title') or '本机工作',
                    'judgment':'回合验收状态暂不可读，请核对原任务；不能据此认定已闭环。',
                    'severity':'high', 'object_id':job.get('object_id'),
                    'action':{'type':'open_task','job_id':job['id'],'task_id':task_id,'label':'核对任务'},
                    'source':'AgentJobs 回合登记', 'observed_at':failure.get('observed_at'),
                    'updated_at':failure.get('observed_at') or job.get('updated_at'), 'notification':{'state':'not_connected'}})
            if not open_events and not result_pending[job['id']] and job['id'] not in result_errors and job['id'] not in completion_errors and job.get('status') in ('failed', 'needs_input') and job.get('task_kind') != 'group':
                inbox.append({'id':'local:'+job['id'], 'kind':'agent_job', 'group':'act',
                    'title':job.get('title') or '本机工作',
                    'judgment':job.get('error') or job.get('summary') or '请核对成果与中断原因。',
                    'severity':'normal', 'object_id':job.get('object_id'),
                    'action':{'type':'open_task','job_id':job['id'],'task_id':'local:'+job['id'],'label':'核对任务'},
                    'updated_at':job.get('updated_at')})
        # Reuse the same business decisions as the home page. These are
        # projections of existing customer records, not new tasks or copies
        # of inquiry/message data. Website open is not itself a local todo.
        try:
            today = self.app.today.snapshot()
            today_sources = today.get('sources') or {}
            for group, items in today.get('groups', {}).items():
                for item in items:
                    if item.get('kind') not in ('agent_job', 'agent_job_running', 'cloud_run'):
                        business_items.append({**item, 'business_group': group})
            for name in ('customers', 'prospects', 'gmail', 'buyer_mail', 'website'):
                sources[name] = today_sources.get(name, {'state': 'unavailable'})
            for item in today.get('groups', {}).get('act', []):
                kind, oid = item.get('kind'), item.get('object_id')
                if kind in ('customer_reply', 'buyer_mail', 'catalog_status') or (
                    kind == 'customer_action' and str(oid or '').startswith('customer:website-')
                ):
                    inbox.append(dict(item))
        except Exception:
            # A missing business source must not make the task list fail or
            # look as though the customer inbox was successfully read.
            for name in ('customers', 'prospects', 'gmail', 'buyer_mail', 'website'):
                sources[name] = {'state': 'unavailable'}
        try:
            cloud = self.app.cloud_review.workspace_status()
            sources['cloud'] = {'state': 'ok', 'observed_at': cloud.get('observed_at'),
                                'dispatch': cloud.get('dispatch'), 'truncated': cloud.get('truncated', False)}
            for run in cloud['runs']:
                row = {key: run.get(key) for key in ('title', 'instruction', 'status', 'summary', 'error',
                       'updated_at', 'task_id', 'version', 'source', 'source_version', 'model', 'next_steps', 'priority')}
                row.update(id='cloud:' + run['id'], run_id=run['id'], origin='cloud',
                           object_id=None, job_id=None, observed_at=cloud.get('observed_at'))
                tasks.append(row)
                if run.get('status') in ('awaiting_review', 'failed', 'interrupted', 'blocked', 'outcome_unknown'):
                    inbox.append({'id': row['id'], 'kind': 'cloud_run', 'group': 'decide',
                        'title': row.get('title') or '云端工作',
                        'judgment': row.get('error') or row.get('summary') or '请核对云端执行结果。',
                        'severity': 'high' if run.get('status') != 'awaiting_review' else 'normal',
                        'action': {'type': 'open_cloud_review', 'run_id': run['id'], 'label': '核对云端成果'},
                        'updated_at': row.get('updated_at')})
        except (ValueError, OSError) as error:
            sources['cloud'] = {'state': 'unavailable', 'reason': str(error), 'observed_at': now()}
        inbox.sort(key=lambda item: (0 if item.get('severity') == 'high' else 1,
                                    0 if item.get('group') == 'decide' else 1,
                                    item.get('updated_at') or ''))
        tasks.sort(key=lambda item: item.get('updated_at') or '', reverse=True)
        observed = now()
        for item in business_items:
            tasks.append({**{k:item.get(k) for k in ('object_id', 'title', 'updated_at', 'action')},
                'id':'business:' + str(item['id']), 'origin':'business',
                'status':item.get('business_group', 'act'), 'summary':item.get('judgment'),
                'priority':'high' if item.get('severity') == 'high' else 'low' if item.get('severity') == 'low' else 'normal',
                'priority_basis':'business_severity', 'priority_source':'severity', 'source_severity':item.get('severity') or 'normal',
                'next_action':item.get('judgment') or (item.get('action') or {}).get('label') or '',
                'kind':item.get('kind')})
        try:
            objects = {obj['id']:obj for obj in self.app.business.list_objects()}
            sources['objects'] = {'state':'ok', 'observed_at':observed}
        except Exception:
            objects = {}
            sources['objects'] = {'state':'unavailable', 'observed_at':observed}
        desktop = getattr(self.app, 'desktop_snapshot', None)
        try:
            snapshot = desktop.read() if desktop else {'state':'missing','threads':[], 'observed_at':None,
                'source':DESKTOP_SOURCE, 'automatic_refresh':False,
                'reason':'尚未导入；本机后台没有持续读取桌面会话的连接器。'}
        except (ValueError, OSError, RuntimeError):
            snapshot = {'state':'unavailable','threads':[], 'observed_at':None, 'source':DESKTOP_SOURCE,
                'automatic_refresh':False,'reason':'无法读取桌面快照。'}
        sources['desktop'] = {k:v for k,v in snapshot.items() if k != 'threads'}
        workstreams = build_workstreams(self.app.root, jobs, snapshot) if getattr(self.app,'root',None) else []
        thread_streams, job_streams = {}, {}
        for stream in workstreams:
            conversation = stream.get('conversation') or {}
            identity = (conversation.get('host_id'), conversation.get('id'))
            if all(identity): thread_streams.setdefault(identity,set()).add(stream['id'])
            for related in stream.get('related_jobs',[]):
                job_streams.setdefault(related['id'],set()).add(stream['id'])
        for row in tasks:
            matches = job_streams.get(row.get('id'),set())
            if len(matches)==1: row['workstream_id'] = next(iter(matches))
        for thread in snapshot['threads']:
            status = thread.get('status') or 'unknown'
            observation = thread.get('individual_observation') or {}
            freshness = observation.get('state') or snapshot['state']
            observed_at = observation.get('observed_at') or snapshot.get('snapshot_observed_at') or snapshot.get('observed_at')
            matches = thread_streams.get((thread['hostId'],thread['id']),set())
            workstream_id = next(iter(matches)) if len(matches)==1 else None
            tasks.append({'id':'desktop:' + quote(thread['hostId'],safe='') + ':' + quote(thread['id'],safe=''),
                'thread_id':thread['id'], 'host_id':thread['hostId'], 'origin':'desktop', 'object_id':None,
                'title':thread.get('title') or '桌面会话', 'status':status if freshness=='ok' and status!='notLoaded' else 'unknown',
                'source_status':status, 'source':observation.get('source') or DESKTOP_SOURCE, 'updated_at':thread.get('updatedAt'),
                'observed_at':observed_at, 'observation_attempted_at':observation.get('attempted_at') or snapshot.get('observed_at'),
                'snapshot_state':freshness, 'snapshot_age_seconds':observation.get('age_seconds', snapshot.get('age_seconds')),
                'snapshot_imported_at':snapshot.get('imported_at'), 'workstream_id':workstream_id,
                'conversation_scope':'reference_only',
                'next_action':'请在原桌面会话核对；此处不读取历史或控制执行。'})
        for source in sources.values():
            if source is not sources['desktop']: source.setdefault('observed_at', observed)
        jobs_by_id = {job['id']: job for job in jobs}
        def belongs_to_group(row):
            parent = row.get('parent_job_id')
            seen = set()
            found = False
            while parent and parent not in seen:
                seen.add(parent)
                item = jobs_by_id.get(parent)
                if not item:
                    return False
                if item.get('status') == 'cancelled':
                    return False
                if item.get('task_kind') == 'group':
                    found = True
                parent = item.get('parent_job_id')
            return found and parent is None
        def priority_effect(row):
            if (row['origin'] != 'local' or row.get('task_kind') == 'group'
                    or row.get('status') != 'planned' or row.get('attempt', 0)
                    or (row.get('batch_id') and row.get('mode') == 'outreach_research')):
                return 'display_only'
            if not row.get('parent_job_id'):
                return 'explicit_standalone_dispatch'
            return 'explicit_group_dispatch' if belongs_to_group(row) else 'display_only'
        for row in tasks:
            obj = objects.get(row.get('object_id'), {})
            oid = row.get('object_id') or ''
            kind = obj.get('kind') or oid.split(':')[0]
            source_path = str(row.get('source') or obj.get('source') or '').replace('\\','/')
            line = ((row.get('workstream_id') if row.get('workstream_id') in ('alibaba','website') else 'other') if row['origin']=='desktop' else
                    'alibaba' if row.get('kind')=='catalog_status' or oid=='channel:alibaba' or source_path.startswith('02_Alibaba运营/') else
                    'website' if oid.startswith('customer:website-') or source_path.startswith('03_独立站/') else
                    'domestic' if oid == 'channel:douyin' else
                    'creation' if kind == 'creation' else
                    'international' if kind in ('customer','prospect') else
                    'products' if kind == 'product' else 'other')
            row.update(business_line=line, object_title=obj.get('title') or row.get('object_id') or '未关联对象',
                executor='codex_cli' if row['origin']=='local' else 'paired_cloud' if row['origin']=='cloud' else 'codex_desktop' if row['origin']=='desktop' else 'business_owner',
                priority=(row.get('priority') or 'normal') if row['origin']=='local' else row.get('priority'),
                priority_basis=row.get('priority_basis') or ('registered' if row.get('priority') else 'local_default' if row['origin']=='local' else 'unregistered'),
                next_action=(row.get('next_action') if row.get('next_action') is not None else row.get('next_steps') or
                    ({'planned':'核对计划后显式派发', 'running':'等待执行结果', 'queued':'等待已派发任务启动',
                      'failed':'核对中断原因与已有成果', 'needs_input':'补充所需信息', 'completed':'核对成果'}
                     .get(row.get('status'), '') if row['origin']=='local' else '')),
                blocker=row.get('error') or ('前置任务：' + ', '.join(row['depends_on']) if row.get('depends_on') else ''),
                result=row.get('summary') or '', observed_at=row.get('observed_at', observed),
                source=row.get('source') or ('AgentJobs' if row['origin']=='local' else 'paired_cloud_queue' if row['origin']=='cloud' else 'business_source'),
                capabilities={'adjust':row['origin']=='local',
                    'scheduling_effect':priority_effect(row),
                    'next_action_effect':'next_attempt' if row['origin']=='local' and row.get('task_kind')!='group' else 'none',
                    'external_conversation_control':False,
                    'read_only_reason':'' if row['origin']=='local' else '此总览未接入该来源的安全写入。'})
            if row['origin']=='local':
                pending = [event for event in row.get('completion_events', []) if event.get('state') != 'verified_complete']
                row['completion_pending'] = len(pending)
                if row.get('job_id') in result_errors or result_pending.get(row.get('job_id')):
                    row['blocker'] = '成果保存结果不明，请先核对实际记录和回执，不要重做。'
                elif row.get('job_id') in completion_errors and not row['blocker']:
                    row['blocker'] = '回合验收状态暂不可读。'
                elif pending:
                    latest = max(pending, key=lambda event: (event.get('attempt') if type(event.get('attempt')) is int else -1,
                                                              str(event.get('observed_at') or '')))
                    state = latest.get('state') or 'unknown'
                    row['completion_state'] = state
                    if isinstance(latest.get('dispatch_blocked'), dict) and not latest.get('dispatch'):
                        state = 'dispatch_blocked'
                        row['completion_state'] = state
                    if state in ('blocked','unknown','intent_changed','review_required','dispatch_failed','dispatch_unknown','dispatch_blocked') and not row['blocker']:
                        row['blocker'] = latest.get('reason') or _COMPLETION_MESSAGES.get(state, _COMPLETION_MESSAGES['unknown'])
                        if state=='dispatch_blocked' and latest['dispatch_blocked'].get('reason'):
                            row['blocker'] += ' ' + str(latest['dispatch_blocked']['reason'])
            row['freshness'] = ({'state':row.get('snapshot_state'), 'updated_at':row.get('updated_at'),
                'age_seconds':row.get('snapshot_age_seconds')} if row['origin']=='desktop'
                else self._freshness(row.get('updated_at'), observed))
            row['conversation_scope'] = 'reference_only' if row['origin']=='desktop' or any(c.get('control')=='reference_only' for c in row.get('conversations') or []) else None
        options = {key:[{'value':value, 'label':value} for value in sorted({str(row.get(key)) for row in tasks if row.get(key)})]
                   for key in ('business_line','object_id','executor','priority')}
        tasks = [row for row in tasks if all(str(row.get(key) or '') == value for key,value in filters.items() if value)]
        return {'tasks': tasks, 'workstreams':workstreams, 'sources': sources, 'inbox': inbox, 'observed_at': observed,
                'filters':options, 'applied_filters':filters,
                'completion_capabilities':{'local_finished_events':'agent_jobs' if local_state=='ok' and callable(completion_reader) else 'unavailable',
                    'external_turn_bridge':'not_connected','push_notification':'not_connected'},
                'scheduling_effect':'explicit_standalone_or_group_dispatch_only',
                'scope': '本机 AgentJobs、已配对云队列、现有业务待办及由 Dot 导入的桌面会话只读快照（非实时、未自动更新）；未导入或未登记的会话和其他数据库不在此列表。'}

    @staticmethod
    def _freshness(updated_at, observed_at):
        try:
            source = datetime.fromisoformat(updated_at.replace('Z','+00:00'))
            if source.tzinfo is None:
                return {'state':'unknown', 'updated_at':updated_at, 'age_seconds':None}
            age = max(0, (datetime.fromisoformat(observed_at) - source).total_seconds())
            return {'state':'recent' if age < 86400 else 'older', 'updated_at':updated_at, 'age_seconds':int(age)}
        except (ValueError, TypeError, AttributeError):
            return {'state':'unknown', 'updated_at':updated_at, 'age_seconds':None}

    def route(self, instruction, object_id=None):
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 12000:
            raise ValueError('请填写1至12000字的目标。')
        instruction = instruction.strip()
        objects = self.app.business.list_objects()
        needs_confirmation = False
        if object_id is not None:
            obj = self.app.business.get_object(object_id)
            matches = [obj]
        else:
            # A name/alias hit supplies candidates only. Existing exact object
            # identifiers and a whole-instruction title retain their routing.
            exact, suggested = [], []
            def mentioned(value):
                return isinstance(value, str) and bool(value.strip()) and re.search(
                    r'(?<![A-Za-z0-9:_-])' + re.escape(value.strip()) + r'(?![A-Za-z0-9:_-])', instruction, re.I)
            for obj in objects:
                keys = [obj['id']]
                if obj.get('kind') == 'product':
                    keys.append(obj['id'].removeprefix('product:'))
                if obj.get('title') == instruction or any(mentioned(key) for key in keys):
                    exact.append(obj)
                aliases = obj.get('aliases') or []
                if isinstance(aliases, str): aliases = [aliases]
                if any(mentioned(key) for key in [obj.get('title'), obj.get('current_model'), *aliases]):
                    suggested.append(obj)
            by_id = {obj['id']:obj for obj in [*exact, *suggested]}
            matches = list(by_id.values())
            needs_confirmation = len(exact) != 1 or len(matches) != 1
        candidates = [{key: obj.get(key) for key in ('id', 'title', 'kind')} for obj in matches]
        if needs_confirmation or len(matches) != 1:
            return {'action': 'choose', 'instruction': instruction, 'candidates': candidates,
                    'jobs': [], 'reason': '请选择明确的业务对象，尚未创建或执行任务。'}
        oid = matches[0]['id']
        jobs = [job for job in self.app.agent_jobs.list_jobs() if job.get('object_id') == oid
                and job.get('task_kind') != 'group' and job.get('status') != 'cancelled']
        # Existing work is shown, never resumed or duplicated by text similarity.
        return {'action': 'continue' if jobs else 'create', 'object_id': oid,
                'instruction': instruction, 'candidates': candidates, 'jobs': jobs,
                'reason': '已有工作请先查看上下文；不会自动重复执行。' if jobs else '对象已确认，可保存为现有任务系统中的计划。'}
