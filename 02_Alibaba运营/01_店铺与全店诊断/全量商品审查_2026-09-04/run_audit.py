import json, subprocess, pathlib, concurrent.futures, csv, re

ROOT = pathlib.Path(r'C:\Users\spq\Desktop\贝强')
CLI = ROOT / '.agents' / 'skills' / 'alibaba-openapi-operator' / 'scripts' / 'alibaba_openapi.py'
OUT = pathlib.Path(__file__).parent

def call(method, **params):
    args = ['python', str(CLI), 'call', method] + [f'{k}={v}' for k,v in params.items()]
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90)
    try: return json.loads(p.stdout)
    except Exception: return {'_call_error': p.stderr[-1000:], '_stdout_tail': p.stdout[-1000:]}

pages=[]
for page in range(1, 30):
    x=call('alibaba.icbu.product.list', language='en_US', pageNo=page, pageSize=10)
    pages.append(x)
    if not x.get('products'): break
    if page*10 >= int(x.get('total_item',0)): break
# The list endpoint currently returns page 1 regardless of supplied page params.
# Use the latest local full catalog snapshot for the complete ID set, while retaining
# the fresh API page response for any matching metadata.
snap = ROOT / '02_Alibaba运营' / '06_图片与检查记录' / 'API全量图片审计_2026-09-03' / '线上商品目录.json'
snapshot = json.loads(snap.read_text(encoding='utf-8')) if snap.exists() else []
fresh = {str(p.get('id')): p for x in pages for p in x.get('products',[]) if p.get('id') is not None}
products=[]
for p in snapshot:
    pid=str(p.get('product_id'))
    products.append(fresh.get(pid, {'id':p.get('product_id'),'product_id':p.get('encrypted_product_id'),'subject':p.get('title'),'red_model':p.get('model'),'status':p.get('status'),'display':'Y','main_image':{'images':[]},'category_id':None,'group_name':None,'pc_detail_url':p.get('pc_detail_url'),'gmt_modified':None,'struct_detail_product':None}))
for p in fresh.values():
    if str(p.get('id')) not in {str(x.get('id')) for x in products}: products.append(p)
ids=[]
for p in products:
    if p.get('id') not in ids: ids.append(p['id'])

def get_one(pid):
    return pid, call('alibaba.icbu.product.get', product_id=pid, language='en_US')
details={}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    for pid, data in ex.map(get_one, ids): details[str(pid)] = data

def count_urls(obj):
    return len(obj.get('images',[])) if isinstance(obj,dict) else 0

records=[]
seen_products=set()
for p in products:
    pid=str(p.get('id')); d=details.get(pid,{})
    if pid in seen_products: continue
    seen_products.add(pid)
    prod=d.get('product',{}) if isinstance(d,dict) else {}
    sku=(prod.get('product_sku') or {}).get('skus',[]) or []
    attrs=sku and (prod.get('product_sku') or {}).get('sku_attributes',[]) or []
    colors=[]; sizes=[]
    for a in attrs:
        vals=[v.get('system_value_name') for v in a.get('values',[]) if v.get('system_value_name') is not None]
        name=(a.get('attribute_name') or '').lower()
        if 'color' in name: colors=vals
        if 'size' in name: sizes=vals
    sd=prod.get('struct_detail') or {}
    di=sd.get('detail_image') or {}; ci=sd.get('company_image') or {}
    trade=prod.get('sourcing_trade') or {}
    images=(p.get('main_image') or {}).get('images',[]) or (prod.get('main_image') or {}).get('images',[])
    bad=[u for u in images if not re.match(r'^https://sc04\.alicdn\.com/kf/[^/]+\.(?:jpg|jpeg|png|webp)$',u,re.I)]
    records.append({'productId':p.get('id'),'encryptedProductId':p.get('product_id'),'title':p.get('subject'),'modelNumber':p.get('red_model'),'categoryId':p.get('category_id'),'categoryName':p.get('group_name'),'status':p.get('status'),'display':p.get('display'),'mainImageCount':len(images),'skuColorCount':len(colors),'skuColors':' | '.join(colors),'skuSizeCount':len(sizes),'skuSizes':' | '.join(sizes),'skuTotalCount':len(sku),'detailType':'STRUCTURED' if p.get('struct_detail_product') else 'HTML/UNKNOWN','productDetailImageCount':len(di.get('images',[])),'companyImageCount':len(ci.get('images',[])),'video':'not returned by product.list/get','fobMinPrice':trade.get('fob_min_price'),'fobMaxPrice':trade.get('fob_max_price'),'currency':trade.get('fob_currency'),'moq':trade.get('min_order_quantity'),'unit':trade.get('min_order_unit_type'),'leadTime100Pairs':next((x.get('process_period') for x in trade.get('deliver_periods',[]) if x.get('quantity')==100),None),'package':'not returned by product.list/get','badUrlCount':len(bad),'badUrls':' | '.join(bad),'url':p.get('pc_detail_url'),'gmtModified':p.get('gmt_modified')})

(OUT/'api_product_list_pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'api_product_get_details.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'full_product_audit.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'full_product_audit.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=records[0].keys()); w.writeheader(); w.writerows(records)
print(json.dumps({'products':len(records),'output':str(OUT)},ensure_ascii=False))
