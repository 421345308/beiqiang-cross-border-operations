"""Local commercial continuation in the existing customer profile.

Original quotations, sample agreements and orders remain authoritative. This
section records operator summaries and references, never sends or places orders.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4
from workspaces import WorkspaceConflict

KINDS = {'quotation': '报价', 'sample': '样品', 'order': '订单'}
STATUSES = {'draft': '内部准备', 'recorded': '实际记录', 'cancelled': '已取消'}
FIELDS = {'id', 'kind', 'status', 'summary', 'reference', 'products', 'terms',
          'purpose', 'acceptance', 'exclusions', 'actual_result', 'profit_basis'}


def _text(value, limit=4000):
    if not isinstance(value, str) or len(value) > limit or '\x00' in value:
        raise ValueError('商机文字格式无效或过长')
    return value.strip()


def _revision(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def view(workspace, object_id):
    obj, source_type, record, original, source_hash = workspace._source(object_id)
    saved = workspace._saved_profile(object_id)
    data = deepcopy(saved.get('commercial') or {'records': []})
    flow = workspace.workflow(object_id)
    # The editable revision must cover both commercial records and the persisted
    # workflow fields shown in this editor. Otherwise a next-action edit can be
    # silently overwritten while the commercial-only hash remains unchanged.
    flow_data = saved.get('workflow') or {}
    # Use shared persisted observations, not Gmail's per-process cache or the
    # clock-derived overdue display. The event table is not a complete mailbox.
    revision = _revision({'commercial': data, 'workflow': flow_data,
                          'source_hash':source_hash,'gmail':workspace._gmail_revision_inputs(object_id)})
    return {'object_id': object_id, 'revision': revision, **data,
            'owner': data.get('owner', ''),
            'next_action': flow.get('next_action', ''), 'due_at': flow.get('due_at'),
            'source': obj.get('source', ''),
            'source_orders': deepcopy(record.get('orders', [])) if source_type == 'alibaba_order_buyer' else [],
            'labels': {'kinds': KINDS, 'statuses': STATUSES},
            'local_only': True, 'external_action': False}


def save(workspace, object_id, body):
    if not isinstance(body, dict) or set(body) - {'revision', 'record', 'owner', 'next_action', 'due_at'}:
        raise ValueError('不支持的客户商机字段')
    with workspace._profile_write():
        current = view(workspace, object_id)
        if body.get('revision') != current['revision']:
            raise WorkspaceConflict('客户商机或下一步已变化，请重新读取后合并再保存')
        saved = workspace._saved_profile(object_id)
        data = deepcopy(saved.get('commercial') or {'records': []})
        if 'owner' in body:
            data['owner'] = _text(body['owner'], 200)
        if 'record' in body:
            incoming = body['record']
            if not isinstance(incoming, dict) or set(incoming) - FIELDS:
                raise ValueError('报价、样品或订单字段无效')
            rows = data.setdefault('records', [])
            record_id = incoming.get('id')
            old = next((r for r in rows if r['id'] == record_id), None)
            if record_id and old is None:
                raise ValueError('商机记录不存在')
            row = {**(old or {}), **{k: _text(v) for k, v in incoming.items()}}
            if row.get('kind') not in KINDS or row.get('status') not in STATUSES:
                raise ValueError('请选择有效的商机类型和记录状态')
            if not row.get('summary'):
                raise ValueError('请填写当前商业结论')
            if old and row['kind'] != old['kind']:
                raise ValueError('不能将报价记录改成样品或订单')
            row['id'] = record_id or 'commercial-' + uuid4().hex
            row['updated_at'] = datetime.now(timezone.utc).isoformat()
            if old:
                rows[rows.index(old)] = row
            else:
                if len(rows) >= 200:
                    raise ValueError('单客户商机记录已达200条，请沿原项目接续')
                rows.append(row)
        # One existing workflow owns the next action; never maintain a second one.
        flow_body = {k: body[k] for k in ('next_action', 'due_at') if k in body}
        if flow_body:
            import customer_workflow
            flow = workspace.workflow(object_id)
            if flow.get('excluded'):
                # Order buyers remain outside inquiry queues, but can own a next action.
                flow = {**flow, 'excluded': False}
            saved['workflow'] = customer_workflow.update(flow, flow_body, record=workspace._source(object_id)[2])
        data['updated_at'] = datetime.now(timezone.utc).isoformat()
        saved.update(object_id=object_id, commercial=data)
        workspace._store_profile(object_id, saved, commit=False)
        result = view(workspace, object_id)
    return result
