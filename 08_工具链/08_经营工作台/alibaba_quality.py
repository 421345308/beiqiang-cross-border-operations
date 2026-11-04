"""Projection of locally saved official quality diagnostics; never calls Alibaba."""
from pathlib import Path
import json
from collections import Counter


def latest_quality(root):
    base = Path(root) / '08_工具链/08_经营工作台/.local/alibaba'
    snapshots = []
    for path in base.glob('quality-*/quality.json'):
        try:
            data = json.loads(path.read_text(encoding='utf8'))
            if not isinstance(data, dict) or not isinstance(data.get('items'), list):
                continue
            if not isinstance(data.get('observed_at_utc'), str):
                continue
            snapshots.append((data['observed_at_utc'], data, path))
        except (OSError, ValueError, TypeError):
            continue
    if not snapshots:
        return {'available': False, 'notice': '暂无已保存的质量分诊断；需要运行只读诊断后查看。'}
    _, data, path = max(snapshots, key=lambda entry: entry[0])
    catalog_states = None
    try:
        catalog = json.loads((path.parent / 'catalog/catalog.json').read_text(encoding='utf8'))
        products = catalog.get('products') or []
        if catalog.get('complete') is True and len(products) == catalog.get('total_item'):
            catalog_states = dict(Counter(f"{row.get('status') or 'unknown'}/{row.get('display') or 'unknown'}" for row in products))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    items = data['items']
    below = [row for row in items if isinstance(row, dict) and isinstance(row.get('score'), (int, float)) and row['score'] < 5]
    issue_rows = [row for row in items if isinstance(row, dict) and row.get('problems')]
    score_times = [row['observed_at_utc'] for row in items if isinstance(row, dict) and isinstance(row.get('observed_at_utc'), str)]
    below.sort(key=lambda row: (row['score'], str(row.get('id', ''))))
    visible = lambda row: {k: row.get(k) for k in ('id', 'model', 'listing_status', 'display', 'score', 'problems', 'platform_reason', 'observed_at_utc')}
    return {'available': True, 'observed_at': data['observed_at_utc'],
            'score_observed_from': min(score_times) if score_times else None,
            'score_observed_to': max(score_times) if score_times else None,
            'catalog_observed_at': data.get('catalog_observed_at_utc'),
            'catalog_state_counts': catalog_states,
            'catalog_total': data.get('catalog_total'), 'selected': data.get('selected'),
            'scored': data.get('scored'), 'complete': data.get('complete') is True,
            'error_count': len(data.get('errors') or []),
            'missing_score_count': sum(row.get('score') is None for row in items if isinstance(row, dict)),
            'below_5_count': len(below), 'below_5': [visible(row) for row in below],
            'issue_count': len(issue_rows), 'issues': [visible(row) for row in issue_rows],
            'notice': '汇总时间是汇总生成时间，各商品评分可能分时采集；请查看评分采集时间范围。这不是实时流量、询盘或公开页面验收。'}
