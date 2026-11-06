"""Cross-process metadata for a bounded correspondence observation, not mail storage.

Only a stable Gmail OAuth mailbox historyId surrounding a complete query may
advance the successful watermark. Timestamps, message dates/IDs and IMAP UIDs
are not substitute watermarks. Pending/failed/incomplete attempts remain unknown.
History IDs are decimal strings: compare as Python integers, never SQLite REAL.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import re


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def history_id(value):
    return value if isinstance(value, str) and re.fullmatch(r'[1-9][0-9]{0,127}', value) else None


def address_hashes(addresses):
    return sorted({_digest(str(a).strip().lower()) for a in addresses if str(a).strip()})


class GmailObservations:
    def __init__(self, app):
        self.app = app
        with app.lock:
            if getattr(app.db, 'in_transaction', False):
                raise RuntimeError('邮箱观察初始化不能嵌入已有事务')
            app.db.execute('''CREATE TABLE IF NOT EXISTS gmail_observations (
                account TEXT NOT NULL, scope TEXT NOT NULL, addresses TEXT NOT NULL,
                attempt INTEGER NOT NULL, state TEXT NOT NULL, reason TEXT NOT NULL,
                history_id TEXT, content_digest TEXT, message_count INTEGER,
                observed_at TEXT, PRIMARY KEY(account,scope))''')
            app.db.commit()

    @contextmanager
    def _write(self):
        with self.app.lock:
            db = self.app.db
            if db.in_transaction:
                raise RuntimeError('邮箱观察不能嵌入已有事务')
            db.execute('BEGIN IMMEDIATE')
            try:
                yield
                db.commit()
            except BaseException:
                if db.in_transaction:
                    db.rollback()
                raise

    def begin(self, account, addresses):
        hashes = address_hashes(addresses)
        if not isinstance(account, str) or not account or not hashes:
            raise ValueError('邮箱观察范围无效')
        account = account.strip().lower()
        scope = _digest({'coverage': 'gmail_exact_correspondence_v1', 'addresses': hashes})
        with self._write():
            row = self.app.db.execute('SELECT attempt FROM gmail_observations WHERE account=? AND scope=?', (account, scope)).fetchone()
            attempt = row[0] + 1 if row else 1
            if row:
                self.app.db.execute("UPDATE gmail_observations SET attempt=?,state='unknown',reason='pending' WHERE account=? AND scope=?", (attempt, account, scope))
            else:
                self.app.db.execute("INSERT INTO gmail_observations(account,scope,addresses,attempt,state,reason) VALUES (?,?,?,?,'unknown','pending')", (account, scope, json.dumps(hashes), attempt))
        return {'account': account, 'scope': scope, 'attempt': attempt}

    def finish(self, ticket, *, before=None, after=None, complete=False, messages=(), reason='incomplete'):
        """Finish only the latest-started attempt. Retain prior successful data.

        An old completion/failure cannot overwrite a newer attempt. A newer
        attempt with a lower provider watermark also cannot regress success.
        Only a digest/count are stored, never bodies, subjects or addresses.
        """
        before, after = history_id(before), history_id(after)
        valid = complete is True and before is not None and before == after
        if complete and not valid:
            reason = 'unstable_or_missing_history_id'
        digest = _digest(sorted([{k: m.get(k) for k in (
            'id', 'thread_id', 'direction', 'sent_at', 'from', 'to', 'cc', 'bcc',
            'rfc_message_id', 'subject', 'body', 'mail_kind', 'body_truncated', 'attachments')}
            for m in messages], key=lambda x: str(x.get('id')))) if valid else None
        with self._write():
            row = self.app.db.execute('SELECT attempt,history_id,content_digest FROM gmail_observations WHERE account=? AND scope=?', (ticket['account'], ticket['scope'])).fetchone()
            if not row or row[0] != ticket['attempt']:
                return {'state': 'unknown', 'reason': 'superseded_attempt', 'accepted': False}
            if valid and row[1] and int(after) < int(row[1]):
                valid, reason = False, 'regressed_history_id'
            if valid and row[1] == after and row[2] not in (None, digest):
                valid, reason = False, 'conflicting_same_watermark'
            if valid:
                self.app.db.execute("UPDATE gmail_observations SET state='complete',reason='',history_id=?,content_digest=?,message_count=?,observed_at=? WHERE account=? AND scope=? AND attempt=?", (after, digest, len(messages), datetime.now(timezone.utc).isoformat(), ticket['account'], ticket['scope'], ticket['attempt']))
            else:
                self.app.db.execute("UPDATE gmail_observations SET state='unknown',reason=? WHERE account=? AND scope=? AND attempt=?", (str(reason)[:100], ticket['account'], ticket['scope'], ticket['attempt']))
        return {'state': 'complete' if valid else 'unknown', 'reason': '' if valid else reason,
                'history_id': after if valid else row[1], 'accepted': valid,
                'scope': ticket['scope'], 'content_digest': digest if valid else row[2]}


def begin_observation(mailbox, addresses):
    store = getattr(mailbox, 'observation_store', None)
    if store is None:
        return None
    try:
        return store.begin(mailbox.account_email, addresses)
    except Exception:
        return None


def finish_observation(mailbox, ticket, **values):
    if ticket is None:
        return {'state': 'unknown', 'reason': 'shared_observation_unavailable'}
    try:
        return mailbox.observation_store.finish(ticket, **values)
    except Exception:
        # Persistence failures cannot certify an observation or affect dispatch.
        return {'state': 'unknown', 'reason': 'shared_observation_write_failed'}


def revision_observations(app, account, addresses):
    """Read persisted matching scopes, including unknown state, without writes.

    Attempt counters and polling timestamps intentionally do not invalidate a
    client revision when a successful observation is otherwise unchanged.
    """
    wanted = set(address_hashes(addresses))
    if not account or not wanted:
        return []
    with app.lock:
        exists = app.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='gmail_observations'").fetchone()
        if not exists:
            return []
        rows = app.db.execute('SELECT scope,addresses,state,history_id,content_digest FROM gmail_observations WHERE account=? ORDER BY scope', (str(account).strip().lower(),)).fetchall()
    return [{'scope': scope, 'state': state, 'history_id': hid, 'content_digest': digest}
            for scope, hashed, state, hid, digest in rows if wanted.intersection(json.loads(hashed))]
