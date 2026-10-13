"""Freeze a reviewed public actual-shoe package once, validating junction targets."""
from pathlib import Path
import argparse,json,re,hashlib,shutil

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'


def main():
    p=argparse.ArgumentParser();p.add_argument('family');args=p.parse_args()
    folder=BASE/args.family;plan=json.loads((folder/'事实与页面计划.json').read_text(encoding='utf8'))
    candidate=ROOT/'99_临时区/HR实源替换/货源发现'/plan['candidate']
    page=json.loads((candidate/'page.json').read_text(encoding='utf8'));rows=json.loads((candidate/'images.json').read_text(encoding='utf8'))
    assert page['url']==plan['source_url']and page['excluded_sidebar_images']
    specs=page['public_specs_text'];assert re.search(r'货号：\s*'+re.escape(plan['source_artno'])+r'\s',specs)
    price=float(re.search(r'价格：\s*([\d.]+)',specs).group(1));assert price==plan['source_price_cny']
    assert all(c in specs for c in plan['source_color_labels'])
    text=(candidate/'text.txt').read_text(encoding='utf8');assert '一件代发'in text or'上门拿货'in text
    raw_root=(ROOT/'01_产品资产/01_原始数据包').resolve();dest=ROOT/plan['source_assets_root']
    assert dest.resolve().is_relative_to(raw_root)and dest.resolve()!=raw_root
    dest.mkdir(parents=True,exist_ok=True);copied=[]
    for row in rows:
        src=ROOT/row['path'];assert hashlib.sha256(src.read_bytes()).hexdigest()==row['sha256']
        target=dest/f"{row['index']:02}.jpg"
        if target.exists():assert hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']
        else:shutil.copy2(src,target)
        copied.append({**row,'path':target.relative_to(ROOT).as_posix()})
    for name in ['source.html','text.txt']:
        src=candidate/name;target=dest/name
        if target.exists():assert src.read_bytes()==target.read_bytes()
        else:shutil.copy2(src,target)
    source={'url':plan['source_url'],'supplier':plan['supplier'],'artno':plan['source_artno'],
            'price_cny':price,'colors':plan['colors'],'source_color_labels':plan['source_color_labels'],
            'sizes_eu':plan['sizes'],'observed_on':plan['source_date'],
            'procurement_entry':'Current public single-pair fulfillment and supplier business enquiry entry; actual stock and transaction terms confirmed per order',
            'current_public_specs':specs,'images':copied}
    file=dest/'source.json'
    if file.exists():assert json.loads(file.read_text(encoding='utf8'))==source
    else:file.write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    proof={'family':args.family,'source':source,'raw_package':plan['source_assets_root'],
           'materials_evidence':plan['materials_evidence'],
           'identity_review':'All current product-photo sheets reviewed; specific original shoe geometry/colour/closure retained, sidebar recommendations excluded',
           'dedup_review':plan['dedup'],'SKU_scope':'Confirmed numeric EU choices only; no inferred US/UK/foot-length conversion',
           'IP_route':'No recognised global shoe mark on selected frames; actual shoe markings retained; no unbranded or own-factory-production claim'}
    (folder/'来源事实.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(args.family,'REVIEWED_RAW_SOURCE_FROZEN',len(copied))


if __name__=='__main__':main()
