"""Bounded read-only formal product snapshots, one stable current file per ID."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ids', nargs='*')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('catalog_read', ROOT / '08_工具链/01_业务脚本/国际站扩品/read_only_catalog.py')
    read = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(read)
    spec = importlib.util.spec_from_file_location('alibaba_client', ROOT / '.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py')
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    original = client.http_json
    client.http_json = lambda request: original(request, timeout=25)
    config = client.load_config(client.DEFAULT_CONFIG)
    catalog = json.loads((OUT / 'catalog.json').read_text(encoding='utf-8'))
    if not catalog.get('complete'):
        raise ValueError('Complete catalog snapshot required')
    ids = args.ids or [str(p['id']) for p in catalog['products']]
    def fetch(pid):
        path = OUT / '商品' / pid / 'formal_get.json'
        if path.exists() and not args.refresh:
            old = json.loads(path.read_text(encoding='utf-8'))
            if old.get('response', {}).get('product'):
                return {'id': pid, 'state': 'PRESERVED', 'at': old['observed_at_utc']}
        logs = []
        try:
            response = read.read_only_call(client, config, 'alibaba.icbu.product.get', {'product_id': int(pid), 'language': 'ENGLISH'}, evidence=logs)
            product = response.get('product')
            if not product:
                raise ValueError('Formal product missing')
            at = datetime.now(timezone.utc).isoformat()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'requested_product_id': pid, 'observed_at_utc': at, 'method': 'alibaba.icbu.product.get', 'response': client.redact_tokens(response)}, ensure_ascii=False, indent=2), encoding='utf-8')
            return {'id': pid, 'state': 'SAVED', 'at': at}
        except Exception as exc:
            # Keep controlled classifications, never signed URLs or tokens.
            return {'id': pid, 'state': 'ERROR', 'type': type(exc).__name__, 'transport': logs}
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(fetch, pid) for pid in ids]
        for job in as_completed(jobs):
            results.append(job.result())
            if len(results) % 25 == 0:
                print(json.dumps({'processed': len(results), 'total': len(ids), 'errors': sum(x['state']=='ERROR' for x in results)}, ensure_ascii=False), flush=True)
    manifest = {'scope': 'Formal product.get fields returned by API; not public visual QA or source verification', 'items': sorted(results, key=lambda x: x['id'])}
    suffix = 'full_detail_manifest.json' if not args.ids else 'selected_detail_manifest.json'
    (OUT / suffix).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'total': len(results), 'saved_or_preserved': sum(x['state']!='ERROR' for x in results), 'errors': sum(x['state']=='ERROR' for x in results)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
