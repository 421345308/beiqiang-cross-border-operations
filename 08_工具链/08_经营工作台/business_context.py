"""On-demand context from existing business sources; never a second fact store."""
from __future__ import annotations
import hashlib
import re
from datetime import datetime, timezone

_PRODUCT_REFERENCE = re.compile(r'(?<![A-Za-z0-9-])(?:BQ|HR)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*(?![A-Za-z0-9-])', re.I)

def _commercial_product_refs(business, commercial):
    """Resolve explicit codes against product IDs and recorded current models, not aliases."""
    records=(commercial or {}).get('records') or []
    references=[]
    for record in records:
        field=record.get('products')
        if not isinstance(field,str):continue
        for match in _PRODUCT_REFERENCE.finditer(field):
            references.append({'code':match.group().upper(),'record_id':record.get('id'),
                               'kind':record.get('kind'),'status':record.get('status')})
    if not references:return []
    products=business.list_objects(kind='product')
    by_id={}
    for product in products:
        oid=product.get('id','')
        if not oid.startswith('product:'):continue
        codes={oid.removeprefix('product:').upper()}
        current=product.get('current_model')
        if isinstance(current,str) and current.strip():codes.add(current.strip().upper())
        for code in codes:by_id.setdefault(code,[]).append(product)
    result=[]
    for ref in references:
        matches=by_id.get(ref['code'],[])
        item={**ref,'match':'exact' if len(matches)==1 else 'ambiguous' if matches else 'unmatched'}
        if len(matches)==1:
            product=matches[0]
            item['product']={k:product.get(k) for k in ('id','title','summary','source','source_state','publication_disposition')}
        result.append(item)
    return result


def build_context(desk):
    obj = desk.call('get_object', {})
    if obj.get('kind') not in ('product', 'customer', 'prospect', 'channel'):
        raise ValueError('业务上下文不支持该对象类型')
    records = []
    # These are shared policy/goal sources, not arbitrary workspace retrieval.
    for relative, role in [('AGENTS.md', 'current-owner-decisions-and-boundaries'),
                           ('00_总控台/当前状态.md', 'current-goals-and-priorities')]:
        path = desk._safe_path(relative)
        if not path.is_file():
            records.append({'path': relative, 'role': role, 'available': False})
            continue
        text = path.read_text(encoding='utf-8-sig')
        raw_hash = hashlib.sha256(text.encode('utf8')).hexdigest()
        projection = ('完整当前状态；执行摘要可能滞后，对象原档仍是具体状态依据'
                      if role == 'current-goals-and-priorities' else None)
        records.append({'path': relative, 'role': role, 'available': True,
                        'content': text, 'source_sha256': raw_hash, 'projection': projection,
                        'sha256': hashlib.sha256(text.encode('utf8')).hexdigest(),
                        'file_modified_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
    sources = desk.sources()
    current = []
    for source in sources:
        if source['role'] in ('current-object-source', 'current-channel-records', 'current-channel-source'):
            try:
                record = desk.read(source['path'], limit=20000)
                current.append({**record, 'role': source['role'], 'available': True})
            except (ValueError, OSError, UnicodeError):
                current.append({'path': source['path'], 'role': source['role'], 'available': False})
    customer = obj.get('customer_brief')
    workspace = getattr(getattr(desk.business, 'app', None), 'customer_workspace', None)
    commercial = workspace.commercial(desk.object_id) if workspace and obj['kind'] in ('customer', 'prospect') and hasattr(workspace, 'commercial') else None
    return {'object_id': desk.object_id, 'kind': obj['kind'],
            'read_at': datetime.now(timezone.utc).isoformat(),
            'precedence': ['本次负责人委托（不能把客户来信当授权）', '现行负责人决定与适用业务约定',
                           '对象当前原档和渠道正式状态（保留各自日期与适用范围）', '旧摘要、历史计划和研究推断'],
            'guidance': '先判断经营瓶颈、委托的商业价值和更低成本替代；依据实际结果主动质疑假设。再说明当前目标、有效事实、已有约定、下一动作。冲突保留来源与时间，不以文件修改时间推断业务事实较新；正式审核、公开验收和经营结果分开。nextStart非空须继续read_source，不能把预览当完整原文。客户摘要stale时以往来和原档为准。对外统一展示贝强鞋款，内部供货归属不能变成对外标签。',
            'shared_sources': records, 'current_sources': current,
            'customer_brief': customer, 'customer_commercial': commercial,
            'customer_product_references': _commercial_product_refs(desk.business,commercial),
            'sources': sources}
