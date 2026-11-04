"""Read-only listing quality diagnostic; evidence stays in the local workbench data directory."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from read_only_catalog import fetch_catalog, read_only_call

ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / '.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py'


def summarize_score(product, response):
    result = response.get('result') or {}
    raw = result.get('problem_map') or {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    problems = raw.get('extendProblemMap') or {}
    if not isinstance(problems, dict):
        raise ValueError('Unexpected diagnostic format')
    reasons = raw.get('errorReasonMap') or {}
    platform_reason = None
    if isinstance(reasons, dict):
        platform_reason = next((reasons[language].strip() for language in ('zh', 'en')
                                if isinstance(reasons.get(language), str) and reasons[language].strip()), None)
    score = result.get('final_score')
    number = float(score) if score is not None else None
    return {'id': str(product['id']), 'model': product.get('red_model'),
            'listing_status': product.get('status'), 'display': product.get('display'),
            'score': number, 'problems': [str(k) for k, v in problems.items() if v is True],
            'platform_reason': platform_reason,
            'request_id': response.get('request_id'), 'trace_id': response.get('_trace_id_')}


def diagnose(client, config, output, max_items=None, resume=False, rebuild_only=False):
    output = Path(output)
    if rebuild_only and not resume:
        raise ValueError('Rebuild requires a saved catalog')
    prior_errors = {}
    if rebuild_only and (output / 'quality.json').is_file():
        previous = json.loads((output / 'quality.json').read_text(encoding='utf8'))
        prior_errors = {str(entry.get('id')): entry for entry in previous.get('errors', [])}
    snapshot_file = output / 'catalog/catalog.json'
    if resume:
        snapshot = json.loads(snapshot_file.read_text(encoding='utf8'))
        saved = snapshot.get('products') or []
        if not snapshot.get('complete') or len(saved) != snapshot.get('total_item') or len({str(x['id']) for x in saved}) != len(saved):
            raise ValueError('Cannot resume an incomplete catalog snapshot')
    else:
        snapshot = fetch_catalog(client, config, output / 'catalog')
    evidence_dir = output / 'scores'
    evidence_dir.mkdir(parents=True, exist_ok=True)
    products = snapshot['products']
    selected = products if max_items is None else products[:max_items]
    rows, errors = [], []
    def read_one(item):
        try:
            secret = item.get('product_id')
            if not secret:
                raise ValueError('No product_id returned by list')
            listing_id = str(item['id'])
            if not listing_id.isdecimal():
                raise ValueError('Invalid listing ID')
            evidence_path = evidence_dir / f'{listing_id}.json'
            if resume and evidence_path.is_file():
                response = json.loads(evidence_path.read_text(encoding='utf8'))
            elif rebuild_only:
                return None, prior_errors.get(listing_id, {'id': listing_id, 'type': 'ReceiptUnavailable', 'evidence': {}})
            else:
                response = read_only_call(client, config, 'alibaba.icbu.product.score.get', {'product_id': secret})
                evidence_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding='utf-8')
            row = summarize_score(item, response)
            row['observed_at_utc'] = datetime.fromtimestamp(evidence_path.stat().st_mtime, timezone.utc).isoformat()
            return row, None
        except Exception as exc:
            evidence = getattr(exc, 'api_evidence', {})
            return None, {'id': str(item.get('id')), 'type': type(exc).__name__, 'evidence': evidence}
    pool = ThreadPoolExecutor(max_workers=3)
    try:
        futures = [pool.submit(read_one, item) for item in selected]
        for future in as_completed(futures):
            row, error = future.result()
            if error: errors.append(error)
            else: rows.append(row)
            print(json.dumps({'processed': len(rows) + len(errors), 'selected': len(selected)}, ensure_ascii=False), flush=True)
    except KeyboardInterrupt:
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)
    rows.sort(key=lambda row: row['id'])
    payload = {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
               'catalog_observed_at_utc': snapshot['observed_at_utc'],
               'catalog_total': snapshot['total_item'], 'selected': len(selected),
               'scored': sum(row['score'] is not None for row in rows),
               'errors': errors, 'complete': len(selected) == len(products) and not errors and all(row['score'] is not None for row in rows),
               'below_5': [row for row in rows if row['score'] is not None and row['score'] < 5], 'items': rows}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'quality.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-items', type=int, help='Limit scores for a smoke test; omission reads every listing')
    parser.add_argument('--resume', action='store_true', help='Resume the complete catalog and saved score receipts in this output directory')
    parser.add_argument('--rebuild-only', action='store_true', help='With --resume, rebuild from saved receipts without any platform requests')
    args = parser.parse_args()
    if args.max_items is not None and args.max_items < 1:
        parser.error('--max-items must be positive')
    if args.rebuild_only and not args.resume:
        parser.error('--rebuild-only requires --resume')
    spec = importlib.util.spec_from_file_location('alibaba_client', CLIENT)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    config = None if args.rebuild_only else client.load_config(client.DEFAULT_CONFIG)
    result = diagnose(client, config, args.output, args.max_items, args.resume, args.rebuild_only)
    print(json.dumps({k: result[k] for k in ('catalog_total', 'selected', 'scored', 'complete')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
