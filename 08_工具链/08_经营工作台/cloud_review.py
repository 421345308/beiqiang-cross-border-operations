"""Read cloud proposals and reuse the existing version-checked local review."""
from __future__ import annotations

import importlib.util
import re
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
QUEUE_URL = 'https://www.beiqiang.online/api/workbench-runner'


class CloudReview:
    def __init__(self, root, state, queue_factory=None):
        self.root = Path(root).resolve()
        self.state = Path(state)
        self.queue_factory = queue_factory or _runner.Queue

    def _queue(self):
        path = self.state / 'cloud-pairing-secret.txt'
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512:
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
                raise ValueError('云端连接身份已失效，请恢复现有配对。') from None
            if error.code == 400:
                raise ValueError('云端服务尚未支持此读取方式，请先完成服务更新。') from None
            raise ValueError('云端读取失败，请稍后重新读取。') from None
        except (URLError, TimeoutError, OSError):
            raise ValueError('暂时无法连接云端，请检查网络后重新读取。') from None
        if not isinstance(value, dict):
            raise ValueError('云端返回格式无效。')
        return value

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
        return proposal

    def preview(self, run_id):
        proposal = self._proposal(run_id)
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
                'diff': preview.get('diff', ''), 'proposal_hash': preview.get('proposal_hash'),
                'conflict': False}

    def apply(self, run_id, expected_hash):
        if not isinstance(expected_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_hash):
            raise ValueError('请先预览当前云端成果。')
        proposal = self._proposal(run_id)
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
