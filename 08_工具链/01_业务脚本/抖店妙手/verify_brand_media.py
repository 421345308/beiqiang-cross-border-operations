"""Read-only CDN pixel acceptance for an existing, verified brand revision."""
import hashlib
import json
import sys
import time
import io
from http.client import IncompleteRead
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from PIL import Image, ImageChops, ImageStat

root = Path('09_国内电商/抖店')
# Domestic product CDN follows the workspace's approved direct route. Keep TLS verification.
media_opener = build_opener(ProxyHandler({}))
plan = json.loads((root / '数据/品牌首发商品.json').read_text(encoding='utf-8'))
for model in (sys.argv[1:] or list(plan['models'])):
    product = plan['models'].get(model) or plan.get('expansion_candidates', {}).get('models', {}).get(model)
    if product is None:
        raise ValueError('Unknown reviewed model: ' + model)
    evidence = root / product['publication']['private_content_evidence']
    file = evidence / 'verification.json'
    verification = json.loads(file.read_text(encoding='utf-8'))
    if not verification['verified']:
        raise ValueError('Backend verification is not complete')
    base = verification['base']['productInfo']
    rows = []
    for role, urls, assets in [('main', base['pic'], product['main_assets']),
                               ('detail', base['descriptionImgList'], product['detail_files'])]:
        if len(urls) != len(assets):
            raise ValueError('Media count differs')
        for index, (url, asset) in enumerate(zip(urls, assets), 1):
            rows.append(dict(role=role, index=index, url=url, expected=asset['path']))
    for index, binding in enumerate(product['media_binding']['sku_color_files'], 1):
        value = next(v for spec in base['specs'] if str(spec['propertyId']) == '2752'
                     for v in spec['values'] if v['name'] == binding['color'])
        picture = next(v for v in base['specPics'] if str(v['specDetailId']) == str(value['id']))
        rows.append(dict(role='color', index=index, name=binding['color'], url=picture['pic'], expected=binding['path']))
    target = evidence / 'platform-media'
    target.mkdir(exist_ok=True)
    for row in rows:
        parsed = urlparse(row['url'])
        if parsed.scheme != 'https' or not parsed.hostname.endswith('.ecombdimg.com'):
            raise ValueError('Unexpected platform media host')
        actual = target / f"{row['role']}-{row['index']}.img"
        if not actual.exists():
            for attempt in range(3):
                try:
                    with media_opener.open(Request(row['url'], headers={'User-Agent': 'BeiqiangMediaQuality/1.0'}), timeout=30) as response:
                        content = response.read()
                    with Image.open(io.BytesIO(content)) as downloaded:
                        downloaded.verify()
                    pending = actual.with_suffix('.tasktmp')
                    pending.write_bytes(content)
                    pending.replace(actual)
                    break
                except (URLError, IncompleteRead, TimeoutError, ConnectionError) as error:
                    if isinstance(error, HTTPError) and error.code not in (429, 502, 503, 504):
                        raise
                    if attempt == 2:
                        raise
                    time.sleep(attempt + 1)
        with Image.open(row['expected']) as original, Image.open(actual) as published:
            original, published = original.convert('RGB'), published.convert('RGB')
            same_size = original.size == published.size
            if same_size:
                difference = ImageChops.difference(original, published)
                mean = sum(ImageStat.Stat(difference).mean) / 3
                exact = difference.getbbox() is None
            else:
                mean, exact = None, False
            row.update(actual=str(actual), same_size=same_size, exact_pixels=exact, mean_absolute_error=mean,
                       passed=same_size and mean <= 2,
                       actual_sha256=hashlib.sha256(actual.read_bytes()).hexdigest())
    result = dict(model=model, passed=all(r['passed'] for r in rows), rows=rows,
                  criterion='Same dimensions and RGB mean absolute error <=2/255; ordered per formal readback; no rescaling')
    (evidence / 'media-comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    verification['pixelComparison'] = 'PASSED' if result['passed'] else 'FAILED'
    file.write_text(json.dumps(verification, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(model=model, passed=result['passed'], checked=len(rows), exact=sum(r['exact_pixels'] for r in rows))))
    if not result['passed']:
        raise SystemExit(2)
