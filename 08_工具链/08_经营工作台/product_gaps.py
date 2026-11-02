"""Find missing product associations without inferring a price or specification."""
import re

PLATFORM_ID = re.compile(r'^Alibaba\s+(\d{6,32})$')

# 已登记的资料关联
GAPS = (
    ('no_source', '缺供货链接', '尚未关联这款外采商品的供货链接。', 'high'),
    ('no_asset', '未关联商品图片', '商品档案中没有关联图片。', 'normal'),
    ('no_platform_id', '未关联国际站商品', '商品档案中没有国际站商品链接。', 'low'),
)
GAP_KEYS = tuple(key for key, *_ in GAPS)
GAP_BY_KEY = {key: {'key': key, 'label': label, 'reason': reason, 'severity': severity}
              for key, label, reason, severity in GAPS}
LIST_LEVEL_KEYS = ('no_source', 'no_asset', 'no_platform_id')
SEVERITY_ORDER = {'high': 0, 'normal': 1, 'low': 2}


def _platform_ids(obj):
    ids = []
    for link in obj.get('links') or []:
        match = PLATFORM_ID.match(str(link.get('label') or '').strip())
        if match:
            ids.append(match.group(1))
    return ids


def _gaps(obj):
    """Return gap keys present on one product object."""
    found = []
    supply = obj.get('supply') or {}
    if supply.get('kind') == 'external' and not supply.get('url'):
        found.append('no_source')
    if not obj.get('assets'):
        found.append('no_asset')
    if not _platform_ids(obj):
        found.append('no_platform_id')
    return found


class ProductGaps:
    def __init__(self, app):
        self.app = app

    def _detail_gaps(self, obj):
        """Only associations are authoritative in this projection."""
        return sorted(set(_gaps(obj)), key=lambda k: SEVERITY_ORDER[GAP_BY_KEY[k]['severity']])

    def summary(self, limit=12):
        """全量汇总，供"今天"页与商品页排序使用。"""
        rows = []
        products = [obj for obj in self.app.business.list_objects(kind='product')
                    if not re.fullmatch(r'HR[-_]?\d+', str(obj.get('title') or ''), re.I)]
        for obj in products:
            keys = _gaps(obj)
            if not keys:
                continue
            rows.append({'product_id': obj['id'].split(':', 1)[-1], 'object_id': obj['id'], 'title': obj.get('title') or '',
                         'supply_label': (obj.get('supply') or {}).get('label', ''),
                         'source_role': obj.get('source_role'), 'category': obj.get('category'),
                         'gap_keys': keys,
                         'gaps': [GAP_BY_KEY[k] for k in keys],
                         'severity': min((GAP_BY_KEY[k]['severity'] for k in keys), key=lambda s: SEVERITY_ORDER[s]),
                         'platform_ids': _platform_ids(obj)})
        rows.sort(key=lambda r: (SEVERITY_ORDER[r['severity']], -len(r['gap_keys']), r['title']))
        counts = {key: sum(key in r['gap_keys'] for r in rows) for key in GAP_KEYS}
        return {'total': len(products), 'with_gaps': len(rows),
                'counts': counts, 'items': rows[:max(0, int(limit))],
                'checked': list(LIST_LEVEL_KEYS),
                'labels': GAP_BY_KEY,
                'notice': '展示尚未关联的商品资料，具体报价与供货以实际商品和订单为准。'}

    def for_product(self, product_id):
        """单款已登记的资料关联。"""
        if not isinstance(product_id, str) or not product_id.strip():
            raise ValueError('请提供商品款号')
        object_id = product_id if product_id.startswith('product:') else 'product:' + product_id
        obj = self.app.business.get_object(object_id)
        keys = self._detail_gaps(obj)
        return {'object_id': obj['id'], 'title': obj.get('title') or '',
                'supply_label': (obj.get('supply') or {}).get('label', ''), 'source_role': obj.get('source_role'),
                'gap_keys': keys, 'gaps': [GAP_BY_KEY[k] for k in keys],
                'platform_ids': _platform_ids(obj),
                'checked': list(LIST_LEVEL_KEYS),
                'notice': '这里只检查已关联的资料，不判断能否报价。'}
