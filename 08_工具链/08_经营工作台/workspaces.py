"""Local video drafts and typed connector calls; shares the workbench SQLite store."""
from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


class WorkspaceConflict(ValueError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def text(value, label, maximum=4000, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(label + '格式不正确')
    return value.strip() if required else value


class Workspaces:
    def __init__(self, app):
        self.app = app
        self.modules = {}
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS workspace_objects (kind TEXT, id TEXT, data TEXT NOT NULL, PRIMARY KEY(kind,id))')
            app.db.execute('CREATE TABLE IF NOT EXISTS tool_receipts (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            app.db.commit()

    def objects(self, kind):
        with self.app.lock:
            return [json.loads(r[0]) for r in self.app.db.execute('SELECT data FROM workspace_objects WHERE kind=? ORDER BY rowid DESC', (kind,))]

    def get(self, kind, oid):
        with self.app.lock:
            row = self.app.db.execute('SELECT data FROM workspace_objects WHERE kind=? AND id=?', (kind, oid)).fetchone()
        if not row:
            raise ValueError('找不到这份本地草稿')
        return json.loads(row[0])

    def save(self, kind, body):
        old = self.get(kind, body['id']) if body.get('id') else None
        oid = old['id'] if old else uuid.uuid4().hex
        now = timestamp()
        if kind == 'canvas':
            nodes = body.get('nodes', [])
            if not isinstance(nodes, list) or len(nodes) > 120:
                raise ValueError('画布最多保存120个节点')
            clean = []
            ids = set()
            for node in nodes:
                if not isinstance(node, dict):
                    raise ValueError('节点格式不正确')
                nid = text(node.get('id'), '节点ID', 100, True)
                if nid in ids:
                    raise ValueError('节点ID不能重复')
                ids.add(nid)
                kind_name = node.get('type')
                if kind_name not in ('text', 'shot', 'asset', 'image', 'video', 'audio', 'script'):
                    raise ValueError('不支持的节点类型')
                position = {}
                for axis in ('x', 'y'):
                    value = node.get(axis, 0)
                    if type(value) not in (int, float) or not math.isfinite(value) or not -100000 <= value <= 100000:
                        raise ValueError('节点位置不正确')
                    position[axis] = value
                clean.append({'id': nid, 'type': kind_name, 'title': text(node.get('title', ''), '节点标题', 200),
                              'content': text(node.get('content', ''), '节点内容', 12000),
                              'media_path': text(node.get('media_path', ''), '素材路径', 2000), **position})
            data = {'id': oid, 'title': text(body.get('title'), '画布名称', 200, True), 'nodes': clean,
                    'project_id': text(body.get('project_id') or '', 'LibTV画布ID', 128),
                    'workspace_id': text(body.get('workspace_id') or '', 'LibTV工作区ID', 128)}
        elif kind == 'product_draft':
            product_id = text(body.get('product_id'), '商品ID', 128, True)
            if not re.fullmatch(r'[A-Za-z0-9_-]+', product_id):
                raise ValueError('商品ID不正确')
            data = {'id': oid, 'product_id': product_id,
                    'subject_before': text(body.get('subject_before', ''), '原商品标题', 1000),
                    'subject_after': text(body.get('subject_after', ''), '拟修改标题', 1000),
                    'notes': text(body.get('notes', ''), '优化说明', 12000), 'status': 'local_draft'}
        else:
            raise ValueError('不支持的草稿类型')
        data.update(created_at=old['created_at'] if old else now, updated_at=now)
        with self.app.lock:
            if old and (body.get('updated_at') != old['updated_at'] or self.get(kind, oid)['updated_at'] != old['updated_at']):
                raise WorkspaceConflict('这份草稿已被其他页面更新，请重新打开后编辑；当前内容未覆盖')
            self.app.db.execute('INSERT OR REPLACE INTO workspace_objects VALUES (?,?,?)', (kind, oid, json.dumps(data, ensure_ascii=False)))
            self.app.db.commit()
        return data

    def adapter(self, provider):
        if provider not in ('alibaba', 'libtv'):
            raise ValueError('未知连接器')
        if provider not in self.modules:
            path = HERE / 'connectors' / provider / 'adapter.py'
            name = 'workbench_connector_' + provider
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            self.modules[provider] = module
        return self.modules[provider]

    def call(self, provider, operation, args, write=False):
        routes = {
            'alibaba': {'capabilities': (), 'connection-check': (), 'products': ('page', 'page_size'),
                        'product': ('product_id',), 'orders': ('page', 'page_size'), 'order': ('order_id',)},
            'libtv': {'account': (), 'workspaces': ('page', 'page_size'), 'projects': ('workspace_id', 'page', 'page_size'),
                      'project': ('project_id',), 'nodes': ('project_id',),
                      'create-project': ('name', 'workspace_id'),
                      'create-text-node': ('project_id', 'title', 'content', 'x', 'y')},
        }
        mutations = {'create-project', 'create-text-node'}
        if operation not in routes.get(provider, {}) or ((operation in mutations) != write):
            raise ValueError('该操作尚未接入')
        if write and args.get('confirmed') is not True:
            raise ValueError('请先核对目标与内容，再确认执行')
        params = {k: args[k] for k in routes[provider][operation] if k in args and args[k] not in (None, '')}
        for key in ('page', 'page_size'):
            if key in params:
                params[key] = int(params[key])
        result = self.adapter(provider).execute(operation, **params)
        if provider == 'libtv' and result.get('ok'):
            result['source'] = {**(result.get('source') or {}), 'collectedAt': timestamp()}
        receipt = {'id': uuid.uuid4().hex, 'provider': provider, 'operation': operation,
                   'target': str(params.get('product_id') or params.get('order_id') or params.get('project_id') or params.get('workspace_id') or ''),
                   'at': timestamp(), 'ok': result.get('ok') is True, 'source': result.get('source'), 'error': result.get('error')}
        with self.app.lock:
            self.app.db.execute('INSERT INTO tool_receipts VALUES (?,?)', (receipt['id'], json.dumps(receipt, ensure_ascii=False)))
            self.app.db.commit()
        return {**result, 'receipt_id': receipt['id']}

    def receipts(self):
        with self.app.lock:
            return [json.loads(r[0]) for r in self.app.db.execute('SELECT data FROM tool_receipts ORDER BY rowid DESC LIMIT 50')]

    def metrics(self):
        source = '02_Alibaba运营/01_店铺与全店诊断/经营复核.json'
        path = self.app.root / source
        if not path.is_file():
            return {'ok': False, 'error': '尚无本地经营数据档案', 'source': source}
        summary = json.loads(path.read_text(encoding='utf-8-sig'))['summary']
        return {'ok': True, 'source': source, 'observed_at': summary.get('observed_at'),
                'period': summary.get('period'), 'timezone': summary.get('timezone'),
                'metrics': summary.get('totals', {}),
                'warnings': ['本地历史经营档案，不是实时API；刷新不会重新采集平台数据。', summary.get('scope', ''),
                             '询盘、TM买家、营销点击口径不同，不合并为转化率。']}

    def route_get(self, path, query):
        if path == '/api/canvases':
            return {'canvases': [{k: v for k, v in item.items() if k != 'nodes'} for item in self.objects('canvas')]}
        if path.startswith('/api/canvases/'):
            return self.get('canvas', path.split('/')[-1])
        if path == '/api/product-drafts':
            return {'drafts': self.objects('product_draft')}
        if path == '/api/tools/receipts':
            return {'receipts': self.receipts()}
        if path == '/api/channel-metrics/alibaba':
            return self.metrics()
        if path.startswith('/api/tools/'):
            parts = path.strip('/').split('/')
            if len(parts) != 4:
                raise ValueError('未知工具入口')
            return self.call(parts[2], parts[3], {k: v[0] for k, v in query.items()})
        raise ValueError('未知工作区入口')

    def route_post(self, path, body):
        if path == '/api/canvases':
            return self.save('canvas', body)
        if path == '/api/product-drafts':
            return self.save('product_draft', body)
        parts = path.strip('/').split('/')
        if len(parts) == 4 and parts[:2] == ['api', 'tools']:
            return self.call(parts[2], parts[3], body, write=True)
        raise ValueError('未知工作区操作')
