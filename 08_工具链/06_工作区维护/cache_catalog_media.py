"""Save current Alibaba image references once per content hash, with per-ID roles."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from PIL import Image
import argparse

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / '02_Alibaba运营/05_扩品工程/数据/目录对账'
DETAILS = AREA / '当前平台目录/商品'
CACHE = ROOT / '01_产品资产/05_平台当前素材'


def image_urls(value):
    found = set()
    if isinstance(value, dict):
        for nested in value.values():
            found |= image_urls(nested)
    elif isinstance(value, list):
        for nested in value:
            found |= image_urls(nested)
    elif isinstance(value, str):
        for url in re.findall(r'https?://[^\s\"<>]+', value):
            url = url.rstrip('),;')
            host = (urlsplit(url).hostname or '').lower()
            if host.endswith('.alicdn.com') and re.search(r'\.(jpg|jpeg|png|webp|gif)(\?|$)',url,re.I):
                found.add(url)
    return found


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=12)
    args=parser.parse_args()
    if not 1 <= args.workers <= 16:
        raise ValueError('Use bounded 1-16 image download workers')
    if (ROOT/'01_产品资产').resolve() != Path(r'E:\贝强大文件\01_产品资产').resolve():
        raise ValueError('Actual asset target changed')
    CACHE.mkdir(parents=True,exist_ok=True)
    manifest_file = AREA/'当前素材清单.json'
    old = json.loads(manifest_file.read_text(encoding='utf-8')) if manifest_file.exists() else {'assets':{}}
    by_id = {}
    urls = set()
    for file in DETAILS.glob('*/formal_get.json'):
        p = json.loads(file.read_text(encoding='utf-8'))['response']['product']
        roles = {
            'main': image_urls(p.get('main_image')),
            'details': image_urls((p.get('struct_detail') or {}).get('detail_image')),
            'company': image_urls((p.get('struct_detail') or {}).get('company_image')),
            'sku': image_urls(p.get('product_sku')),
            'html': image_urls(p.get('product_desc', '')),
        }
        by_id[file.parent.name] = {k:sorted(v) for k,v in roles.items()}
        for value in roles.values():
            urls |= value
    assets = old['assets']
    def fetch(url):
        record = assets.get(url)
        if record and (ROOT/record.get('file','')).is_file():
            path = ROOT/record['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() == record.get('sha256'):
                return url,record
        try:
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'image/jpeg,image/png'}),timeout=25) as response:
                raw = response.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:
                raise ValueError('Image exceeds limit')
            pic = Image.open(BytesIO(raw))
            pic.verify()
            pic = Image.open(BytesIO(raw))
            sha = hashlib.sha256(raw).hexdigest()
            ext = {'JPEG':'.jpg','PNG':'.png','WEBP':'.webp','GIF':'.gif','AVIF':'.avif'}.get(pic.format)
            if not ext:
                raise ValueError('Unrecognized image format')
            path = CACHE/(sha+ext)
            if not path.exists():
                path.write_bytes(raw)
            return url,{'state':'SAVED','file':path.relative_to(ROOT).as_posix(),'sha256':sha,'bytes':len(raw),'width':pic.width,'height':pic.height}
        except Exception as exc:
            return url,{'state':'ERROR','error_type':type(exc).__name__}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(fetch,url) for url in sorted(urls)]
        for n,job in enumerate(as_completed(jobs),1):
            url,record = job.result()
            assets[url] = record
            if n%100==0:
                print(json.dumps({'processed':n,'urls':len(urls)},ensure_ascii=False),flush=True)
                manifest_file.write_text(json.dumps({'assets':assets,'products':by_id,'state':'IN_PROGRESS','scope':'当前正式字段图片本地缓存'},ensure_ascii=False,indent=2),encoding='utf-8')
    current_assets = {url:assets[url] for url in sorted(urls)}
    out = {'scope':'当前正式回读内官方图片字段；不下载视频，不生成或改动实物图；每个内容哈希只保存一份媒体文件','products':by_id,'assets':current_assets,'urls':len(urls),'saved_urls':sum(a['state']=='SAVED' for a in current_assets.values()),'unique_files':len({a['file'] for a in current_assets.values() if a.get('file')}),'errors':sum(a['state']=='ERROR' for a in current_assets.values())}
    manifest_file.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in {'products','assets'}},ensure_ascii=False))


if __name__ == '__main__':
    main()
