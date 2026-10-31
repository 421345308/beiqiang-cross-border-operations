"""Append-only intake of real inquiry text. No platform calls or SQLite copy."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

DIRECTORY = '04_客户开发/.local/询盘原件'


class InquiryConflict(ValueError):
    code = 'SOURCE_CONTENT_CONFLICT'


class InquiryIntake:
    def __init__(self, app):
        self.app = app
        self.root = Path(app.root).resolve()
        self.directory = self.root / DIRECTORY

    def _directory(self):
        if not self.directory.resolve().is_relative_to(self.root):
            raise ValueError('询盘原件目录超出本地业务范围')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        return self.directory

    @contextmanager
    def _locked(self):
        with self.app.lock:
            folder = self._directory()
            lock = folder / '.intake.lock'
            if lock.is_symlink():
                raise ValueError('原件锁文件不能是链接')
            with lock.open('a+b') as stream:
                if stream.tell() == 0:
                    stream.write(b'0'); stream.flush()
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                try:
                    yield folder
                finally:
                    stream.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _records(self, folder):
        result = []
        for path in folder.glob('*.json'):
            if not re.fullmatch(r'[a-f0-9]{32}\.json', path.name) or path.is_symlink():
                continue
            row = json.loads(path.read_text(encoding='utf-8'))
            if row.get('id') != path.stem or row.get('source_type') != 'manual_import':
                raise ValueError('询盘原件身份不一致，请核对本地原档')
            text = row.get('original_text')
            if not isinstance(text, str) or hashlib.sha256(text.encode('utf-8')).hexdigest() != row.get('original_sha256'):
                raise ValueError('询盘原件校验不一致，请核对本地原档')
            result.append(row)
        return sorted(result, key=lambda row: (row['imported_at'], row['id']), reverse=True)

    def list_records(self):
        with self._locked() as folder:
            return self._records(folder)

    def get_record(self, record_id):
        if not isinstance(record_id, str) or not re.fullmatch(r'[a-f0-9]{32}', record_id):
            raise ValueError('询盘记录编号无效')
        with self._locked() as folder:
            row = next((row for row in self._records(folder) if row['id'] == record_id), None)
            if row is None:
                raise ValueError('找不到询盘原件')
            return row

    @staticmethod
    def _text(body, key, maximum):
        value = body.get(key, '')
        if value is None:
            value = ''
        if not isinstance(value, str) or len(value) > maximum or '\x00' in value:
            raise ValueError(key + '格式或长度无效')
        return value.strip()

    @staticmethod
    def _source_reference(folder, channel, source_id, record, validate_only=False):
        """Append-only alias lets text dedup preserve each actual source ID."""
        if not source_id:
            return
        key = hashlib.sha256((channel + '\n' + source_id).encode('utf-8')).hexdigest()[:32]
        path = folder / ('.source-' + key + '.json')
        if path.is_symlink():
            raise ValueError('来源关联文件不能是链接')
        if path.exists():
            old = json.loads(path.read_text(encoding='utf-8'))
            if old.get('original_sha256') != record['original_sha256']:
                raise InquiryConflict('同一来源编号已有不同正文；原件未覆盖。')
            return
        if validate_only:
            return
        with path.open('x', encoding='utf-8') as stream:
            json.dump({'id': record['id'], 'original_sha256': record['original_sha256']}, stream)
            stream.flush(); os.fsync(stream.fileno())

    def add(self, body):
        if not isinstance(body, dict) or body.get('channel') not in ('alibaba', 'email', 'other'):
            raise ValueError('请选择真实来源渠道')
        channel = body['channel']
        original = body.get('original_text')
        if not isinstance(original, str) or not original.strip() or len(original) > 100000 or '\x00' in original:
            raise ValueError('请输入真实询盘原文，最多100000字')
        fields = {key: self._text(body, key, maximum) for key, maximum in (
            ('company', 500), ('contact_name', 300), ('country', 100), ('quantity', 300),
            ('source_url', 2000), ('source_id', 256), ('received_at', 100))}
        if fields['source_url']:
            url = urlsplit(fields['source_url'])
            if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password:
                raise ValueError('来源链接应为不含登录凭证的HTTP(S)地址')
        if fields['received_at']:
            try:
                datetime.fromisoformat(fields['received_at'].replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('收到时间请使用ISO日期或日期时间，未知时留空') from None
        sha = hashlib.sha256(original.encode('utf-8')).hexdigest()
        record_id = hashlib.sha256((channel + '\n' + sha).encode('utf-8')).hexdigest()[:32]
        row = {'id': record_id, 'channel': channel, **fields, 'original_text': original,
               'original_sha256': sha, 'source_type': 'manual_import',
               'imported_at': datetime.now(timezone.utc).isoformat(),
               'buyer_identity_verified': False, 'natural_acquisition_verified': False}
        with self._locked() as folder:
            previous = self._records(folder)
            # Source alias validation also catches a source ID whose earlier
            # text deduplicated into another source's immutable original.
            if fields['source_id']:
                self._source_reference(folder, channel, fields['source_id'], row, validate_only=True)
            # Check source-ID collision before text dedup: do not silently mask
            # a changed source record by matching a different record's text.
            if fields['source_id']:
                matches = [r for r in previous if r['channel'] == channel and r['source_id'] == fields['source_id']]
                if any(r['original_sha256'] != sha for r in matches):
                    raise InquiryConflict('同一渠道和来源编号已有不同正文；原件未覆盖，请核对来源或明确建立新版本。')
                if matches:
                    self._source_reference(folder, channel, fields['source_id'], matches[0])
                    return matches[0]
            duplicate = next((r for r in previous if r['channel'] == channel and r['original_sha256'] == sha), None)
            if duplicate:
                self._source_reference(folder, channel, fields['source_id'], duplicate)
                return duplicate
            target = folder / (record_id + '.json')
            if target.exists() or target.is_symlink():
                raise InquiryConflict('原件编号已存在，未覆盖')
            fd, temporary = tempfile.mkstemp(prefix='.intake-', dir=folder)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                    json.dump(row, stream, ensure_ascii=False, indent=2)
                    stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
            self._source_reference(folder, channel, fields['source_id'], row)
            return row
