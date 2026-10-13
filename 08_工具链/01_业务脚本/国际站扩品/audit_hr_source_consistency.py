"""Audit current HR sources, exact-ID records and local projections without writes to Alibaba."""
from pathlib import Path
from datetime import datetime, timezone
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
REG = ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
sys.path.insert(0, str(ROOT/'08_工具链/06_工作区维护'))
import build_product_workspace as workspace


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    registry = load(REG)
    products = {x['id']: x for x in registry['products']}
    listings = {x['id']: x for x in registry['listings']}
    sources = {x['id']: x for x in registry['sources']}
    rows = []
    for family, targets in load(BASE/'scope.json')['targets'].items():
        plan = load(BASE/family/'事实与页面计划.json')
        source_id = plan['source_id']
        product = products[family]
        for variant, pid in targets.items():
            folder = BASE/'商品'/pid
            verification = load(folder/'verification.json') if (folder/'verification.json').exists() else {'state': 'SUBMITTED' if (folder/'update_once.json').exists() else 'LOCAL_DRAFT'}
            listing = listings[pid]
            state = verification['state']
            checks = {
                'one_current_real_source': product['candidate_source_ids'] == [source_id]
                    and sources[source_id]['model'] == plan['source_artno'],
                'listing_state_matches_api': listing['optimization']['source_replacement']['state'] == state,
                'source_plan_target_id': plan['target_ids'][variant] == pid,
                'submission_stage_ledger_correct': not (folder/'update_once.json').exists() if state in ['LOCAL_DRAFT','LOCAL_PREPARATION'] else (folder/'update_once.json').is_file(),
            }
            if state == 'FORMAL_FIELDS_SCORE_PASS':
                actual = load(folder/'after_get.json')['product']
                canonical = load(ROOT/listing['formal_fields']['file'])['response']['product']
                current = listing['current_platform_fields']
                checks.update({
                    'formal_source_bound': listing['bound_source_id'] == source_id,
                    'current_local_title': actual['subject'] == canonical['subject'] == current['title'],
                    'current_local_main_images': actual['main_image']['images'] == canonical['main_image']['images'] == current['main_images'],
                    'current_local_sku': actual['product_sku'] == canonical['product_sku'],
                    'current_local_details': actual['struct_detail'] == canonical['struct_detail'],
                    'bank_manifest_complete': load(BASE/family/'素材清单.json')['state'] == 'VISUAL_PASS',
                })
            rows.append({'family': family, 'model': plan.get('model_numbers',{}).get(variant,family+'-'+variant), 'id': pid,
                         'state': state, 'source_id': source_id, 'checks': checks})
    for profile in load(BASE/'已有实款对应.json')['families']:
        family = profile['family']; source_id = profile['source_id']
        product = products[family]
        proof = load(BASE/family/'来源与正式绑定核验.json')
        for pid in profile['ids']:
            listing = listings[pid]
            checks = {
                'one_current_real_source': product['candidate_source_ids'] == [source_id]
                    and product['adopted_source_id'] == source_id
                    and sources[source_id]['model'] == profile['source_model'],
                'formal_source_bound': listing['bound_source_id'] == source_id,
                'binding_evidence_matches': listing['optimization']['source_binding_reconciliation']['source_id'] == source_id
                    and proof['source']['id'] == source_id,
                'no_repeated_platform_replacement': proof['platform_mutation'] == 'NONE_EXISTING_ACTUAL_SHOE_PRESERVED',
                'formal_picture_sku_proof': any(r['id'] == pid and all(r['checks'].values()) for r in proof['links']),
            }
            rows.append({'family': family, 'model': listing['model'], 'id': pid,
                         'state': proof['state'], 'source_id': source_id, 'checks': checks})
    # Check the buyer/source lookup projections as well as their JSON truth.
    stale = []
    for path, expected in workspace.build(registry).items():
        target = path if path.is_absolute() else ROOT/path
        if not target.is_file() or target.read_bytes().replace(b'\r\n', b'\n') != expected.replace(b'\r\n', b'\n'):
            stale.append(str(target.relative_to(ROOT)))
    failed = [{'id': row['id'], 'checks': [k for k, v in row['checks'].items() if not v]}
              for row in rows if not all(row['checks'].values())]
    proof = {'state': 'CURRENT_SOURCE_PLATFORM_LOCAL_CONSISTENCY_PASS' if not failed and not stale else 'CONSISTENCY_FAILED',
             'at': datetime.now(timezone.utc).isoformat(), 'rows': rows,
             'failed': failed, 'stale_source_projections': stale,
             'scope': 'Exact recorded HR replacements and verified existing-real-source bindings only; pending review stays pending. Submission ledgers prevent replay. Physical stock and untested public presentation are not implied.'}
    (BASE/'双改与货源一致性核验.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    assert not failed and not stale, (failed, stale)
    print('SOURCE_DOUBLE_SYNC_PASS', len(rows), 'links; current source lookup projections match registry')


if __name__ == '__main__':
    main()
