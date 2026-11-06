"""Read persisted Gmail dispatch/job links; explicitly repair a reviewed link.

No service constructors, Gmail reads, dispatches, retries or job writes occur.
Legacy jobs have no event identity: matching object/mode is only a candidate,
never proof of origin. A manual link records that distinction in last_error,
retaining the original error as audit data without changing the event schema.

Future explicit provenance, if present, uses only this exact job field:
source_event = {"kind": "gmail_reply", "object_id": ..., "message_id": ...}.
Instruction text, timestamps, subjects and job order are never used to match.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json


REPAIRABLE = frozenset({'outcome_unknown', 'dispatched_unlinked', 'failed'})
SNAPSHOT_FIELDS = frozenset({'dispatch_state', 'job_id', 'updated_at'})


class ReconcileRejected(ValueError):
    pass


class ReconcileConflict(ReconcileRejected):
    """Refresh the persisted event; the reviewed snapshot is no longer current."""


class ReconcileOutcomeUnknown(RuntimeError):
    """Read back before any further action; never retry or dispatch implicitly."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _identity(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 1000 or '\x00' in value:
        raise ReconcileRejected(label + '无效')
    return value


def _audit(value):
    try:
        parsed = json.loads(value or 'null')
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) and parsed.get('kind') == 'manual_gmail_event_link' else None


class GmailEventReconcile:
    def __init__(self, app, *, clock=_now):
        self.app = app
        self.clock = clock

    def _schema(self):
        tables = {r[0] for r in self.app.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        columns = {r[1] for r in self.app.db.execute('PRAGMA table_info(gmail_reply_events)')} if 'gmail_reply_events' in tables else set()
        return tables, columns

    def _jobs(self, tables):
        jobs = {}
        if 'agent_jobs' not in tables:
            return jobs
        for job_id, raw in self.app.db.execute('SELECT id,data FROM agent_jobs'):
            try:
                job = json.loads(raw)
            except (TypeError, ValueError):
                job = None
            jobs[job_id] = job if isinstance(job, dict) and job.get('id') == job_id else None
        return jobs

    def _rows(self, object_id, columns):
        selected = ['object_id', 'message_id', 'dispatch_state'] + [name if name in columns else 'NULL AS ' + name for name in ('job_id', 'updated_at', 'last_error')]
        names = ['object_id', 'message_id', 'dispatch_state', 'job_id', 'updated_at', 'last_error']
        return [dict(zip(names, row)) for row in self.app.db.execute('SELECT ' + ','.join(selected) + ' FROM gmail_reply_events WHERE object_id=? ORDER BY message_id', (object_id,))]

    @staticmethod
    def _job_view(job_id, job, object_id, message_id=None):
        if job is None:
            return {'id': job_id, 'valid_record': False, 'origin': 'unknown', 'source_matches': None}
        source = job.get('source_event')
        if source is None:
            origin, matches = 'manual_review_required', None
        else:
            exact = isinstance(source, dict) and source.get('kind') == 'gmail_reply' and source.get('object_id') == object_id
            matches = bool(exact and message_id is not None and source.get('message_id') == message_id)
            origin = 'explicit_event' if exact else 'conflicting_event_source'
        return {'id': job_id, 'valid_record': True, 'object_id': job.get('object_id'),
                'mode': job.get('mode'), 'status': job.get('status'), 'updated_at': job.get('updated_at'),
                'object_matches': job.get('object_id') == object_id,
                'mode_matches': job.get('mode') == 'mail_draft',
                'origin': origin, 'source_matches': matches}

    def list_events(self, object_id):
        """Read-only report, even for legacy schemas; no automatic job matching."""
        _identity(object_id, '客户ID')
        with self.app.lock:
            tables, columns = self._schema()
            required = {'object_id', 'message_id', 'dispatch_state'}
            if not required.issubset(columns):
                return {'object_id': object_id, 'available': False, 'events': [], 'candidate_jobs': [],
                        'warning': '邮件事件表不存在或结构不完整；未创建或迁移任何表', 'automatic_replay': False}
            jobs = self._jobs(tables)
            rows = self._rows(object_id, columns)
            acknowledged = self.app.db.execute('SELECT message_id FROM gmail_acknowledged WHERE object_id=?', (object_id,)).fetchone() if 'gmail_acknowledged' in tables else None
            ack_known = 'gmail_acknowledged' in tables
            links = {}
            if 'job_id' in columns:
                for oid, mid, jid in self.app.db.execute("SELECT object_id,message_id,job_id FROM gmail_reply_events WHERE job_id IS NOT NULL AND job_id<>''"):
                    links.setdefault(jid, []).append({'object_id': oid, 'message_id': mid})
            events = []
            for row in rows:
                jid = row['job_id']
                job = jobs.get(jid)
                view = self._job_view(jid, job, object_id, row['message_id']) if jid else None
                audit = _audit(row['last_error'])
                if not jid:
                    relation = 'unlinked'
                elif jid not in jobs:
                    relation = 'job_missing'
                elif job is None:
                    relation = 'job_record_invalid'
                elif not view['object_matches']:
                    relation = 'object_mismatch'
                elif not view['mode_matches']:
                    relation = 'mode_mismatch'
                elif view['source_matches'] is False:
                    relation = 'event_source_mismatch'
                elif audit:
                    relation = 'manually_verified'
                elif view['source_matches']:
                    relation = 'explicit_event_link'
                else:
                    relation = 'object_only_manual_review_required'
                ack = bool(acknowledged and acknowledged[0] == row['message_id']) if ack_known else None
                events.append({**row, 'snapshot': {k: row[k] for k in SNAPSHOT_FIELDS},
                               'acknowledged': ack, 'job': view, 'relation': relation,
                               'duplicate_job_link': bool(jid and len(links.get(jid, [])) > 1),
                               'manual_link_audit': audit,
                               'manual_link_allowed': ack is False and 'agent_jobs' in tables
                               and {'job_id', 'updated_at', 'last_error'}.issubset(columns)
                               and row['dispatch_state'] in REPAIRABLE and not jid,
                               'automatic_replay': False})
            candidates = []
            for jid, job in jobs.items():
                if job and job.get('object_id') == object_id and job.get('mode') == 'mail_draft':
                    view = self._job_view(jid, job, object_id)
                    view.update(linked_events=links.get(jid, []), already_linked=bool(links.get(jid)),
                                automatic_match=False)
                    candidates.append(view)
            return {'object_id': object_id, 'available': True, 'events': events,
                    'candidate_jobs': candidates, 'acknowledgement_coverage_known': ack_known,
                    'origin_note': '无明确来源标识的历史Job须人工核对；同对象、时间相近或状态相同均不证明属于该邮件。',
                    'automatic_replay': False}

    def link_existing(self, object_id, message_id, job_id, snapshot, *, confirmed=False, manual_note=''):
        """Explicitly link a reviewed existing job; never create/restart/replay one.

        snapshot must be the exact dispatch_state/job_id/updated_at values read
        from list_events. Successful repairs become dispatched, with a durable
        manual audit and the original error retained. Even source-tagged jobs
        require this explicit human confirmation.
        """
        for value, label in ((object_id, '客户ID'), (message_id, '邮件ID'), (job_id, '任务ID')):
            _identity(value, label)
        if confirmed is not True:
            raise ReconcileRejected('须明确人工确认已有任务与该邮件的关系')
        if not isinstance(manual_note, str) or not manual_note.strip() or len(manual_note) > 4000 or '\x00' in manual_note:
            raise ReconcileRejected('请记录人工核对依据，最多4000字')
        if not isinstance(snapshot, dict) or set(snapshot) != SNAPSHOT_FIELDS:
            raise ReconcileRejected('须提供原dispatch_state、job_id及updated_at完整快照')
        if any(v is not None and not isinstance(v, str) for v in snapshot.values()):
            raise ReconcileRejected('事件快照格式无效')
        with self.app.lock:
            db = self.app.db
            if db.in_transaction:
                raise ReconcileRejected('人工关联不能嵌入已有事务')
            db.execute('BEGIN IMMEDIATE')
            try:
                tables, columns = self._schema()
                if not {'gmail_reply_events', 'agent_jobs', 'gmail_acknowledged'}.issubset(tables) or not {'object_id', 'message_id', 'dispatch_state', 'job_id', 'updated_at', 'last_error'}.issubset(columns):
                    raise ReconcileRejected('持久化事件、任务或已确认状态不完整，不能安全关联')
                row = db.execute('SELECT dispatch_state,job_id,updated_at,last_error FROM gmail_reply_events WHERE object_id=? AND message_id=?', (object_id, message_id)).fetchone()
                if row is None:
                    raise ReconcileConflict('原邮件事件不存在，请重新读取')
                state, old_job, updated_at, old_error = row
                if any(snapshot[k] != v for k, v in zip(('dispatch_state', 'job_id', 'updated_at'), row[:3])):
                    raise ReconcileConflict('邮件事件已变化，请重新核对快照')
                if state not in REPAIRABLE or old_job:
                    raise ReconcileRejected('仅允许未关联任务的未知结果、未回传任务ID或旧失败事件；活动及已关联事件不能改配')
                if db.execute('SELECT 1 FROM gmail_acknowledged WHERE object_id=? AND message_id=?', (object_id, message_id)).fetchone():
                    raise ReconcileRejected('该邮件已确认处理，不能再关联')
                job_row = db.execute('SELECT data FROM agent_jobs WHERE id=?', (job_id,)).fetchone()
                if not job_row:
                    raise ReconcileRejected('已有任务不存在')
                try:
                    job = json.loads(job_row[0])
                except (TypeError, ValueError):
                    job = None
                if not isinstance(job, dict) or job.get('id') != job_id:
                    raise ReconcileRejected('已有任务记录无效')
                if job.get('object_id') != object_id or job.get('mode') != 'mail_draft':
                    raise ReconcileRejected('只可关联同客户的mail_draft任务')
                view = self._job_view(job_id, job, object_id, message_id)
                if job.get('source_event') is not None and view['source_matches'] is not True:
                    raise ReconcileRejected('任务的明确事件来源与该邮件不一致')
                if db.execute('SELECT 1 FROM gmail_reply_events WHERE job_id=?', (job_id,)).fetchone():
                    raise ReconcileRejected('该任务已被其他邮件事件关联')
                at = _identity(self.clock(), '关联时间')
                audit = {'kind': 'manual_gmail_event_link', 'confirmed_at': at, 'note': manual_note.strip(),
                         'origin': 'explicit_event' if view['source_matches'] else 'manual_review_required',
                         'previous_snapshot': dict(snapshot), 'previous_error': old_error}
                changed = db.execute("UPDATE gmail_reply_events SET dispatch_state='dispatched',job_id=?,updated_at=?,last_error=? WHERE object_id=? AND message_id=? AND dispatch_state IS ? AND job_id IS ? AND updated_at IS ? AND NOT EXISTS (SELECT 1 FROM gmail_acknowledged WHERE object_id=? AND message_id=?)",
                                     (job_id, at, json.dumps(audit, ensure_ascii=False), object_id, message_id, state, old_job, updated_at, object_id, message_id))
                if changed.rowcount != 1:
                    raise ReconcileConflict('邮件事件已变化，关联未完成')
                result = {'object_id': object_id, 'message_id': message_id, 'dispatch_state': 'dispatched',
                          'job_id': job_id, 'updated_at': at, 'manual_link_audit': audit,
                          'snapshot': {'dispatch_state': 'dispatched', 'job_id': job_id, 'updated_at': at},
                          'job_status': job.get('status'), 'automatic_replay': False}
                try:
                    db.commit()
                except BaseException as exc:
                    if not db.in_transaction:
                        raise ReconcileOutcomeUnknown('关联提交结果未知；须只读对账，不得自动重播或重试') from exc
                    raise
                return result
            except BaseException:
                if db.in_transaction:
                    db.rollback()
                raise
