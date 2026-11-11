"""Idempotent, same-job continuation for the existing local AgentJobs runtime."""
from __future__ import annotations

import copy
import hashlib
import os
import re
import threading
from datetime import datetime, timezone

from codex_backend import CodexBackend
from workspaces import WorkspaceConflict


def stamp():
    return datetime.now(timezone.utc).isoformat()


def _request_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,199}', value):
        raise ValueError('请提供可复用的派工请求编号。')
    return value


def _event_for(job, attempt):
    events = job.get('completion_events')
    event = events.get(str(attempt)) if isinstance(events, dict) else None
    if (type(attempt) is not int or attempt < 1 or not isinstance(event, dict) or
            event.get('event_id') != f"agent-job:{job.get('id')}:attempt:{attempt}"):
        raise ValueError('没有该轮已确认结束的完成事件，请先核对。')
    return event


class CompletionDispatch:
    @staticmethod
    def _confirmed_result_outcome(job, attempt):
        """Return only an explicitly reconciled save outcome with evidence."""
        records = job.get('result_reconciliations', [])
        if not isinstance(records, list):
            return None
        for record in reversed(records):
            if (isinstance(record, dict) and type(record.get('attempt')) is int and record['attempt'] == attempt
                    and record.get('outcome') in ('completed', 'failed')
                    and isinstance(record.get('evidence'), str) and record['evidence'].strip()):
                return record['outcome']
        return None

    @staticmethod
    def _held_unknown_attempts(job):
        """Find retained uncertain saves, including pre-outcome legacy records."""
        index = job.get('held_results', {})
        if not isinstance(index, dict):
            raise WorkspaceConflict('待复核成果索引不可读，请先核对，不能另建工作。')
        held = list(index.values())
        if job.get('held_result') is not None:
            held.append(job['held_result'])
        attempts = set()
        for item in held:
            if not isinstance(item, dict):
                raise WorkspaceConflict('待复核成果记录不可读，请先核对，不能另建工作。')
            if item.get('reason') == 'result_outcome_unknown':
                if type(item.get('attempt')) is not int or item['attempt'] < 1:
                    raise WorkspaceConflict('未知成果轮次不可读，请先核对，不能另建工作。')
                attempts.add(item['attempt'])
        return attempts

    @classmethod
    def _pending_result_attempts(cls, job):
        attempts = {attempt for attempt in cls._held_unknown_attempts(job)
                    if cls._confirmed_result_outcome(job, attempt) is None}
        commit = job.get('result_commit')
        if commit is not None:
            if not isinstance(commit, dict) or type(commit.get('attempt')) is not int or commit['attempt'] < 1:
                raise WorkspaceConflict('成果保存记录不可读，请先核对，不能另建工作。')
            # A live or stale marker must be resolved even if an older receipt
            # appears to settle the same attempt.
            attempts.add(commit['attempt'])
        return attempts

    @classmethod
    def _result_save_observation(cls, job, attempt):
        commit = job.get('result_commit')
        if commit is not None:
            if not isinstance(commit, dict) or commit.get('attempt') != attempt:
                return 'unknown'
            if commit.get('state') == 'saving':
                return 'saving'
            return 'unknown'
        outcome = cls._confirmed_result_outcome(job, attempt)
        if outcome is not None:
            return outcome
        try:
            return 'unknown' if attempt in cls._held_unknown_attempts(job) else None
        except WorkspaceConflict:
            return 'unknown'

    @staticmethod
    def _require_resolved_followups(job):
        events = job.get('completion_events', {})
        if not isinstance(events, dict):
            raise WorkspaceConflict('回合或派工记录不可读，请先核对，不能继续。')
        for event in events.values():
            if not isinstance(event, dict):
                raise WorkspaceConflict('回合或派工记录不可读，请先核对，不能继续。')
            receipt = event.get('dispatch')
            if receipt is not None and (not isinstance(receipt, dict) or receipt.get('state') not in ('completed','failed')):
                raise WorkspaceConflict('存在尚未对账的接续请求；请先核对原请求，不能另开或重发。')

    def assess_and_continue(self, job_id, attempt, *, expected_version, expected_intent_version,
                            disposition, goal_status, capability_status, result_ref, gap, next_action, evidence,
                            supervisor_guard=None):
        """Persist the review, then advance a supported read-only continuation."""
        event = self.assess_completion(job_id, attempt, expected_version=expected_version,
            expected_intent_version=expected_intent_version, disposition=disposition,
            goal_status=goal_status, capability_status=capability_status, result_ref=result_ref,
            gap=gap, next_action=next_action, evidence=evidence, supervisor_guard=supervisor_guard)
        if disposition != 'continue':
            return event
        current = self.get_job(job_id)
        if current.get('mode') != 'mail_draft':
            return event
        request_id = 'followup-' + hashlib.sha256(event['event_id'].encode('utf8')).hexdigest()
        try:
            reviewed_version = event.get('assessment', {}).get('task_version_at_review')
            return self.continue_followup(job_id, attempt, expected_version=reviewed_version, request_id=request_id,
                                          supervisor_guard=supervisor_guard)
        except (ValueError, WorkspaceConflict) as error:
            # No claim was accepted by this call. Preserve a visible, actionable
            # pre-dispatch blocker; do not represent it as an external receipt.
            with self._write():
                latest = self.get_job(job_id)
                revision = self._verify_supervisor_guard(latest, job_id, attempt, supervisor_guard)
                saved = _event_for(latest, attempt)
                if supervisor_guard is not None and (
                        latest.get('version') != reviewed_version or
                        not isinstance(saved.get('assessment'), dict) or
                        saved['assessment'].get('supervision_revision') != revision):
                    raise WorkspaceConflict('自动验收后的任务或监督配置已变，不记录旧阻塞。')
                if saved.get('dispatch') is None and saved.get('assessment') == event.get('assessment'):
                    saved['dispatch_blocked'] = {'request_id':request_id, 'reason':str(error)[:1000],
                                                 'observed_at':stamp(), 'source':'agent_jobs'}
                    latest['completion_revision'] = latest.get('completion_revision', 0) + 1
                    self._event(latest, 'followup_blocked', '接续尚未领取，请处理已记录的阻塞。')
                    if supervisor_guard is not None:
                        self._verify_supervisor_guard(latest, job_id, attempt, supervisor_guard)
                    self._save(latest)
                return copy.deepcopy(saved)

    def _sync_followup_receipts(self, job):
        """Project observed local execution into its persisted request receipt."""
        events = job.get('completion_events')
        if not isinstance(events, dict):
            return False
        changed = False
        for event in events.values():
            receipt = event.get('dispatch') if isinstance(event, dict) else None
            if not isinstance(receipt, dict):
                continue
            target = receipt.get('target_attempt')
            if type(target) is not int:
                continue
            plan = job.get('attempt_plan') if isinstance(job.get('attempt_plan'), dict) else {}
            bound = (plan.get('attempt') == target and plan.get('followup_request_id') == receipt.get('request_id')
                     and plan.get('followup_source_attempt') == event.get('attempt'))
            observation = self._result_save_observation(job, target) if bound else None
            state = None
            if job.get('attempt') == target:
                if not bound and receipt.get('state') in ('accepted','starting','running'):
                    state = 'unknown'
                elif bound and (observation == 'unknown' or (observation == 'saving' and
                                      (job.get('status') != 'running' or job.get('worker_finished') is True))):
                    state = 'unknown'
                elif bound and job.get('status') == 'running':
                    state = 'running' if type(job.get('process_id')) is int and job['process_id'] > 0 else 'starting'
                elif bound and job.get('worker_finished') is True and job.get('status') in ('completed', 'failed', 'needs_input', 'cancelled'):
                    state = observation if observation in ('completed', 'failed') else 'completed' if job['status'] == 'completed' else 'failed'
            elif (type(job.get('attempt')) is int and job['attempt'] < target and job.get('worker_finished') is True and
                  job.get('status') in ('failed', 'needs_input', 'cancelled')):
                state = 'unknown'
            if state and receipt.get('state') != state:
                receipt.update(state=state, updated_at=stamp(), receipt_source='agent_jobs')
                changed = True
            if state == 'running' and receipt.get('observed_process_id') != job.get('process_id'):
                receipt['observed_process_id'] = job['process_id']
                receipt.setdefault('started_at', stamp())
                changed = True
            if (state == 'running' and job.get('session_id') and
                    receipt.get('observed_session_id') != job['session_id']):
                receipt['observed_session_id'] = job['session_id']
                changed = True
        if changed:
            job['completion_revision'] = job.get('completion_revision', 0) + 1
        return changed

    def continue_followup(self, job_id, attempt, *, expected_version, request_id, supervisor_guard=None):
        """Claim one safe continuation; a repeated request never launches again."""
        request_id = _request_id(request_id)
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError('请提供实际读取的任务版本。')
        with self.lock:
            with self._write():
                job = self._continuity_defaults(self.get_job(job_id))
                revision = self._verify_supervisor_guard(job, job_id, attempt, supervisor_guard)
                event = _event_for(job, attempt)
                if supervisor_guard is not None:
                    reviewed = event.get('assessment')
                    if (not isinstance(reviewed, dict) or reviewed.get('supervision_revision') != revision or
                            reviewed.get('disposition') != 'continue' or reviewed.get('goal_status') != 'unknown' or
                            reviewed.get('capability_status') != 'unknown' or
                            reviewed.get('next_action') != job['supervision']['continuation_instruction']):
                        raise WorkspaceConflict('当前监督配置没有匹配的自动验收记录。')
                existing = event.get('dispatch')
                if existing is not None:
                    if isinstance(existing, dict) and existing.get('request_id') == request_id:
                        # Older versions could have stored a false 'failed'
                        # receipt while the target save was still unknown.
                        # Re-observe the existing request; never launch again.
                        if self._sync_followup_receipts(job):
                            if supervisor_guard is not None:
                                self._verify_supervisor_guard(job, job_id, attempt, supervisor_guard)
                            self._save(job)
                        return copy.deepcopy(_event_for(job, attempt))
                    raise WorkspaceConflict('该轮已有接续请求；请先按原请求编号对账，不能重复派工。')
                self._require_resolved_followups(job)
                if job['version'] != expected_version:
                    raise WorkspaceConflict('任务版本已变化，请重新读取后安排接续。')
                assessment = event.get('assessment')
                if supervisor_guard is not None:
                    if any(isinstance(item, dict) and isinstance(item.get('dispatch'), dict) and
                           item['dispatch'].get('supervision_revision') == revision
                           for item in job.get('completion_events', {}).values()):
                        raise WorkspaceConflict('本次监督配置已有自动派工，停止重复派工。')
                    if (job.get('status') != 'completed' or event.get('run_status') != 'completed' or
                            event.get('intent_version') != job['intent']['version'] or
                            not isinstance(event.get('artifact_ids'), list) or
                            assessment.get('result_ref') not in event['artifact_ids']):
                        raise WorkspaceConflict('回合状态、意图或成果已变化，停止自动接续。')
                    from supervisor import verify_artifact_assessment
                    verify_artifact_assessment(self.app, job, event, assessment.get('evidence'), 'continue')
                if not isinstance(assessment, dict) or assessment.get('disposition') != 'continue':
                    raise ValueError('请先按当前目标登记需要继续的验收结论。')
                if assessment.get('task_version_at_review') != expected_version:
                    raise WorkspaceConflict('验收后任务安排已变化，请重新验收，不自动沿用旧下一动作。')
                if assessment.get('intent_version') != job['intent']['version']:
                    raise WorkspaceConflict('任务意图已变化，请重新验收后再接续。')
                if job.get('mode') != 'mail_draft':
                    raise ValueError('该任务不属于本轮支持的只读受控接续范围；请沿原入口显式处理。')
                if type(self.backend) is not CodexBackend:
                    raise ValueError('当前执行器的只读能力尚未验证；请沿原入口显式处理。')
                if (job.get('attempt') != attempt or job.get('status') in ('planned', 'queued', 'running') or
                        job.get('worker_finished') is not True or job_id in self.threads):
                    raise WorkspaceConflict('原轮次仍在收尾或已有新轮次，请先核对。')
                if job.get('result_commit'):
                    raise WorkspaceConflict('上一轮成果保存结果未核对；不能自动接续。')
                if job.get('process_id') and self._pid_alive(job['process_id']) is not False:
                    raise WorkspaceConflict('先前进程仍在运行或状态未知，请先核对。')
                self._check_parent_available(job)
                self._check_dependencies(job)
                self._check_object_available(job['object_id'], exclude=job_id)
                obj = self.app.business.get_object(job['object_id'])
                action = assessment.get('next_action')
                if not isinstance(action, str) or not action.strip() or len(action) > 4000:
                    raise ValueError('当前验收缺少可执行的下一动作。')
                action = action.strip()
                if job.get('next_action', '') != action:
                    previous = job.get('next_action')
                    job['next_action'] = action
                    job['adjustment_version'] = job.get('adjustment_version', 0) + 1
                    job.setdefault('adjustments', []).append({'at':stamp(), 'changes':{'next_action':{'before':previous,'after':action}},
                        'scheduling_effect':'display_only'})
                    job['adjustments'] = job['adjustments'][-200:]
                    self._event(job, 'planning_adjusted', '已按本轮验收结论登记下一动作，并在领取时固定。')
                    job['events'][-1]['adjustment_version'] = job['adjustment_version']
                session = job.get('session_id')
                job.update(status='queued', instruction=action, error=None, process_id=None,
                           owner_pid=os.getpid(), owner_id=self.owner_id, worker_finished=False,
                           continuation_mode='resume' if session else 'new_session')
                self._freeze_attempt_plan(job)
                job['attempt_plan'].update(followup_request_id=request_id, followup_source_attempt=attempt)
                if supervisor_guard is not None:
                    # The same transaction that claims this attempt fixes the
                    # business rationale; later supervision edits must not be
                    # mistaken for the rationale the worker actually received.
                    job['attempt_plan']['supervision_revision'] = revision
                    job['attempt_plan']['business_case'] = copy.deepcopy(job['supervision']['business_case'])
                now = stamp()
                event.pop('dispatch_blocked', None)
                event['dispatch'] = {'request_id':request_id, 'state':'accepted', 'target_job_id':job_id,
                    'target_attempt':attempt+1, 'target_session_id':session, 'prepared_at':now,
                    'updated_at':now, 'receipt_source':'agent_jobs', 'notification':'not_connected'}
                if supervisor_guard is not None:
                    event['dispatch']['supervision_revision'] = revision
                job['completion_revision'] = job.get('completion_revision', 0) + 1
                self._event(job, 'followup_accepted', '已在原任务记录接续请求；尚未据此认定执行器已启动。')
                if supervisor_guard is not None:
                    self._verify_supervisor_guard(job, job_id, attempt, supervisor_guard)
                    verify_artifact_assessment(self.app, job, event, assessment.get('evidence'), 'continue')
                self._save(job)
            worker = threading.Thread(target=self._work, args=(job_id, obj), daemon=True,
                                      name='business-agent-' + job_id[:8])
            self.threads[job_id] = worker
            try:
                worker.start()
            except Exception:
                # A lost/failed launch acknowledgement is never proof that no
                # worker started. Preserve the one request and reconcile it.
                with self._write():
                    current = self.get_job(job_id)
                    self._verify_supervisor_guard(current, job_id, attempt, supervisor_guard)
                    receipt = _event_for(current, attempt).get('dispatch')
                    if isinstance(receipt, dict) and receipt.get('request_id') == request_id and receipt.get('state') in ('accepted', 'starting'):
                        receipt.update(state='unknown', updated_at=stamp(),
                                       reason='线程启动回执不明，请核对本机任务和进程；不得自动重发。')
                        current['completion_revision'] = current.get('completion_revision', 0) + 1
                        self._event(current, 'followup_unknown', '接续启动结果不明，保留请求等待对账。')
                        if supervisor_guard is not None:
                            self._verify_supervisor_guard(current, job_id, attempt, supervisor_guard)
                        self._save(current)
            return copy.deepcopy(_event_for(self.get_job(job_id), attempt))

    def reconcile_followup(self, job_id, attempt, *, expected_version, request_id):
        """Read the original local receipt and observed attempt; never dispatch."""
        request_id = _request_id(request_id)
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError('请提供实际读取的任务版本。')
        with self._write():
            job = self._continuity_defaults(self.get_job(job_id))
            if job['version'] != expected_version:
                raise WorkspaceConflict('任务版本已变化，请重新读取后对账。')
            event = _event_for(job, attempt)
            receipt = event.get('dispatch')
            if not isinstance(receipt, dict) or receipt.get('request_id') != request_id:
                raise ValueError('请求编号与已记录的接续不匹配。')
            self._sync_followup_receipts(job)
            if receipt.get('state') in ('accepted', 'starting'):
                receipt['state'] = 'unknown'
                receipt['reason'] = '尚无可确认的执行器或完成回执；不得自动重发。'
            receipt.update(last_reconciled_at=stamp(), reconciliation_source='agent_jobs')
            job['completion_revision'] = job.get('completion_revision', 0) + 1
            self._event(job, 'followup_reconciled', '已核对原请求及本机执行记录；未知结果不会自动重发。')
            self._save(job)
            return copy.deepcopy(_event_for(job, attempt))
