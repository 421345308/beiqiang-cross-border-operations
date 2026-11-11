"""Recoverable, explicitly scoped supervision of existing AgentJobs.

The two SQLite tables here contain only lease/heartbeat metadata.  Task intent,
completion assessments, blockers and dispatch receipts remain on AgentJobs.
Nothing in this module sends customer messages or starts a service by itself.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone

from codex_backend import CodexBackend
from workspaces import WorkspaceConflict

POLICY = 'mail_draft_read_only_v1'
EVIDENCE_SOURCE = 'agent_jobs:artifact_contains'
DECISION_ACTION = '人工核对机械验收结果及整体业务目标。'
TERMINAL = {'completed', 'failed', 'needs_input'}
BUSINESS_CASE_FIELDS = frozenset({'business_outcome', 'current_bottleneck', 'intended_change',
                                  'stop_condition', 'evidence_source'})
PREREQUISITE_STATES = frozenset({'ready', 'waiting_asset', 'waiting_review', 'unknown'})
VALUE_STATES = frozenset({'supported', 'none', 'unknown'})


def _stamp(value=None):
    return datetime.fromtimestamp(time.time() if value is None else value, timezone.utc).isoformat()


def _event_id(job_id, attempt):
    if (not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', job_id)
            or type(attempt) is not int or attempt < 1):
        raise ValueError('任务或轮次身份无效。')
    return f'agent-job:{job_id}:attempt:{attempt}'


def verify_guard(db, job_id, attempt, guard):
    """Fence an actual task write on its own SQLite connection/transaction."""
    event_id = _event_id(job_id, attempt)
    if not db.in_transaction:
        raise RuntimeError('监督租约必须在任务写事务内校验。')
    if (not isinstance(guard, dict) or set(guard) != {'owner_id', 'fence'}
            or not isinstance(guard['owner_id'], str)
            or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,200}', guard['owner_id'])
            or type(guard['fence']) is not int or guard['fence'] < 1):
        raise WorkspaceConflict('监督租约身份无效，停止当前写入。')
    try:
        row = db.execute('SELECT owner_id,fence,expires_at,heartbeat_at FROM supervisor_leases WHERE job_id=? AND event_id=?',
                         (job_id, event_id)).fetchone()
    except sqlite3.Error:
        raise WorkspaceConflict('监督租约不可读取，停止当前写入。') from None
    now = time.time()
    if (not row or row[0] != guard['owner_id'] or type(row[1]) is not int or row[1] != guard['fence']
            or not isinstance(row[2], (int, float)) or not math.isfinite(row[2])
            or not isinstance(row[3], (int, float)) or not math.isfinite(row[3])
            or not math.isfinite(now) or not row[3] <= now < row[2]):
        raise WorkspaceConflict('监督租约已失效或心跳不可确认，停止当前写入。')
    return True


def _criteria(job):
    config = job.get('supervision')
    if not isinstance(config, dict) or config.get('enabled') is not True:
        raise WorkspaceConflict('任务未明确纳管或监督已关闭。')
    rule = config.get('acceptance_criteria')
    if (config.get('policy') != POLICY or not isinstance(rule, dict)
            or set(rule) != {'kind', 'text'} or rule.get('kind') != 'artifact_contains'
            or not isinstance(rule.get('text'), str) or not rule['text'].strip() or len(rule['text']) > 500
            or not isinstance(config.get('continuation_instruction'), str)
            or not config['continuation_instruction'].strip() or len(config['continuation_instruction']) > 4000
            or not isinstance(config.get('authorization_ref'), str)
            or not config['authorization_ref'].strip() or len(config['authorization_ref']) > 1000
            or type(config.get('max_auto_continuations')) is not int or config['max_auto_continuations'] != 1
            or not isinstance(config.get('business_case'), dict)
            or set(config['business_case']) != BUSINESS_CASE_FIELDS
            or any(not isinstance(value, str) or not value.strip() or len(value) > 500
                   for value in config['business_case'].values())
            or not isinstance(config.get('prerequisite_state'), str)
            or config['prerequisite_state'] not in PREREQUISITE_STATES
            or not isinstance(config.get('value_state'), str) or config['value_state'] not in VALUE_STATES
            or type(job.get('supervision_revision')) is not int or job['supervision_revision'] < 1):
        raise WorkspaceConflict('监督范围、验收条件或授权来源不可读。')
    return config, rule


def _artifact_observation(app, job, event):
    _, rule = _criteria(job)
    if not isinstance(event, dict) or event.get('run_status') != 'completed':
        raise WorkspaceConflict('本轮没有确认成功结束，无法机械核对成果。')
    ids = event.get('artifact_ids')
    if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str) or not ids[0]:
        raise WorkspaceConflict('本轮没有唯一可核对的关联成果，请人工核对。')
    try:
        artifacts = app.business.list_artifacts(job['object_id'])
        matches = [a for a in artifacts if isinstance(a, dict) and a.get('id') == ids[0]
                   and a.get('object_id') == job['object_id']]
        if len(matches) != 1 or not isinstance(matches[0].get('content'), str):
            raise ValueError()
        body = matches[0]['content']
        if len(body) > 200000:
            raise ValueError()
        return {'artifact_id': ids[0], 'sha256': hashlib.sha256(body.encode('utf8')).hexdigest(),
                'condition_met': rule['text'] in body}
    except Exception:
        raise WorkspaceConflict('本轮关联成果不可读取或身份不唯一，请人工核对。') from None


def verify_artifact_assessment(app, job, event, evidence, disposition):
    """Re-read and compare the artifact while the guarded task transaction is held.

    SQLite and app.lock do not lock an independent editor of the artifact file.
    This comparison therefore cannot guarantee cross-file atomicity.
    """
    if not app.db.in_transaction:
        raise RuntimeError('成果观察必须在任务写事务内复核。')
    if not isinstance(evidence, dict) or evidence.get('source') != EVIDENCE_SOURCE:
        raise WorkspaceConflict('监督验收缺少可核对的成果观察。')
    try:
        recorded = json.loads(evidence.get('detail', ''))
    except (TypeError, ValueError):
        raise WorkspaceConflict('监督验收的成果观察不可读。') from None
    actual = _artifact_observation(app, job, event)
    if (not isinstance(recorded, dict) or set(recorded) != {'artifact_id', 'sha256', 'condition_met'}
            or type(recorded['condition_met']) is not bool or recorded != actual):
        raise WorkspaceConflict('成果或验收条件已变化，保留旧观察，不自动刷新重试。')
    expected = 'needs_decision' if actual['condition_met'] else 'continue'
    if disposition != expected:
        raise WorkspaceConflict('验收结论与机械条件观察不一致。')
    return actual


class Supervisor:
    def __init__(self, jobs, owner_id=None, lease_seconds=30):
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 600:
            raise ValueError('监督租约时长无效。')
        self.jobs, self.app = jobs, jobs.app
        self.owner_id = owner_id or uuid.uuid4().hex
        if not isinstance(self.owner_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,200}', self.owner_id):
            raise ValueError('监督实例身份无效。')
        self.lease_seconds = lease_seconds
        self._running = False
        self._last_scan = None
        now = time.time()
        with self.jobs._write():
            self.app.db.execute('CREATE TABLE IF NOT EXISTS supervisor_leases (job_id TEXT NOT NULL,event_id TEXT NOT NULL,owner_id TEXT NOT NULL,fence INTEGER NOT NULL,expires_at REAL NOT NULL,heartbeat_at REAL NOT NULL,PRIMARY KEY(job_id,event_id))')
            self.app.db.execute('CREATE TABLE IF NOT EXISTS supervisor_heartbeats (instance_id TEXT PRIMARY KEY,started_at REAL NOT NULL,heartbeat_at REAL NOT NULL)')
            try:
                self.app.db.execute('INSERT INTO supervisor_heartbeats VALUES (?,?,?)', (self.owner_id, now, now))
            except sqlite3.IntegrityError:
                raise WorkspaceConflict('监督实例身份已存在，请使用新的实例身份。') from None

    def configure(self, job_id, *, expected_version, acceptance_criteria, continuation_instruction, authorization_ref,
                  business_case, prerequisite_state, value_state):
        if (not isinstance(acceptance_criteria, dict) or set(acceptance_criteria) != {'kind','text'}
                or acceptance_criteria.get('kind') != 'artifact_contains'
                or not isinstance(acceptance_criteria.get('text'), str) or not acceptance_criteria['text'].strip()
                or len(acceptance_criteria['text']) > 500
                or not isinstance(continuation_instruction, str) or not continuation_instruction.strip()
                or len(continuation_instruction) > 4000 or not isinstance(authorization_ref, str)
                or not authorization_ref.strip() or len(authorization_ref) > 1000
                or not isinstance(business_case, dict) or set(business_case) != BUSINESS_CASE_FIELDS
                or any(not isinstance(value, str) or not value.strip() or len(value) > 500
                       for value in business_case.values())
                or not isinstance(prerequisite_state, str) or prerequisite_state not in PREREQUISITE_STATES
                or not isinstance(value_state, str) or value_state not in VALUE_STATES):
            raise ValueError('请提供验收条件、明确授权、完整经营意图和有效的前置条件及价值状态。')
        desired = {'enabled':True, 'policy':POLICY,
                   'acceptance_criteria':{'kind':'artifact_contains','text':acceptance_criteria['text']},
                   'continuation_instruction':continuation_instruction.strip(),
                   'authorization_ref':authorization_ref.strip(), 'max_auto_continuations':1,
                   'business_case':{key:value.strip() for key,value in business_case.items()},
                   'prerequisite_state':prerequisite_state, 'value_state':value_state}
        with self.jobs._write():
            job = self.jobs._continuity_defaults(self.jobs.get_job(job_id))
            if type(expected_version) is not int or expected_version != job['version']:
                raise WorkspaceConflict('任务版本已变化，请重新读取后纳管。')
            if job.get('status') in ('queued', 'running') and job.get('result_commit'):
                raise WorkspaceConflict('本轮结果正在保存，请先重新读取实际结果再调整监督配置。')
            revision = job.get('supervision_revision', 0)
            if type(revision) is not int or revision < 0:
                raise WorkspaceConflict('监督配置版本不可读。')
            existing = job.get('supervision')
            if isinstance(existing, dict) and all(existing.get(k) == v for k, v in desired.items()):
                return copy.deepcopy(job)
            job['supervision'] = {**desired,'configured_at':_stamp()}
            job['supervision_revision'] = revision + 1
            self.jobs._event(job, 'supervision_configured', '已显式登记监督范围与机械验收条件；不代表目标已完成。')
            job['events'][-1]['supervision_revision'] = job['supervision_revision']
            self.jobs._save(job)
            return copy.deepcopy(job)

    def disable(self, job_id, *, expected_version):
        with self.jobs._write():
            job = self.jobs._continuity_defaults(self.jobs.get_job(job_id))
            if type(expected_version) is not int or expected_version != job['version']:
                raise WorkspaceConflict('任务版本已变化，请重新读取后关闭监督。')
            if job.get('status') in ('queued', 'running') and job.get('result_commit'):
                raise WorkspaceConflict('本轮结果正在保存，请先重新读取实际结果再调整监督配置。')
            config = job.get('supervision')
            revision = job.get('supervision_revision', 0)
            if not isinstance(config, dict) or type(revision) is not int or revision < 1:
                raise ValueError('任务尚未明确纳管。')
            if config.get('enabled') is False:
                return copy.deepcopy(job)
            job['supervision'] = {**config, 'enabled':False, 'configured_at':_stamp()}
            job['supervision_revision'] = revision + 1
            self.jobs._event(job, 'supervision_disabled', '已关闭后续监督领取，不中断正在执行的工作。')
            job['events'][-1]['supervision_revision'] = job['supervision_revision']
            self.jobs._save(job)
            return copy.deepcopy(job)

    def heartbeat(self):
        now = time.time()
        with self.jobs._write():
            cursor = self.app.db.execute('UPDATE supervisor_heartbeats SET heartbeat_at=? WHERE instance_id=?',
                                         (now,self.owner_id))
            if cursor.rowcount != 1:
                raise WorkspaceConflict('监督实例心跳记录不可用。')
        return {'instance_id':self.owner_id,'heartbeat_at':_stamp(now)}

    def claim(self, job_id, attempt):
        event_id = _event_id(job_id, attempt)
        with self.jobs._write():
            now = time.time()
            job = self.jobs.get_job(job_id)
            _criteria(job)
            if job.get('attempt') != attempt or job.get('worker_finished') is not True or job.get('status') not in TERMINAL:
                raise WorkspaceConflict('仅可监督已确认结束的当前轮次。')
            row = self.app.db.execute('SELECT owner_id,fence,expires_at,heartbeat_at FROM supervisor_leases WHERE job_id=? AND event_id=?',
                                      (job_id,event_id)).fetchone()
            if row:
                if type(row[1]) is not int or row[1] < 1 or not isinstance(row[2], (int,float)) or not math.isfinite(row[2]):
                    raise WorkspaceConflict('监督租约记录不可读。')
                if row[2] > now:
                    if row[0] != self.owner_id:
                        return None
                    return {'guard':{'owner_id':self.owner_id,'fence':row[1]},'event_id':event_id,'expires_at':row[2]}
                fence = row[1] + 1
                self.app.db.execute('UPDATE supervisor_leases SET owner_id=?,fence=?,expires_at=?,heartbeat_at=? WHERE job_id=? AND event_id=?',
                                    (self.owner_id,fence,now+self.lease_seconds,now,job_id,event_id))
            else:
                fence = 1
                self.app.db.execute('INSERT INTO supervisor_leases VALUES (?,?,?,?,?,?)',
                                    (job_id,event_id,self.owner_id,fence,now+self.lease_seconds,now))
            return {'guard':{'owner_id':self.owner_id,'fence':fence},'event_id':event_id,'expires_at':now+self.lease_seconds}

    def renew(self, job_id, attempt, guard):
        with self.jobs._write():
            try:
                verify_guard(self.app.db,job_id,attempt,guard)
                job = self.jobs.get_job(job_id)
                _criteria(job)
                if job.get('attempt') != attempt:
                    return False
                now = time.time()
                self.app.db.execute('UPDATE supervisor_leases SET expires_at=?,heartbeat_at=? WHERE job_id=? AND event_id=? AND owner_id=? AND fence=?',
                                    (now+self.lease_seconds,now,job_id,_event_id(job_id,attempt),guard['owner_id'],guard['fence']))
                return True
            except WorkspaceConflict:
                return False

    def _event(self, job_id, attempt, guard):
        """Read finished event and freeze the versions before any assessment."""
        with self.jobs._write():
            verify_guard(self.app.db,job_id,attempt,guard)
            job = self.jobs._continuity_defaults(self.jobs.get_job(job_id))
            config,_ = _criteria(job)
            if job.get('attempt') != attempt or job.get('worker_finished') is not True or job.get('status') not in TERMINAL:
                raise WorkspaceConflict('任务轮次或结束状态已变化。')
            events = job.get('completion_events', {})
            if not isinstance(events,dict):
                raise WorkspaceConflict('回合记录不可读。')
            event = events.get(str(attempt))
            changed = False
            if event is None:
                event = self.jobs._record_finished_attempt(job)
                changed = True
            if not isinstance(event,dict) or event.get('event_id') != _event_id(job_id,attempt):
                raise WorkspaceConflict('回合身份不可确认。')
            # An assessment-in-progress checkpoint is task metadata, not a new
            # queue. It survives an expired lease or crash and ensures a later
            # owner cannot silently adopt a newer human-edited task version.
            checkpoint = event.get('supervisor_checkpoint')
            conflict = event.get('supervisor_conflict')
            blocker = event.get('dispatch_blocked')
            assessment = event.get('assessment')
            revision = job['supervision_revision']
            conflict_current = isinstance(conflict,dict) and conflict.get('supervision_revision') == revision
            no_assessment = assessment is None and event.get('dispatch') is None
            if no_assessment and checkpoint is not None and not conflict_current:
                matches = (isinstance(checkpoint,dict) and type(checkpoint.get('task_version')) is int
                           and checkpoint['task_version'] == job['version']
                           and checkpoint.get('intent_version') == job['intent']['version']
                           and checkpoint.get('supervision_revision') == revision)
                # A fresh configuration after a recorded conflict is an
                # explicit new review; a concurrent config change before the
                # conflict was recorded is not.
                reviewed_again = isinstance(conflict,dict) and conflict.get('supervision_revision') != revision
                if not matches and not reviewed_again:
                    self._set_conflict(job,event,'监督评估期间任务、意图或授权已变化，请人工核对。')
                    changed = True
                    conflict_current = True
                elif not matches:
                    checkpoint = None
            if no_assessment and checkpoint is None and not conflict_current:
                allowed_blocker = (blocker is None or (isinstance(blocker,dict)
                    and blocker.get('source') == 'supervisor'
                    and not (blocker.get('requires_manual_reset') is True
                             and blocker.get('supervision_revision') == revision)))
                eligible = (allowed_blocker and job.get('status') == 'completed'
                    and job.get('mode') == 'mail_draft' and type(self.jobs.backend) is CodexBackend
                    and config['prerequisite_state'] == 'ready' and config['value_state'] == 'supported'
                    and not any(isinstance(row,dict) and isinstance(row.get('dispatch'),dict)
                        and row['dispatch'].get('supervision_revision') == revision for row in events.values()))
                if eligible:
                    try:
                        eligible = not self.jobs._pending_result_attempts(job)
                        self.jobs._require_resolved_followups(job)
                    except WorkspaceConflict:
                        eligible = False
                if eligible:
                    event['supervisor_checkpoint'] = {'task_version':job['version']+1,
                        'intent_version':job['intent']['version'],'supervision_revision':revision,
                        'observed_at':_stamp()}
                    job['completion_revision'] = job.get('completion_revision',0) + 1
                    changed = True
            if changed:
                verify_guard(self.app.db,job_id,attempt,guard)
                self.jobs._save(job)
            return copy.deepcopy(job),copy.deepcopy(event)

    def _set_conflict(self, job, event, reason):
        """Append a sticky conflict to a fresh job snapshot without replacing human data."""
        revision = job['supervision_revision']
        previous = event.get('supervisor_conflict')
        if isinstance(previous,dict) and previous.get('supervision_revision') != revision:
            event.setdefault('supervisor_conflict_history',[]).append(copy.deepcopy(previous))
        event['supervisor_conflict'] = {'reason':reason,'observed_at':_stamp(),
            'supervision_revision':revision,'task_version_at_detection':job['version']}
        blocker = event.get('dispatch_blocked')
        if blocker is None or (isinstance(blocker,dict) and blocker.get('source') == 'supervisor'):
            event['dispatch_blocked'] = {'source':'supervisor','reason':reason,'observed_at':_stamp(),
                'supervision_revision':revision,'requires_manual_reset':True}
        job['completion_revision'] = job.get('completion_revision',0) + 1
        self.jobs._event(job,'supervisor_blocked','监督评估或接续发生冲突；保留原任务待人工复核。')

    def _mark_conflict(self, job_id, attempt, guard, reason):
        """Latch a conflict against the latest snapshot, not an old job version."""
        with self.jobs._write():
            verify_guard(self.app.db,job_id,attempt,guard)
            job = self.jobs._continuity_defaults(self.jobs.get_job(job_id))
            _criteria(job)
            event = job.get('completion_events',{}).get(str(attempt))
            if not isinstance(event,dict) or event.get('event_id') != _event_id(job_id,attempt):
                raise WorkspaceConflict('回合身份不可确认，不能登记监督冲突。')
            self._set_conflict(job,event,reason)
            verify_guard(self.app.db,job_id,attempt,guard)
            self.jobs._save(job)

    def _block(self, job_id, attempt, guard, expected_version, reason, *, sticky=False):
        with self.jobs._write():
            verify_guard(self.app.db,job_id,attempt,guard)
            job = self.jobs.get_job(job_id)
            _criteria(job)
            if job.get('version') != expected_version or job.get('attempt') != attempt:
                raise WorkspaceConflict('任务已变化，不能写入过时阻塞。')
            event = job.get('completion_events', {}).get(str(attempt))
            if not isinstance(event,dict) or event.get('event_id') != _event_id(job_id,attempt):
                raise WorkspaceConflict('回合身份不可确认。')
            if event.get('dispatch') is not None:
                return
            previous = event.get('dispatch_blocked')
            if isinstance(previous,dict) and previous.get('source') != 'supervisor':
                return
            if (isinstance(previous,dict) and previous.get('reason') == reason and
                    previous.get('supervision_revision') == job['supervision_revision'] and
                    previous.get('requires_manual_reset') is sticky):
                return
            event['dispatch_blocked'] = {'source':'supervisor','reason':reason,'observed_at':_stamp(),
                'supervision_revision':job['supervision_revision'],'requires_manual_reset':sticky}
            checkpoint = event.get('supervisor_checkpoint')
            if (isinstance(checkpoint,dict) and checkpoint.get('task_version') == job['version']
                    and checkpoint.get('supervision_revision') == job['supervision_revision']):
                checkpoint['task_version'] = job['version'] + 1
            job['completion_revision'] = job.get('completion_revision',0) + 1
            self.jobs._event(job,'supervisor_blocked','监督推进受阻；已保留原任务待核对。')
            verify_guard(self.app.db,job_id,attempt,guard)
            self.jobs._save(job)

    def _process(self, job_id, attempt, guard):
        job,event = self._event(job_id,attempt,guard)
        config,_ = _criteria(job)
        revision = job['supervision_revision']
        blocker = event.get('dispatch_blocked')
        conflict = event.get('supervisor_conflict')
        if isinstance(conflict,dict) and conflict.get('supervision_revision') == revision:
            return 'blocked', '监督评估或接续发生冲突，须人工核对后重新纳管。'
        if (isinstance(blocker,dict) and blocker.get('source') != 'supervisor'):
            return 'pending', '该轮已有其他来源的阻塞，须先人工核对。'
        if (isinstance(blocker,dict) and blocker.get('requires_manual_reset') is True
                and blocker.get('supervision_revision') == revision):
            return 'blocked', '先前版本或成果冲突，须人工核对后重新纳管。'
        if event.get('dispatch') is not None:
            return 'pending', '该轮已有接续回执，先观察或对账，不重复领取。'
        if config['prerequisite_state'] != 'ready' or config['value_state'] != 'supported':
            reason = ('前置状态为 '+config['prerequisite_state']+'，价值状态为 '+config['value_state']+
                      '；须先补齐素材、完成审核或由人判断是否继续。')
            self._block(job_id,attempt,guard,job['version'],reason)
            return 'blocked',reason
        if job.get('mode') != 'mail_draft' or type(self.jobs.backend) is not CodexBackend:
            reason = '当前模式或执行器不在已验证的只读监督白名单。'
            self._block(job_id,attempt,guard,job['version'],reason)
            return 'blocked',reason
        try:
            if self.jobs._pending_result_attempts(job):
                raise WorkspaceConflict('存在结果不明的成果保存，须先对账。')
            self.jobs._require_resolved_followups(job)
        except WorkspaceConflict as error:
            reason = str(error)
            self._block(job_id,attempt,guard,job['version'],reason)
            return 'blocked',reason
        events = job.get('completion_events',{})
        if any(isinstance(row,dict) and isinstance(row.get('dispatch'),dict)
               and row['dispatch'].get('supervision_revision') == revision for row in events.values()):
            reason = '本次授权的自动接续次数已用完；请人工核对新成果。'
            self._block(job_id,attempt,guard,job['version'],reason)
            return 'blocked',reason
        assessment = event.get('assessment')
        if isinstance(assessment,dict):
            if assessment.get('supervision_revision') != revision:
                return 'pending','已有人工或其他版本的验收，请人工核对，不自动覆盖。'
            if assessment.get('disposition') == 'needs_decision':
                return 'pending','机械条件已满足；仍须人工判断整体目标与能力。'
            if (assessment.get('disposition') != 'continue' or
                    assessment.get('task_version_at_review') != job['version'] or
                    assessment.get('intent_version') != (job.get('intent') or {}).get('version') or
                    assessment.get('next_action') != config['continuation_instruction']):
                reason = '原监督验收与当前版本或授权不一致，请人工核对。'
                self._block(job_id,attempt,guard,job['version'],reason,sticky=True)
                return 'blocked',reason
        else:
            try:
                observation = _artifact_observation(self.app,job,event)
            except WorkspaceConflict as error:
                reason = str(error)
                self._block(job_id,attempt,guard,job['version'],reason)
                return 'blocked',reason
            disposition = 'needs_decision' if observation['condition_met'] else 'continue'
            evidence = {'source':EVIDENCE_SOURCE,'observed_at':_stamp(),
                        'detail':json.dumps(observation,ensure_ascii=False,sort_keys=True)}
            action = DECISION_ACTION if observation['condition_met'] else config['continuation_instruction']
            try:
                assessed = self.jobs.assess_completion(job_id,attempt,expected_version=job['version'],
                    expected_intent_version=(job.get('intent') or {}).get('version',0),
                    disposition=disposition,goal_status='unknown',capability_status='unknown',
                    result_ref=observation['artifact_id'],gap='机械条件已核对；整体目标与能力尚需判断。',
                    next_action=action,evidence=evidence,supervisor_guard=guard)
            except WorkspaceConflict:
                self._mark_conflict(job_id,attempt,guard,'成果或任务版本冲突，请人工核对，不自动重试。')
                return 'blocked','成果或任务版本冲突，请人工核对，不自动重试。'
            assessment = assessed['assessment']
            if disposition == 'needs_decision':
                return 'pending','机械条件已满足；仍须人工判断整体目标与能力。'
        request_id = 'supervisor-' + hashlib.sha256((_event_id(job_id,attempt)+':'+str(revision)).encode('utf8')).hexdigest()
        try:
            result = self.jobs.continue_followup(job_id,attempt,
                        expected_version=assessment['task_version_at_review'],request_id=request_id,supervisor_guard=guard)
        except WorkspaceConflict:
            self._mark_conflict(job_id,attempt,guard,'续派前任务、租约或成果已变化，请人工核对，不自动重试。')
            return 'blocked','续派前任务、租约或成果已变化，请人工核对，不自动重试。'
        state = (result.get('dispatch') or {}).get('state','unknown')
        return 'advanced' if state in ('accepted','starting','running','completed') else 'pending', '续派回执：'+state

    def scan_once(self):
        self.heartbeat()
        report = {'instance_id':self.owner_id,'observed_at':_stamp(),'events':[]}
        for job in self.jobs.list_jobs():
            config = job.get('supervision')
            if not isinstance(config,dict) or config.get('enabled') is not True:
                continue
            job_id,attempt = job.get('id'),job.get('attempt')
            if type(attempt) is not int or attempt < 1 or job.get('status') not in TERMINAL or job.get('worker_finished') is not True:
                continue
            try:
                lease = self.claim(job_id,attempt)
                if lease is None:
                    state,reason = 'pending','该轮监督由其他有效租约持有。'
                else:
                    state,reason = self._process(job_id,attempt,lease['guard'])
            except (WorkspaceConflict, ValueError, OSError, sqlite3.Error) as error:
                state,reason = 'blocked',str(error)[:1000]
            report['events'].append({'job_id':job_id,'event_id':_event_id(job_id,attempt),'state':state,'reason':reason})
        for key in ('advanced','pending','blocked'):
            report[key] = sum(item['state']==key for item in report['events'])
        self._last_scan = copy.deepcopy(report)
        return report

    def status(self):
        now=time.time()
        base={'instance_id':self.owner_id,'state':'unavailable','observed_at':_stamp(now),'heartbeat_at':None,
              'heartbeat_age_seconds':None,'lease_seconds':self.lease_seconds,'active_leases':None,'leases':None,
              'supervised_tasks':None,'pending':None,'blocked':None,'unknown':None,
              'planner':'not_connected','notification':'not_connected','scope':['mail_draft'],
              'scan_mode':'background' if self._running else 'caller_driven',
              'last_scan':copy.deepcopy(self._last_scan),'reason':''}
        try:
            with self.app.lock:
                hb=self.app.db.execute('SELECT heartbeat_at FROM supervisor_heartbeats WHERE instance_id=?',(self.owner_id,)).fetchone()
                rows=self.app.db.execute('SELECT job_id,event_id,owner_id,expires_at FROM supervisor_leases WHERE expires_at>?',(now,)).fetchall()
            jobs=self.jobs.list_jobs()
            if not hb or not isinstance(hb[0],(int,float)) or not math.isfinite(hb[0]) or hb[0]>now:
                raise ValueError('heartbeat')
            age=max(0,now-hb[0]); base.update(heartbeat_at=_stamp(hb[0]),heartbeat_age_seconds=age,
                active_leases=len(rows),leases=[{'job_id':r[0],'event_id':r[1],'owner_id':r[2],'expires_at':_stamp(r[3])} for r in rows])
            managed=[j for j in jobs if isinstance(j.get('supervision'),dict) and j['supervision'].get('enabled') is True]
            pending=blocked=unknown=0
            for job in managed:
                try:
                    config,_ = _criteria(job)
                    events=job.get('completion_events',{})
                    if not isinstance(events,dict):raise ValueError()
                    if self.jobs._pending_result_attempts(job):unknown+=1;continue
                    if config['prerequisite_state'] != 'ready' or config['value_state'] != 'supported':
                        blocked+=1;continue
                    current=events.get(str(job.get('attempt')))
                    if not isinstance(current,dict):pending+=1;continue
                    receipt=current.get('dispatch')
                    if isinstance(receipt,dict) and receipt.get('state')=='unknown':unknown+=1
                    elif isinstance(current.get('dispatch_blocked'),dict):blocked+=1
                    elif not isinstance(current.get('assessment'),dict) or current['assessment'].get('disposition')=='needs_decision':pending+=1
                except (ValueError,WorkspaceConflict):unknown+=1
            base.update(supervised_tasks=len(managed),pending=pending,blocked=blocked,unknown=unknown,
                        state=('stale' if age>self.lease_seconds*2 else 'running' if self._running else 'idle'))
            if self._running and isinstance(self._last_scan,dict) and self._last_scan.get('state') == 'unavailable':
                base.update(state='unavailable',reason='最近一次监督扫描失败，请核对运行状态。')
        except (sqlite3.Error,ValueError,OverflowError,OSError):
            base['reason']='监督心跳或任务状态不可读取。'
        return base

    def run_forever(self, stop_event, interval_seconds=10):
        if not isinstance(interval_seconds,(int,float)) or isinstance(interval_seconds,bool) or not 1<=interval_seconds<=600:
            raise ValueError('监督扫描间隔无效。')
        if self._running:
            raise RuntimeError('监督循环已运行。')
        self._running=True
        try:
            while not stop_event.is_set():
                try:self.scan_once()
                except Exception:self._last_scan={'instance_id':self.owner_id,'observed_at':_stamp(),
                                                   'state':'unavailable','reason':'监督扫描失败，请核对运行状态。'}
                if stop_event.wait(interval_seconds):break
        finally:self._running=False
