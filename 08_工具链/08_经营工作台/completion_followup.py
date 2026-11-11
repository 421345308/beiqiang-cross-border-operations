"""Completion review on the existing AgentJobs record, not a second queue."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

from workspaces import WorkspaceConflict


TERMINAL_RUN_STATES = {'completed', 'failed', 'needs_input'}
DISPOSITIONS = {'verified_complete', 'continue', 'needs_decision', 'blocked', 'unknown'}
ASSESSMENT_STATES = {
    'verified_complete': 'verified_complete',
    'continue': 'ready_to_continue',
    'needs_decision': 'needs_decision',
    'blocked': 'blocked',
    'unknown': 'unknown',
}
DISPATCH_STATES = {'accepted', 'starting', 'running', 'completed', 'failed', 'unknown'}
DISPATCH_IN_FLIGHT = {'accepted', 'starting', 'running', 'unknown'}
EVIDENCE_CLOCK_SKEW = timedelta(minutes=5)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def _intent_version(job):
    intent = job.get('intent')
    # Legacy jobs have version zero with an unrecorded decision set.
    if 'intent' not in job:
        return 0
    if not isinstance(intent, dict) or type(intent.get('version')) is not int or intent['version'] < 0:
        return None
    return intent['version']


def _evidence(value):
    if not isinstance(value, dict) or set(value) != {'source', 'observed_at', 'detail'}:
        raise ValueError('验收依据必须包含来源、带时区的观察时间和具体说明。')
    source, observed, detail = (value.get(key) for key in ('source', 'observed_at', 'detail'))
    if any(not isinstance(text, str) or not text.strip() or len(text) > limit
           for text, limit in ((source, 1000), (observed, 100), (detail, 4000))):
        raise ValueError('验收依据的来源、观察时间和说明均须为非空文本。')
    try:
        parsed = datetime.fromisoformat(observed.strip().replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
    except (ValueError, OverflowError):
        raise ValueError('验收依据的观察时间必须包含时区。') from None
    try:
        if parsed.astimezone(timezone.utc) > datetime.now(timezone.utc) + EVIDENCE_CLOCK_SKEW:
            raise ValueError('验收依据的观察时间不能超出当前时间和允许的时钟偏差。')
    except OverflowError:
        raise ValueError('验收依据的观察时间超出可比较范围。') from None
    return {'source': source.strip(), 'observed_at': parsed.isoformat(), 'detail': detail.strip()}


class CompletionFollowup:
    def _verify_supervisor_guard(self, job, job_id, attempt, supervisor_guard):
        """Validate the internal lease and current policy in the same write transaction."""
        if supervisor_guard is None:
            return None
        from supervisor import verify_guard
        verify_guard(self.app.db, job_id, attempt, supervisor_guard)
        policy = job.get('supervision')
        revision = job.get('supervision_revision')
        criteria = policy.get('acceptance_criteria') if isinstance(policy, dict) else None
        business_case = policy.get('business_case') if isinstance(policy, dict) else None
        case_fields = {'business_outcome', 'current_bottleneck', 'intended_change', 'stop_condition', 'evidence_source'}
        if (job.get('id') != job_id or type(revision) is not int or revision < 1 or
                not isinstance(policy, dict) or policy.get('enabled') is not True or
                policy.get('policy') != 'mail_draft_read_only_v1' or job.get('mode') != 'mail_draft' or
                policy.get('prerequisite_state') != 'ready' or policy.get('value_state') != 'supported' or
                not isinstance(business_case, dict) or set(business_case) != case_fields or
                any(not isinstance(business_case.get(key), str) or not business_case[key].strip() or
                    len(business_case[key]) > 500
                    for key in case_fields) or
                type(policy.get('max_auto_continuations')) is not int or policy['max_auto_continuations'] != 1 or
                not isinstance(criteria, dict) or set(criteria) != {'kind', 'text'} or
                criteria.get('kind') != 'artifact_contains' or not isinstance(criteria.get('text'), str) or
                not criteria['text'].strip() or
                any(not isinstance(policy.get(key), str) or not policy[key].strip()
                    for key in ('continuation_instruction', 'authorization_ref'))):
            raise WorkspaceConflict('监督配置已停用或不可用，停止自动接续。')
        return revision

    def _record_finished_attempt(self, job):
        """Register the current finished attempt once, inside the job write transaction."""
        if not getattr(self, '_transaction', False):
            raise RuntimeError('回合完成登记必须在任务写事务内进行。')
        attempt, status, job_id = job.get('attempt'), job.get('status'), job.get('id')
        if (type(attempt) is not int or attempt < 1 or status not in TERMINAL_RUN_STATES
                or job.get('worker_finished') is not True or not isinstance(job_id, str) or not job_id):
            raise ValueError('只能登记已确认结束的本机任务执行轮次。')
        revision = job.get('completion_revision', 0)
        if type(revision) is not int or revision < 0:
            raise ValueError('回合验收版本无效，请先核对任务。')
        events = job.setdefault('completion_events', {})
        if not isinstance(events, dict):
            raise ValueError('回合验收记录无效，请先核对任务。')
        key, event_id = str(attempt), f'agent-job:{job_id}:attempt:{attempt}'
        previous = events.get(key)
        if previous is not None:
            if not isinstance(previous, dict) or previous.get('event_id') != event_id:
                raise WorkspaceConflict('该轮完成事件的身份不一致，请先核对原任务。')
            if previous.get('run_status') != status:
                raise WorkspaceConflict('该轮结束状态与已记录的回执不同，请先核对原任务。')
            return previous
        runs = job.get('runs') if isinstance(job.get('runs'), list) else []
        matching = [item for item in runs if isinstance(item, dict) and item.get('attempt') == attempt]
        if len(matching) > 1:
            raise WorkspaceConflict('该轮执行记录不唯一，请先核对原任务。')
        run = matching[0] if matching else {}
        plan = run.get('attempt_plan') if isinstance(run.get('attempt_plan'), dict) else job.get('attempt_plan')
        plan = plan if isinstance(plan, dict) and plan.get('attempt') == attempt else {}
        frozen = plan.get('intent') if isinstance(plan.get('intent'), dict) else {}
        intent_version = frozen.get('version')
        if type(intent_version) is not int or intent_version < 0:
            intent_version = None
        artifacts = run.get('artifact_ids') if isinstance(run.get('artifact_ids'), list) else []
        artifacts = [item for item in artifacts if isinstance(item, str) and item]
        event = {'event_id':event_id, 'attempt':attempt, 'source':'agent_jobs', 'observed_at':stamp(),
                 'run_status':status, 'intent_version':intent_version, 'artifact_ids':artifacts,
                 'summary':str(run.get('summary') or job.get('summary') or '')[:4000],
                 'notification':'not_connected', 'assessment':None, 'dispatch':None}
        events[key] = event
        job['completion_revision'] = revision + 1
        return event

    def completion_view(self, job):
        """Return current review state without mutating stored execution facts."""
        job = copy.deepcopy(job)
        sync = getattr(self, '_sync_followup_receipts', None)
        if callable(sync):
            sync(job)  # Project current local evidence; a read never writes or dispatches.
        events = job.get('completion_events')
        if 'completion_events' not in job:
            return []
        if not isinstance(events, dict):
            raise ValueError('回合验收记录不可读，请核对原任务。')
        current_intent = _intent_version(job)
        views = []
        for key, event in events.items():
            if (not isinstance(event, dict) or type(event.get('attempt')) is not int or event['attempt'] < 1 or
                    key != str(event['attempt']) or
                    event.get('event_id') != f"agent-job:{job.get('id')}:attempt:{event['attempt']}"):
                raise ValueError('回合验收记录身份无效，请核对原任务。')
            item = copy.deepcopy(event)
            assessment = item.get('assessment') if isinstance(item.get('assessment'), dict) else None
            raw_dispatch = item.get('dispatch')
            dispatch = raw_dispatch if isinstance(raw_dispatch, dict) else None
            reference_version = assessment.get('intent_version') if assessment else item.get('intent_version')
            known = type(reference_version) is int and type(current_intent) is int
            changed = bool(known and reference_version != current_intent)
            dispatch_state = dispatch.get('state') if dispatch is not None else None
            if raw_dispatch is not None and dispatch_state not in DISPATCH_STATES:
                dispatch_state = 'unknown'
            if dispatch_state in DISPATCH_IN_FLIGHT:
                state = 'dispatch_' + dispatch_state
            elif not known or changed:
                state = 'review_required'
            elif dispatch_state in DISPATCH_STATES:
                state = 'dispatch_' + dispatch_state
            elif assessment:
                state = ASSESSMENT_STATES.get(assessment.get('disposition'), 'unknown')
            else:
                state = 'awaiting_review'
            item.update(state=state, effective_state=state, intent_changed=changed,
                        intent_version_known=known, current_intent_version=current_intent)
            views.append(item)
        return sorted(views, key=lambda item:item['attempt'], reverse=True)

    def assess_completion(self, job_id, attempt, *, expected_version, expected_intent_version,
                          disposition, goal_status, capability_status, result_ref, gap, next_action, evidence,
                          supervisor_guard=None):
        """Record an evidence-backed review without launching or controlling a conversation."""
        if type(attempt) is not int or attempt < 1:
            raise ValueError('请提供有效的执行轮次。')
        if type(expected_version) is not int or expected_version < 0 or type(expected_intent_version) is not int or expected_intent_version < 0:
            raise ValueError('请提供实际读取的任务版本和意图版本。')
        if disposition not in DISPOSITIONS or goal_status not in ('met', 'not_met', 'unknown') or capability_status not in ('met', 'not_met', 'unknown'):
            raise ValueError('验收结论或目标与能力状态无效。')
        for value, limit in ((result_ref, 2000), (gap, 4000), (next_action, 4000)):
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError('成果、缺口和下一动作须为限定长度的文本。')
        result_ref, gap, next_action = result_ref.strip(), gap.strip(), next_action.strip()
        if disposition == 'verified_complete':
            if goal_status != 'met' or capability_status != 'met' or gap or not result_ref:
                raise ValueError('验收完成须目标和能力均已满足、提供成果位置且没有未完成缺口。')
        elif not next_action:
            raise ValueError('尚未完成的验收须明确具体下一动作。')
        if disposition == 'continue' and goal_status == 'met' and capability_status == 'met' and not gap:
            raise ValueError('目标和能力均已满足且无欠交付；请核对是否确实需要继续。')
        evidence = _evidence(evidence)
        with self._write():
            job = self._continuity_defaults(self.get_job(job_id))
            supervision_revision = self._verify_supervisor_guard(job, job_id, attempt, supervisor_guard)
            if supervisor_guard is not None and job.get('version') != expected_version:
                raise WorkspaceConflict('监督评估的任务版本已变，请重新核对。')
            if _intent_version(job) != expected_intent_version:
                raise WorkspaceConflict('任务或当前意图版本已变化，请重新读取后验收。')
            revision = job.get('completion_revision', 0)
            if type(revision) is not int or revision < 0:
                raise ValueError('回合验收版本无效，请先核对任务。')
            events = job.get('completion_events')
            event = events.get(str(attempt)) if isinstance(events, dict) else None
            if not isinstance(event, dict) or event.get('event_id') != f'agent-job:{job_id}:attempt:{attempt}':
                raise ValueError('没有该轮已确认结束的完成事件，请先核对执行记录。')
            if supervisor_guard is not None:
                # A mechanical condition never proves the overall business goal.
                artifacts = event.get('artifact_ids')
                allowed_action = ((disposition == 'continue' and
                                   next_action == job['supervision']['continuation_instruction'] and bool(gap)) or
                                  (disposition == 'needs_decision' and
                                   next_action == '人工核对机械验收结果及整体业务目标。'))
                if (not allowed_action or goal_status != 'unknown' or capability_status != 'unknown' or
                        job.get('attempt') != attempt or job.get('status') != 'completed' or
                        job.get('worker_finished') is not True or event.get('run_status') != 'completed' or
                        event.get('intent_version') != expected_intent_version or
                        not isinstance(artifacts, list) or len(artifacts) != 1 or result_ref != artifacts[0] or
                        evidence['source'] != 'agent_jobs:artifact_contains'):
                    raise WorkspaceConflict('当前回合、授权下一步或观察证据不满足自动接续条件。')
                from supervisor import verify_artifact_assessment
                verify_artifact_assessment(self.app, job, event, evidence, disposition)
            if disposition == 'verified_complete' and event.get('run_status') != 'completed':
                raise ValueError('只有执行成功结束的轮次才能登记为该轮验收完成。')
            dispatch = event.get('dispatch')
            values = {'disposition':disposition, 'intent_version':expected_intent_version,
                      'goal_status':goal_status, 'capability_status':capability_status,
                      'result_ref':result_ref, 'gap':gap, 'next_action':next_action, 'evidence':evidence}
            if supervisor_guard is not None:
                values['supervision_revision'] = supervision_revision
            previous = event.get('assessment')
            same = isinstance(previous, dict) and all(previous.get(key) == value for key,value in values.items())
            # A replay can return an already persisted receipt even when the
            # task version moved. It must never initiate a new dispatch from
            # an old version when no request was previously recorded.
            if same and dispatch is not None:
                return next(item for item in self.completion_view(job) if item['attempt'] == attempt)
            if type(job.get('version')) is not int or job['version'] != expected_version:
                raise WorkspaceConflict('任务或当前意图版本已变化，请重新读取后验收。')
            if dispatch is not None and (not isinstance(dispatch, dict) or dispatch.get('state') not in ('completed', 'failed')):
                raise WorkspaceConflict('该轮接续正在处理或结果不明，请先对账，不能覆盖验收。')
            if same and previous.get('task_version_at_review') == job['version']:
                return copy.deepcopy(event)
            if isinstance(previous, dict):
                old = copy.deepcopy(previous)
                old.update(status='superseded', superseded_at=stamp())
                event.setdefault('assessment_history', []).append(old)
            if isinstance(event.get('dispatch_blocked'), dict):
                old_block = copy.deepcopy(event.pop('dispatch_blocked'))
                old_block['superseded_at'] = stamp()
                event.setdefault('dispatch_block_history', []).append(old_block)
            # _save increments the job version once in this same transaction.
            # Dispatch must compare against this exact review version; reading
            # a newer version is not permission to apply an old next action.
            event['assessment'] = {**values, 'task_next_action_at_review':job.get('next_action',''),
                                   'reviewed_at':stamp(), 'task_version_at_review':job['version']+1}
            job['completion_revision'] = revision + 1
            self._event(job, 'completion_assessed', '已按当前任务意图登记本轮验收与下一动作。')
            if supervisor_guard is not None:
                self._verify_supervisor_guard(job, job_id, attempt, supervisor_guard)
                verify_artifact_assessment(self.app, job, event, evidence, disposition)
            self._save(job)
            return copy.deepcopy(event)
