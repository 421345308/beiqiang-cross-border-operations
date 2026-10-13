"""Validate and persist actual normal-browser observations by product ID.

Localized DOM is compared with a manually reviewed reference saved by the
browser. No API response is used to assert that a public image has loaded.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import replace_company_bundle as op


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--observations', required=True)
    args = parser.parse_args()
    source = op.load(op.ROOT / args.observations)
    reference = op.load(op.PHASE / '公开验收参考.json')
    assert source['method'] == reference['method'] == 'cua_repl normal page DOM'
    assert source['asset_version'] == reference['asset_version'] == 8
    assert len(reference['faqPairs']) == 8
    aliases = op.aliases()
    mapped = []
    for image in reference['images']:
        role, asset = aliases[image['url'].removeprefix('https:')]
        mapped.append((asset, image))
    assert {asset for asset, image in mapped} == {'C1','C2','C3','C4','C5','C6'}
    items = []
    failures = []
    seen = set()
    for row in source['items']:
        pid = row['id']
        assert pid not in seen
        seen.add(pid)
        passed = ('_'+pid+'.html' in row['url'] and row['introMatch']
                  and row['faqCount'] == 8 and row['companyImageCount'] == 6
                  and all(row['faqPairMatches'])
                  and all(x['count'] == 1 and x['loaded'] for x in row['images']))
        if not passed:
            failures.append({'id':pid,'url':row['url'],'at':row['observedAt']})
            op.save(op.folder(pid)/'latest_public_observation.json', row)
            continue
        assert {x['asset'] for x in row['images']} == {x[0] for x in mapped}
        expanded = dict(row)
        by_asset = dict(mapped)
        expanded['images'] = [{**x, 'url':by_asset[x['asset']]['url'],
                               'width':by_asset[x['asset']]['width'],
                               'height':by_asset[x['asset']]['height']}
                              for x in row['images']]
        expanded['localized_reference'] = 'V8/公开验收参考.json'
        expanded['introComparison'] = 'Exact normalized rendered Chinese text to the manually reviewed reference; approved English company name remains the canonical seller identity.'
        expanded['localization_notice'] = 'Alibaba Chinese auto-translation renders Beiqiang as 北强. The public supplier header uses the correct English legal name; this is a display translation issue, not a seller copy change.'
        items.append(expanded)
    staging = (op.ROOT / '99_临时区/HR实源替换/公开验收已核观察.json')
    op.save(staging, {**source, 'items':items})
    subprocess.run([sys.executable,str(Path(__file__).with_name('save_company_bundle_public.py')),
                    '--observations',str(staging)],check=True)
    print('OBSERVED_PUBLIC_PASS',len(items),'PENDING',json.dumps(failures))


if __name__ == '__main__':
    main()
