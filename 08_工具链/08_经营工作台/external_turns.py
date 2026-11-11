"""Caller-attested external turn evidence on the existing AgentJobs record.

This module neither reads a Codex thread nor sends a message. A caller must
use the supported tool and attest exactly what it observed; an unavailable or
incomplete read is never evidence that a turn or request did not exist.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import datetime, timezone

from completion_followup import ASSESSMENT_STATES, DISPOSITIONS, EVIDENCE_CLOCK_SKEW, _evidence, _intent_version, stamp
from workspaces import WorkspaceConflict


SOURCE = 'codex_app.read_thread'
SEND_SOURCE = 'codex_app.send_message_to_thread'
HEAD_STATES = {'completed', 'inProgress', 'in_progress', 'failed', 'cancelled', 'unknown'}
HEAD_WITHOUT_START = {'inProgress', 'in_progress', 'unknown'}
RECEIPT_STATES = {'unknown', 'accepted', 'running', 'completed', 'failed'}
UNRESOLVED = {'unknown', 'accepted', 'running'}
ID_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z')


def _identifier(value, label):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError(label + '无效。')
    return value


def _event_id(host_id, thread_id, turn_id):
    identity = [SOURCE, host_id, thread_id, turn_id, 'turn.completed']
    raw = json.dumps(identity, ensure_ascii=True, separators=(',', ':')).encode('ascii')
    return 'external:' + hashlib.sha256(raw).hexdigest()


def _head_key(host_id, thread_id):
    return hashlib.sha256(json.dumps([SOURCE, host_id, thread_id], ensure_ascii=True,
                                     separators=(',', ':')).encode('ascii')).hexdigest()


def _seconds(value, label):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(label + '必须是官方回合的有效 Unix 秒数。')
    try:
        datetime.fromtimestamp(value, timezone.utc)
    except (ValueError, OverflowError, OSError):
        raise ValueError(label + '超出可比较范围。') from None
    return value


def _merge_head(old, incoming):
    """Keep incomparable head observations until their real start times are known."""
    if old is None:
        return incoming, True
    if not isinstance(old, dict):
        raise ValueError('外部会话观察水位不可读。')
    pending = old.get('incomparable_heads', [])
    if not isinstance(pending, list) or any(not isinstance(item, dict) for item in pending):
        raise ValueError('外部会话待比较观察不可读。')
    primary = {key:value for key,value in old.items() if key != 'incomparable_heads'}
    candidates = [primary] + copy.deepcopy(pending)
    identities = set()
    times = []
    for candidate in candidates:
        if (any(candidate.get(key) != incoming[key] for key in ('source','host_id','thread_id'))
                or candidate.get('status') not in HEAD_STATES):
            raise ValueError('外部会话待比较观察来源或状态不可读。')
        identity = _identifier(candidate.get('turn_id'), '原最新回合标识')
        if identity in identities:
            raise ValueError('外部会话待比较观察身份重复。')
        identities.add(identity)
        start = candidate.get('started_at')
        if start is None:
            if candidate.get('status') not in HEAD_WITHOUT_START:
                raise ValueError('原最新回合缺少有效开始时间。')
        else:
            _seconds(start, '原最新回合开始时间')
        try:
            observed = datetime.fromisoformat(candidate['observed_at'])
            if observed.tzinfo is None or observed.utcoffset() is None:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise ValueError('外部会话观察时间不可读。') from None
        times.append(observed)
    observed = datetime.fromisoformat(incoming['observed_at'])
    index = next((i for i,item in enumerate(candidates)
                  if item['turn_id'] == incoming['turn_id']), None)
    if index is None:
        if observed < max(times):
            return old, False
        if observed == max(times):
            raise WorkspaceConflict('相同观察时间的会话状态冲突，保留原记录。')
        if len(candidates) >= 100:
            raise WorkspaceConflict('待比较的回合过多，请先核对原会话。')
        candidates.append(copy.deepcopy(incoming))
    else:
        prior = candidates[index]
        if observed < times[index]:
            return old, False
        if observed == times[index]:
            if any(prior.get(key) != incoming[key] for key in ('turn_id','status','started_at')):
                raise WorkspaceConflict('相同观察时间的会话状态冲突，保留原记录。')
            return old, False
        old_start, new_start = prior.get('started_at'), incoming['started_at']
        if old_start is not None and new_start is not None and old_start != new_start:
            raise WorkspaceConflict('同一回合的开始时间冲突，保留原观察。')
        if prior.get('status') in ('completed','failed','cancelled') and incoming['status'] != prior['status']:
            raise WorkspaceConflict('同一回合终态冲突或回退，保留原观察。')
        updated = copy.deepcopy(incoming)
        if updated['started_at'] is None and old_start is not None:
            updated['started_at'] = old_start  # Retain the previously observed real time.
        candidates[index] = updated
    starts = [item['started_at'] for item in candidates if item.get('started_at') is not None]
    if len(starts) != len(set(starts)):
        raise WorkspaceConflict('两个回合开始时间相同，先后不明，请先核对。')
    if len(starts) == len(candidates):
        merged = max(candidates, key=lambda item:item['started_at'])
    else:
        # Do not replace a known head with an incomparable newer observation.
        # Keep every candidate so learning one time cannot hide another one.
        merged = copy.deepcopy(candidates[0])
        if len(candidates) > 1:
            merged['incomparable_heads'] = candidates[1:]
    return merged, merged != old


def _failure_is_resolved(receipt):
    resolution = receipt.get('failure_resolution')
    if not isinstance(resolution,dict) or resolution.get('verification') != 'caller_attested':
        return False
    try:
        recorded = datetime.fromisoformat(resolution['recorded_at'])
        if recorded.tzinfo is None or recorded.utcoffset() is None: return False
        if recorded.astimezone(timezone.utc) > datetime.now(timezone.utc) + EVIDENCE_CLOCK_SKEW:return False
        _evidence(resolution.get('evidence'))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return True


class ExternalTurns:
    @staticmethod
    def _external_defaults(job):
        revision = job.get('external_revision', 0)
        events = job.get('external_turn_events', {})
        heads = job.get('external_thread_heads', {})
        if type(revision) is not int or revision < 0 or not isinstance(events, dict) or not isinstance(heads, dict):
            raise ValueError('外部回合登记不可读，请先核对原任务。')
        job.setdefault('external_revision', revision)
        job.setdefault('external_turn_events', events)
        job.setdefault('external_thread_heads', heads)
        return job

    def _external_reference(self, job, host_id, thread_id, *, allow_unbound=False):
        """Require one explicit reference and reject ambiguous other task links."""
        _identifier(host_id, '主机标识'); _identifier(thread_id, '会话标识')
        refs = job.get('conversations', [])
        if not isinstance(refs, list):
            raise ValueError('任务会话关联不可读，请先核对。')
        matches = [ref for ref in refs if isinstance(ref, dict) and ref.get('provider') == 'codex'
                   and ref.get('conversation_id') == thread_id and ref.get('control') == 'reference_only']
        if len(matches) != 1:
            raise WorkspaceConflict('任务未明确关联唯一的外部会话，不能按标题或工作线猜测。')
        ref = matches[0]
        bound = ref.get('host_id')
        if bound != host_id and not (allow_unbound and bound is None):
            raise WorkspaceConflict('会话主机未绑定或与原关联不一致，请先核对。')
        for other in self.list_jobs():
            if other.get('id') == job.get('id'):
                continue
            other_refs = other.get('conversations', [])
            if not isinstance(other_refs, list):
                raise WorkspaceConflict('其他任务的会话关联不可读，无法确认唯一归属。')
            for candidate in other_refs:
                if (isinstance(candidate, dict) and candidate.get('provider') == 'codex' and
                        candidate.get('conversation_id') == thread_id and
                        candidate.get('host_id') in (None, host_id)):
                    raise WorkspaceConflict('该会话可能关联多个任务，先消除歧义再登记。')
        return ref

    def bind_external_thread(self, job_id, *, expected_version, host_id, thread_id):
        """Add an explicit host to an already linked reference; no control granted."""
        with self._write():
            job = self._external_defaults(self._continuity_defaults(self.get_job(job_id)))
            if type(expected_version) is not int or expected_version != job['version']:
                raise WorkspaceConflict('任务版本已变化，请重新读取会话关联。')
            ref = self._external_reference(job, host_id, thread_id, allow_unbound=True)
            if ref.get('host_id') == host_id:
                return copy.deepcopy(job)
            ref['host_id'] = host_id
            ref['host_bound_at'] = stamp()
            job['external_revision'] += 1
            self._event(job, 'external_thread_bound', '已为外部引用明确主机；仅供观测，不授予控制。')
            self._save(job)
            return copy.deepcopy(job)

    def register_external_turn(self, job_id, *, expected_version, host_id, thread_id, turn_id,
                               started_at, completed_at, head_turn_id, head_status, head_started_at,
                               observed_at, evidence):
        """Register a caller-attested completed turn and latest-page head."""
        for value, label in ((host_id, '主机标识'), (thread_id, '会话标识'),
                             (turn_id, '回合标识'), (head_turn_id, '最新回合标识')):
            _identifier(value, label)
        if head_status not in HEAD_STATES or (turn_id == head_turn_id and head_status != 'completed'):
            raise ValueError('最新回合状态与完成事件不一致。')
        started_at = _seconds(started_at, '回合开始时间')
        completed_at = _seconds(completed_at, '回合结束时间')
        if head_started_at is None:
            if head_turn_id == turn_id or head_status not in HEAD_WITHOUT_START:
                raise ValueError('仅不同的进行中或未知回合可缺少开始时间。')
        else:
            head_started_at = _seconds(head_started_at, '最新回合开始时间')
        observed = _evidence({'source': SOURCE, 'observed_at': observed_at, 'detail': evidence})
        observed_time = datetime.fromisoformat(observed['observed_at'])
        if (started_at > completed_at or completed_at > (observed_time + EVIDENCE_CLOCK_SKEW).timestamp() or
                (head_started_at is not None and head_started_at > (observed_time + EVIDENCE_CLOCK_SKEW).timestamp()) or
                (turn_id == head_turn_id and started_at != head_started_at) or
                (head_started_at is not None and head_started_at < started_at)):
            raise ValueError('回合起止时间或观察时间不一致。')
        event_id = _event_id(host_id, thread_id, turn_id)
        with self._write():
            job = self._external_defaults(self._continuity_defaults(self.get_job(job_id)))
            self._external_reference(job, host_id, thread_id)
            events, heads = job['external_turn_events'], job['external_thread_heads']
            previous = events.get(event_id)
            if previous is not None:
                if (not isinstance(previous, dict) or previous.get('event_id') != event_id or
                        previous.get('source') != SOURCE or previous.get('event_type') != 'turn.completed' or
                        previous.get('host_id') != host_id or previous.get('thread_id') != thread_id or previous.get('turn_id') != turn_id or
                        previous.get('started_at') != started_at or previous.get('completed_at') != completed_at):
                    raise WorkspaceConflict('相同回合身份的原始时间不一致，保留原记录等待核对。')
            key = _head_key(host_id, thread_id)
            old_head = heads.get(key)
            next_head = {'source':SOURCE, 'host_id':host_id, 'thread_id':thread_id,
                         'turn_id':head_turn_id, 'status':head_status, 'started_at':head_started_at,
                         'observed_at':observed['observed_at']}
            next_head, replace_head = _merge_head(old_head, next_head)
            if previous is not None and not replace_head:
                return copy.deepcopy(previous)
            if type(expected_version) is not int or expected_version != job['version']:
                raise WorkspaceConflict('任务版本已变化，请重新读取后登记观察。')
            if previous is None:
                previous = {'event_id':event_id, 'source':SOURCE, 'event_type':'turn.completed',
                    'host_id':host_id, 'thread_id':thread_id, 'turn_id':turn_id,
                    'started_at':started_at, 'completed_at':completed_at, 'observed_at':observed['observed_at'],
                    'evidence':observed, 'verification':'caller_attested', 'recorded_at':stamp(),
                    'intent_version_at_observation':_intent_version(job), 'assessment':None, 'dispatch':None}
                events[event_id] = previous
            if replace_head:
                heads[key] = next_head
            job['external_revision'] += 1
            self._event(job, 'external_turn_observed', '已登记调用方核读的外部回合元数据；未自动读取或派工。')
            self._save(job)
            return copy.deepcopy(previous)

    def external_turns_view(self, job):
        job = self._external_defaults(copy.deepcopy(job))
        events, heads = job['external_turn_events'], job['external_thread_heads']
        intent_version = _intent_version(job)
        result = []
        for key, raw in events.items():
            if not isinstance(raw, dict) or any(not isinstance(raw.get(k), str) for k in ('host_id','thread_id','turn_id')):
                raise ValueError('外部回合记录身份无效。')
            if key != _event_id(raw['host_id'], raw['thread_id'], raw['turn_id']) or raw.get('event_id') != key:
                raise ValueError('外部回合记录身份不一致。')
            head = heads.get(_head_key(raw['host_id'], raw['thread_id']))
            if not isinstance(head, dict):raise ValueError('外部会话观察水位缺失。')
            try:
                head_time = datetime.fromisoformat(head['observed_at'])
                if head_time.tzinfo is None or head_time.utcoffset() is None:raise ValueError()
                age_seconds = max(0.0, (datetime.now(timezone.utc) - head_time.astimezone(timezone.utc)).total_seconds())
            except (KeyError, TypeError, ValueError, OverflowError):
                raise ValueError('外部会话观察时间不可读。') from None
            item = copy.deepcopy(raw)
            same_thread = [x for x in events.values() if isinstance(x, dict) and x.get('host_id') == raw['host_id']
                           and x.get('thread_id') == raw['thread_id']]
            comparable = [x.get('completed_at') for x in same_thread if isinstance(x.get('completed_at'), (int,float))
                          and not isinstance(x.get('completed_at'), bool)]
            pending = head.get('incomparable_heads', [])
            if not isinstance(pending, list):raise ValueError('外部会话待比较观察不可读。')
            order_ambiguous = bool(head.get('started_at') is None or pending or
                                   (comparable and raw.get('completed_at') == max(comparable) and
                                    sum(x == raw.get('completed_at') for x in comparable) > 1))
            current = (head.get('turn_id') == raw['turn_id'] and head.get('status') == 'completed' and
                       not order_ambiguous and bool(comparable) and raw.get('completed_at') == max(comparable))
            assessment = item.get('assessment') if isinstance(item.get('assessment'), dict) else None
            dispatch = item.get('dispatch') if isinstance(item.get('dispatch'), dict) else None
            dispatch_state = dispatch.get('state') if dispatch else None
            changed = bool(assessment and (type(intent_version) is not int or assessment.get('intent_version') != intent_version))
            if dispatch_state in UNRESOLVED:
                state = 'dispatch_' + dispatch_state
            elif dispatch_state in ('completed','failed'):
                target = dispatch.get('target_turn_id')
                target_registered = bool(target and any(x.get('turn_id') == target for x in same_thread))
                state = 'historical' if dispatch_state == 'completed' and target_registered else 'dispatch_' + dispatch_state
            elif order_ambiguous:
                state = 'review_required'
            elif not current:
                state = 'historical'
            elif changed:
                state = 'review_required'
            elif assessment:
                state = ASSESSMENT_STATES.get(assessment.get('disposition'), 'unknown')
            else:
                state = 'awaiting_review'
            item.update(state=state, current=current, order_ambiguous=order_ambiguous,
                        intent_changed=changed, head_turn_id=head.get('turn_id'), head_status=head.get('status'),
                         head_started_at=head.get('started_at'), incomparable_head_count=len(pending),
                        head_observed_at=head.get('observed_at'), source_stale=age_seconds>600,
                        source_age_seconds=int(age_seconds))
            result.append(item)
        return sorted(result, key=lambda item:(item['completed_at'], item['event_id']), reverse=True)

    def _external_event(self, job, event_id):
        if not isinstance(event_id, str) or not re.fullmatch(r'external:[0-9a-f]{64}', event_id):
            raise ValueError('外部事件标识无效。')
        event = job['external_turn_events'].get(event_id)
        if not isinstance(event, dict):raise ValueError('找不到该外部回合观察。')
        self._external_reference(job, event.get('host_id'), event.get('thread_id'))
        _identifier(event.get('turn_id'), '回合标识')
        if (event.get('source') != SOURCE or event.get('event_type') != 'turn.completed' or
                event.get('event_id') != event_id or
                _event_id(event['host_id'],event['thread_id'],event.get('turn_id')) != event_id):
            raise ValueError('外部回合观察身份不一致。')
        return event

    def _external_current_event(self, job, event_id):
        event = self._external_event(job,event_id)
        view = next((row for row in self.external_turns_view(job) if row['event_id'] == event_id), None)
        if not view or not view['current'] or view['order_ambiguous'] or view['source_stale']:
            raise WorkspaceConflict('该回合不是近期已观察的最新完成回合，或先后不明；不能沿旧观察派工。')
        return event

    def assess_external_turn(self, job_id, event_id, *, expected_version, expected_intent_version,
                             disposition, goal_status, capability_status, result_ref, gap, next_action, evidence):
        if type(expected_version) is not int or type(expected_intent_version) is not int:
            raise ValueError('请提供任务和意图版本。')
        if disposition not in DISPOSITIONS or goal_status not in ('met','not_met','unknown') or capability_status not in ('met','not_met','unknown'):
            raise ValueError('验收状态无效。')
        for value, limit in ((result_ref,2000),(gap,4000),(next_action,4000)):
            if not isinstance(value,str) or len(value)>limit:raise ValueError('验收文字无效。')
        result_ref,gap,next_action = result_ref.strip(),gap.strip(),next_action.strip()
        if disposition == 'verified_complete' and (goal_status != 'met' or capability_status != 'met' or gap or not result_ref):
            raise ValueError('验收完成须有成果、目标和能力均达成且没有欠交付。')
        if disposition != 'verified_complete' and not next_action:raise ValueError('未完成时须提供下一动作。')
        if disposition == 'continue' and goal_status == capability_status == 'met' and not gap:
            raise ValueError('无欠交付时请核对是否需要继续。')
        proof = _evidence(evidence)
        with self._write():
            job = self._external_defaults(self._continuity_defaults(self.get_job(job_id)))
            event = self._external_current_event(job,event_id)
            if expected_intent_version != _intent_version(job):
                raise WorkspaceConflict('任务当前意图已变化，旧验收需要重新核对。')
            previous = event.get('assessment')
            values = {'disposition':disposition,'goal_status':goal_status,'capability_status':capability_status,
                      'result_ref':result_ref,'gap':gap,'next_action':next_action,'evidence':proof,
                      'intent_version':expected_intent_version}
            if isinstance(previous,dict) and all(previous.get(k) == v for k,v in values.items()):
                if event.get('dispatch') is not None or (expected_version == job['version'] and
                        expected_intent_version == _intent_version(job)):
                    return copy.deepcopy(event)
            if type(expected_version) is not int or expected_version != job['version'] or type(expected_intent_version) is not int or expected_intent_version != _intent_version(job):
                raise WorkspaceConflict('任务或当前意图版本已变化，请重新核对。')
            if event.get('dispatch') is not None:
                raise WorkspaceConflict('该回合已有外部请求，须对账，不能覆盖或重发。')
            if isinstance(previous,dict):
                old = copy.deepcopy(previous);old.update(status='superseded',superseded_at=stamp())
                event.setdefault('assessment_history',[]).append(old)
            event['assessment'] = {**values,
                'task_version_at_review':job['version']+1,'reviewed_at':stamp()}
            job['external_revision'] += 1
            self._event(job,'external_turn_assessed','已登记调用方对外部回合的验收；未发送消息。')
            self._save(job)
            return copy.deepcopy(event)

    def prepare_external_dispatch(self, job_id, event_id, *, expected_version, expected_intent_version, request_id, instruction):
        _identifier(request_id, '请求标识')
        if not isinstance(instruction,str) or not instruction.strip() or len(instruction)>12000:
            raise ValueError('请提供本次拟发送内容以计算指纹，不自动发送。')
        digest = hashlib.sha256(instruction.encode('utf-8')).hexdigest()
        with self._write():
            job = self._external_defaults(self._continuity_defaults(self.get_job(job_id)))
            event = self._external_current_event(job,event_id)
            existing = event.get('dispatch')
            if existing is not None:
                if isinstance(existing,dict) and existing.get('request_id') == request_id and existing.get('instruction_sha256') == digest:
                    return {'event':copy.deepcopy(event),'created':False}
                raise WorkspaceConflict('该回合已有外部请求；不得重发或替换。')
            if type(expected_version) is not int or expected_version != job['version'] or type(expected_intent_version) is not int or expected_intent_version != _intent_version(job):
                raise WorkspaceConflict('任务或当前意图版本已变化，请重新核对。')
            assessment = event.get('assessment')
            if (not isinstance(assessment,dict) or assessment.get('disposition') != 'continue' or
                    assessment.get('intent_version') != expected_intent_version or
                    assessment.get('task_version_at_review') != expected_version):
                raise WorkspaceConflict('请按当前目标重新验收并确认下一动作，不能沿用旧版本。')
            for related_job in self.list_jobs():
                related_events = related_job.get('external_turn_events', {})
                if not isinstance(related_events,dict):
                    refs = related_job.get('conversations', [])
                    if isinstance(refs,list) and any(isinstance(ref,dict) and ref.get('provider') == 'codex' and
                                                     ref.get('conversation_id') == event['thread_id'] for ref in refs):
                        raise WorkspaceConflict('同标识会话的外部请求记录不可读，不能确认是否重复。')
                    continue
                for other in related_events.values():
                    receipt = other.get('dispatch') if isinstance(other,dict) else None
                    if related_job.get('id') == job_id and isinstance(receipt,dict) and receipt.get('request_id') == request_id:
                        raise WorkspaceConflict('该请求标识已属于其他回合，不能重复使用。')
                    # A thread ID may survive a host migration or alias. Keep
                    # observations separate, but do not use a host label to
                    # bypass an unresolved request or repeat the same payload.
                    related_thread = (isinstance(other,dict) and other.get('thread_id') == event['thread_id']
                                      and isinstance(receipt,dict))
                    if related_thread and (receipt.get('state') not in RECEIPT_STATES or
                                           not isinstance(receipt.get('instruction_sha256'),str) or
                                           not re.fullmatch(r'[0-9a-f]{64}',receipt['instruction_sha256'])):
                        raise WorkspaceConflict('同标识会话的原回执不可读，不能确认是否重复。')
                    if related_thread and receipt.get('instruction_sha256') == digest:
                        raise WorkspaceConflict('同标识会话的相同指令已有原请求，不能作为新请求重复发送。')
                    if related_thread and (receipt.get('state') in UNRESOLVED or
                                           (receipt.get('state') == 'failed' and not _failure_is_resolved(receipt))):
                        raise WorkspaceConflict('同标识会话存在未知或失败待核对请求；跨主机也须先对账。')
            event['dispatch'] = {'request_id':request_id,'state':'unknown','prepared_at':stamp(),
                'source_turn_id':event['turn_id'],'target_turn_id':None,'intent_version':expected_intent_version,
                'intent':assessment['next_action'],'instruction_sha256':digest,'instruction_length':len(instruction),
                'reason':'请求意图已保存；外部发送结果尚未核对，不得盲目重发。',
                'receipt_source':'caller_attested','observations':[]}
            job['external_revision'] += 1
            self._event(job,'external_dispatch_prepared','仅保存外部请求意图；未调用发送工具。')
            self._save(job)
            return {'event':copy.deepcopy(event),'created':True}

    def observe_external_dispatch(self, job_id, event_id, *, expected_version, request_id, state, evidence,
                                  target_turn_id=None, observed_instruction_sha256=None, correlation=None):
        _identifier(request_id,'请求标识')
        if state not in RECEIPT_STATES:raise ValueError('外部请求状态无效。')
        proof = _evidence(evidence)
        if proof['source'] not in (SOURCE,SEND_SOURCE):raise ValueError('外部回执来源无效。')
        if target_turn_id is not None:_identifier(target_turn_id,'目标回合标识')
        if observed_instruction_sha256 is not None and (not isinstance(observed_instruction_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',observed_instruction_sha256)):
            raise ValueError('所观察内容的指纹无效。')
        if correlation not in (None,'matching_receipt','manual_verification'):raise ValueError('请求与回合的关联依据无效。')
        with self._write():
            job = self._external_defaults(self._continuity_defaults(self.get_job(job_id)))
            event = self._external_event(job,event_id)
            receipt = event.get('dispatch')
            if not isinstance(receipt,dict) or receipt.get('request_id') != request_id:
                raise WorkspaceConflict('请求标识不匹配，不能改写其他回执。')
            if type(expected_version) is not int or expected_version != job['version']:
                raise WorkspaceConflict('任务版本已变化，请重新读取原请求后对账。')
            if state == 'accepted' and proof['source'] != SEND_SOURCE:
                raise ValueError('已受理只能登记调用方实际获得的发送响应。')
            if state == 'accepted' and target_turn_id == event['turn_id']:
                raise ValueError('发送回执中的目标回合不能与原回合相同。')
            if (state == 'accepted' and target_turn_id and receipt.get('accepted_target_turn_id') and
                    receipt['accepted_target_turn_id'] != target_turn_id):
                raise WorkspaceConflict('发送回执中的目标回合冲突，保留原记录。')
            if state in ('running','completed','failed'):
                if proof['source'] != SOURCE or not target_turn_id or target_turn_id == event['turn_id']:
                    raise ValueError('请提供正式读取中的目标新回合与状态。')
                if correlation == 'matching_receipt':
                    if not receipt.get('accepted_target_turn_id') or receipt['accepted_target_turn_id'] != target_turn_id:
                        raise WorkspaceConflict('原发送回执未提供与目标回合匹配的标识。')
                elif correlation == 'manual_verification':
                    if observed_instruction_sha256 != receipt.get('instruction_sha256'):
                        raise WorkspaceConflict('人工核对的完整请求指纹不匹配；保持结果未知。')
                else:
                    raise WorkspaceConflict('新回合存在不证明它属于本请求；请先提供明确关联依据。')
            prior = receipt.get('state')
            if prior in ('completed','failed') and state != prior:
                raise WorkspaceConflict('已有终态回执，冲突观察需另行核对，不能覆盖。')
            if prior == 'running' and state == 'accepted':
                raise WorkspaceConflict('旧受理回执不能覆盖已观察的运行状态。')
            if (state in ('running','completed','failed') and receipt.get('target_turn_id') and
                    receipt['target_turn_id'] != target_turn_id):
                raise WorkspaceConflict('不同目标回合的关联证据冲突，保留原回执。')
            observation = {'state':state,'evidence':proof,'target_turn_id':target_turn_id,
                           'correlation':correlation,'verification':'caller_attested'}
            previous = receipt.get('observations',[])
            if not isinstance(previous,list):raise ValueError('原请求观察记录不可读。')
            if previous and previous[-1] == observation:return copy.deepcopy(event)
            if previous:
                last_time = datetime.fromisoformat(previous[-1]['evidence']['observed_at'])
                this_time = datetime.fromisoformat(proof['observed_at'])
                if this_time < last_time:raise WorkspaceConflict('较旧回执不能覆盖新观察。')
                if this_time == last_time:raise WorkspaceConflict('相同观察时间的回执不一致。')
            previous.append(observation);receipt['observations'] = previous[-100:]
            # A later failed or incomplete observation cannot continue to
            # present an old running/accepted observation as current. The
            # earlier receipt remains in observations for audit.
            receipt['state'] = state
            receipt.update(observation_at=proof['observed_at'],receipt_source='caller_attested')
            if state == 'accepted' and target_turn_id:receipt['accepted_target_turn_id'] = target_turn_id
            if state in ('running','completed','failed'):receipt['target_turn_id'] = target_turn_id
            job['external_revision'] += 1
            self._event(job,'external_dispatch_observed','已登记调用方提供的外部请求观察；未自动发送。')
            self._save(job)
            return copy.deepcopy(event)

    def resolve_external_failure(self, job_id, event_id, *, expected_version, request_id, evidence):
        """Record an explicit review of a failed turn's possible side effects."""
        _identifier(request_id, '请求标识')
        proof = _evidence(evidence)
        with self._write():
            job = self._external_defaults(self._continuity_defaults(self.get_job(job_id)))
            event = self._external_event(job,event_id)
            receipt = event.get('dispatch')
            if not isinstance(receipt,dict) or receipt.get('request_id') != request_id or receipt.get('state') != 'failed':
                raise WorkspaceConflict('没有匹配的失败回执，不能登记失败核对。')
            previous = receipt.get('failure_resolution')
            if isinstance(previous,dict):
                if previous.get('evidence') == proof:return copy.deepcopy(event)
                raise WorkspaceConflict('已有失败核对记录；新依据需先与原记录核对。')
            if type(expected_version) is not int or expected_version != job['version']:
                raise WorkspaceConflict('任务版本已变化，请重新读取原失败回执。')
            receipt['failure_resolution'] = {'evidence':proof,'recorded_at':stamp(),
                                             'verification':'caller_attested'}
            job['external_revision'] += 1
            self._event(job,'external_failure_resolved','已登记调用方对失败轮次及可能副作用的核对；未发送或重试。')
            self._save(job)
            return copy.deepcopy(event)
