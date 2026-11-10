"""Read cloud proposals and reuse the existing version-checked local review."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError


HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_runner = _load('cloud_review_runner', HERE / 'cloud-runner' / 'runner.py')
_review = _load('cloud_review_proposal', HERE / 'cloud-runner' / 'review-proposal.py')
QUEUE_URL = 'https://www.beiqiang.online/api/workbench-local'


class CloudRejected(ValueError):
    """The transactional cloud endpoint explicitly rejected the request."""


class CloudReview:
    def __init__(self, root, state, queue_factory=None):
        self.root = Path(root).resolve()
        self.state = Path(state)
        self.bridge_dir = self.state / 'cloud-bridge'
        self.queue_factory = queue_factory or _runner.Queue

    def _queue(self):
        path = self.bridge_dir / 'secret'
        if self.bridge_dir.is_symlink() or not self.bridge_dir.is_dir() or path.is_symlink() or not path.is_file() or path.stat().st_size > 512:
            raise ValueError('本机云端连接尚未配置，请检查现有配对文件。')
        secret = path.read_text(encoding='utf-8-sig').strip()
        if len(secret) < 32 or '\n' in secret or '\r' in secret:
            raise ValueError('本机云端连接配置无效。')
        return self.queue_factory(QUEUE_URL, secret)

    def _call(self, action, **fields):
        try:
            value = self._queue().call(action, **fields)
        except HTTPError as error:
            if error.code == 401:
                raise CloudRejected('云端连接身份已失效，请恢复现有配对。') from None
            if error.code == 400:
                raise CloudRejected('云端服务未接受请求，请重新读取任务。') from None
            if error.code == 409:
                raise CloudRejected('云端任务、资料版本或待审成果已变化，请先核对。') from None
            if error.code in (403, 404, 413, 415, 422):
                raise CloudRejected('云端拒绝了请求，请检查连接和任务范围。') from None
            raise ValueError('云端读取失败，请稍后重新读取。') from None
        except (URLError, TimeoutError, OSError):
            raise ValueError('暂时无法连接云端，请检查网络后重新读取。') from None
        if not isinstance(value, dict):
            raise ValueError('云端返回格式无效。')
        return value

    def list_tasks(self):
        tasks = self._call('tasks').get('tasks')
        if not isinstance(tasks, list) or len(tasks) > 100:
            raise ValueError('云端任务列表无效。')
        for task in tasks:
            if (not isinstance(task, dict) or not re.fullmatch(r'[0-9a-f]{32}', str(task.get('id', '')))
                    or type(task.get('version')) is not int or task['version'] < 1
                    or task.get('source') not in (None, *_review.SOURCE_PATHS)
                    or (task.get('source') is not None and (type(task.get('source_version')) is not int or task['source_version'] < 0))):
                raise ValueError('云端任务或版本无效。')
        return {'tasks': tasks}

    def _journal(self):
        if self.bridge_dir.is_symlink() or not self.bridge_dir.is_dir():
            raise ValueError('本机云端连接尚未配置。')
        directory = self.bridge_dir / 'dispatch'
        if directory.is_symlink():
            raise ValueError('本机任务记录目录无效。')
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        return directory

    def _save_dispatch(self, record, *, new=False):
        directory = self._journal()
        path = directory / (record['request_id'] + '.json')
        if path.is_symlink():
            raise ValueError('本机任务记录无效。')
        data = json.dumps(record, ensure_ascii=False).encode('utf-8')
        if new:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            return
        fd, name = tempfile.mkstemp(prefix='.dispatch-', dir=directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name): os.unlink(name)

    def _dispatch_records(self):
        rows = []
        paths = list(self._journal().glob('*.json'))
        if len(paths) > 1000: raise ValueError('本机提交记录过多，请先整理。')
        for path in paths:
            if path.is_symlink() or path.stat().st_size > 4096:
                raise ValueError('本机提交记录异常，请先核对，不能重复提交。')
            try: item = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                raise ValueError('本机提交记录不完整，请先核对，不能重复提交。') from None
            if (not isinstance(item, dict) or not re.fullmatch(r'[0-9a-f]{32}', str(item.get('request_id', '')))
                    or path.stem != item['request_id'] or item.get('status') not in ('pending', 'confirmed', 'rejected')):
                raise ValueError('本机提交记录异常，请先核对，不能重复提交。')
            rows.append(item)
        return sorted(rows, key=lambda item: str(item.get('created_at', '')), reverse=True)

    def dispatches(self):
        rows = self._dispatch_records()[:50]
        return {'dispatches': [{key: item.get(key) for key in ('request_id', 'task_id', 'title', 'status', 'run_id', 'created_at')} for item in rows]}

    def enqueue(self, task_id, task_version, source_version, instruction, model):
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 12000:
            raise ValueError('请填写不超过12000字的任务要求。')
        if model not in ('gpt-6-luna', 'gpt-6.1-sol'):
            raise ValueError('请选择可用模型。')
        task = next((item for item in self.list_tasks()['tasks'] if item['id'] == task_id), None)
        if not task or task['version'] != task_version or task.get('source_version') != source_version:
            raise ValueError('云端任务或资料已变化，请重新读取。')
        source = task.get('source')
        if any(item.get('status') == 'pending' and (item.get('task_id') == task_id or (source and item.get('source') == source)) for item in self._dispatch_records()):
            raise ValueError('此任务已有未确认提交，请先核对状态，不要重复提交。')
        content = None
        if source:
            part_path = self.root
            for part in Path(source).parts:
                part_path = part_path / part
                if part_path.is_symlink() or getattr(part_path, 'is_junction', lambda: False)():
                    raise ValueError('本地资料路径包含链接，不能同步。')
            path = _review.inside(self.root, self.root / source)
            if not path.is_file(): raise ValueError('对应的本地原资料不存在。')
            content = _review.normalize(path.read_text(encoding='utf-8-sig'))
            if len(content.encode('utf-16-le')) // 2 > 100000:
                raise ValueError('本地原资料超过云端支持的长度。')
        request_id = uuid.uuid4().hex
        record = {'request_id': request_id, 'task_id': task_id, 'source': source, 'title': task.get('title', ''),
                  'status': 'pending', 'run_id': None, 'created_at': datetime.now(timezone.utc).isoformat()}
        self._save_dispatch(record, new=True)
        try:
            value = self._call('enqueue', request_id=request_id, task_id=task_id,
                task_version=task_version, source_version=source_version, source_content=content,
                instruction=instruction.strip(), model=model)
            run = value.get('run')
            if (not isinstance(run, dict) or not re.fullmatch(r'[0-9a-f]{32}', str(run.get('id', '')))
                    or run.get('task_id') != task_id or run.get('source') != source):
                raise ValueError('云端未确认任务编号。')
            record.update(status='confirmed', run_id=run['id'])
            self._save_dispatch(record)
            return {'request_id': request_id, 'run_id': run['id'], 'status': run.get('status')}
        except CloudRejected as error:
            record['status'] = 'rejected'
            self._save_dispatch(record)
            raise ValueError(str(error)) from None
        except (ValueError, OSError):
            raise ValueError('提交结果尚未确认，请先使用“核对提交状态”，不要重复提交。') from None

    def reconcile_dispatch(self, request_id):
        if not isinstance(request_id, str) or not re.fullmatch(r'[0-9a-f]{32}', request_id):
            raise ValueError('本机提交记录编号无效。')
        path = self._journal() / (request_id + '.json')
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
            raise ValueError('本机提交记录不存在。')
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('request_id') != request_id:
            raise ValueError('本机提交记录不一致。')
        value = self._call('request_status', request_id=request_id)
        if value.get('found') is not True:
            return {'request_id': request_id, 'status': 'pending', 'message': '云端暂未查到结果，尚不能确认提交是否到达。'}
        run = value.get('run')
        if (not isinstance(run, dict) or not re.fullmatch(r'[0-9a-f]{32}', str(run.get('id', '')))
                or run.get('task_id') != record.get('task_id') or run.get('source') != record.get('source')):
            raise ValueError('云端提交回执无效。')
        record.update(status='confirmed', run_id=run['id'])
        self._save_dispatch(record)
        return {'request_id': request_id, 'status': 'confirmed', 'run_id': run['id'], 'run_status': run.get('status')}

    def list_pending(self):
        rows = self._call('pending_reviews').get('runs')
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError('云端成果列表无效。')
        safe = []
        for row in rows:
            if not isinstance(row, dict) or not re.fullmatch(r'[0-9a-f]{32}', str(row.get('id', ''))):
                raise ValueError('云端成果身份无效。')
            if row.get('status') != 'awaiting_review':
                raise ValueError('云端成果状态已变化，请重新读取。')
            safe.append({k: row.get(k) for k in ('id', 'title', 'summary', 'source', 'updated_at')})
        return {'runs': safe}

    def _proposal(self, run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r'[0-9a-f]{32}', run_id):
            raise ValueError('云端运行编号无效。')
        run = self._call('status', run_id=run_id).get('run')
        if not isinstance(run, dict) or run.get('id') != run_id:
            raise ValueError('云端运行身份不一致，请重新读取。')
        if run.get('status') != 'awaiting_review' or run.get('kind') == 'inquiry_review':
            raise ValueError('此成果不再待审，或应在网站询盘中处理。')
        if type(run.get('version')) is not int or run['version'] < 1:
            raise ValueError('云端成果版本无效，请重新读取。')
        if 'source' not in run or 'source_version' not in run:
            raise ValueError('云端服务尚未提供原资料版本，请先完成服务更新。')
        result = run.get('result')
        if not isinstance(result, dict):
            raise ValueError('云端成果内容无效。')
        proposal = {'schema_version': 1, 'run_id': run_id, 'task_id': run.get('task_id'),
                    'status': run['status'], 'source': run['source'],
                    'source_hash': run.get('source_hash'), 'source_version': run['source_version'],
                    'summary': result.get('summary'), 'changes': result.get('changes'),
                    'next_steps': result.get('next_steps')}
        _review.validate(proposal)
        return proposal, run['version']

    def preview(self, run_id):
        proposal, _ = self._proposal(run_id)
        try:
            preview = _review.review(proposal, self.root)
        except ValueError as error:
            if 'Source hash conflict' in str(error):
                return {'run_id': run_id, 'summary': proposal['summary'],
                        'next_steps': proposal['next_steps'], 'conflict': True,
                        'message': '本地原资料已变化，不能直接应用；请重新核对。'}
            raise
        return {'run_id': run_id, 'source': proposal['source'], 'summary': proposal['summary'],
                'next_steps': proposal['next_steps'], 'changes': len(proposal['changes']),
                'diff': preview.get('diff', ''), 'proposal_hash': preview.get('proposal_hash') or _review.digest(json.dumps(proposal,sort_keys=True,ensure_ascii=False,separators=(',',':'))),
                'conflict': False}

    def apply(self, run_id, expected_hash):
        if not isinstance(expected_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_hash):
            raise ValueError('请先预览当前云端成果。')
        proposal, _ = self._proposal(run_id)
        try:
            current = _review.review(proposal, self.root)
        except ValueError:
            raise ValueError('云端成果或本地资料已变化，请重新预览。') from None
        if current.get('proposal_hash') != expected_hash:
            raise ValueError('云端成果或本地资料已变化，请重新预览。')
        if not proposal['changes']:
            raise ValueError('此成果没有可回写的修改。')
        try:
            applied = _review.review(proposal, self.root, apply=True)
        except ValueError:
            raise ValueError('本地资料已变化或已有写回，请核对后再处理。') from None
        return {'run_id': run_id, 'status': applied['status'],
                'message': '已写回本地原资料；云端审阅状态仍需同步确认。'}

    def acknowledge(self, run_id, expected_hash):
        if not isinstance(expected_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_hash):
            raise ValueError('请先预览当前云端成果。')
        proposal, version = self._proposal(run_id)
        if proposal['changes']:
            raise ValueError('此成果包含原资料修改，请使用写回流程。')
        try:
            current = _review.review(proposal, self.root)
        except ValueError:
            raise ValueError('本地资料已变化，请重新预览。') from None
        fingerprint = current.get('proposal_hash') or _review.digest(json.dumps(proposal,sort_keys=True,ensure_ascii=False,separators=(',',':')))
        if fingerprint != expected_hash:
            raise ValueError('云端成果已变化，请重新预览。')
        try:
            run = self._call('review_no_change', run_id=run_id, expected_version=version).get('run')
        except CloudRejected as error:
            raise ValueError(str(error)) from None
        except ValueError:
            raise ValueError('云端确认结果尚未核实，请先查看云端状态。') from None
        if not isinstance(run, dict) or run.get('id') != run_id or run.get('status') != 'accepted':
            raise ValueError('云端确认结果尚未核实，请先查看云端状态。')
        return {'run_id': run_id, 'status': 'accepted', 'message': '已确认审阅；本地原资料没有改动。'}
