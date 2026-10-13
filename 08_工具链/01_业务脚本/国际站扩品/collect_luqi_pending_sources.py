"""Read exact pending Luqi source pages/photos without publishing or overwriting.

Queue rows retain their publication state. This is evidence collection only;
source identity, colour naming, deduplication and image quality need review.
"""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from PIL import Image, ImageOps, ImageDraw
from bs4 import BeautifulSoup
import hashlib, json, sys

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08'
QUEUE=BASE/'质量复核_2026-10-09/全分类处理队列.json'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def now():return datetime.now(timezone.utc).isoformat()
def collect(row):
    style=row['style'];url=row['source']
    assert row['publication_state']=='PENDING_STYLE_AND_QUALITY_REVIEW'
    assert urlsplit(url).hostname=='luqi.sooxie.com'and '/detail/'in url
    folder=BASE/(style+'准备');folder.mkdir(exist_ok=True)
    index=folder/'01_产品来源原图/当前来源图像索引.json'
    if index.exists()or(folder/'当前家族来源图像索引.json').exists():
        return {'style':style,'state':'EXISTING_SOURCE_EVIDENCE_KEEP','no_write':True}
    original=folder/'01_产品来源原图';original.mkdir(exist_ok=True)
    assert not list(original.glob('*.jpg')),'Unindexed originals require reconciliation; never overwrite.'
    html_file=folder/'当前公开来源HTML.html'
    assert not html_file.exists(),'Existing unindexed page requires reconciliation; never overwrite.'
    try:
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30)as response:raw=response.read()
    except HTTPError as e:
        result={'style':style,'source':url,'state':'PUBLIC_PAGE_READ_FAILED','http_status':e.code,'observed_at':now()}
        save(folder/'当前来源采集问题.json',result);print(style,result['state'],e.code,flush=True);return result
    html_file.write_bytes(raw);soup=BeautifulSoup(raw,'html.parser');text=soup.get_text('\n',strip=True)
    (folder/'当前来源文本.txt').write_text(text,encoding='utf8')
    if '商品已下架'in text or not soup.select_one('.shop-details'):
        result={'style':style,'source':url,'state':'SOURCE_WITHDRAWN_OR_PRODUCT_DETAILS_ABSENT','observed_at':now()}
        save(folder/'当前来源采集问题.json',result);print(style,result['state'],flush=True);return result
    assert '货号'in text and style in text
    urls=[]
    for photo in soup.select('#photoBig img,#details img'):
        u=photo.get('data-url')or photo.get('src')
        if u:
            u=urljoin(url,u)
            if urlsplit(u).hostname=='images.xiecdn.com'and u not in urls:urls.append(u)
    assert urls and ('一件代发'in text or '上门拿货'in text)
    rows=[];consecutive=0
    for i,u in enumerate(urls,1):
        f=original/f'{i:02}.jpg';assert not f.exists()
        try:
            with urlopen(Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':url}),timeout=30)as response:photo=response.read()
            import io
            im=Image.open(io.BytesIO(photo));im.load();f.write_bytes(photo)
            rows.append({'index':i,'url':u,'path':f.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(photo).hexdigest(),'dimensions':list(im.size),'status':'READABLE'});consecutive=0
        except HTTPError as e:
            rows.append({'index':i,'url':u,'status':'READ_FAILED','http_status':e.code,'observed_at':now()})
            consecutive=consecutive+1 if e.code==403 else 0
            if e.code==429 or consecutive>=3:break
    ok=[x for x in rows if x['status']=='READABLE']
    result={'style':style,'source':url,'observed_at':now(),'source_HTML_sha256':hashlib.sha256(raw).hexdigest(),'collection':'PUBLIC_HTTPS_NORMAL_TLS_PRODUCT_ONLY','excluded_sidebar_images':True,'source_image_count':len(urls),'rows':rows,'collected_images':len(ok),'state':'CURRENT_SOURCE_PHOTOS_COLLECTED_PENDING_REVIEW'if len(ok)==len(urls)else'PARTIAL_SOURCE_PHOTOS_PENDING_REVIEW','public_specs_text':soup.select_one('.shop-details').get_text(' ',strip=True),'no_publish':True,'no_stock_or_width_inference':True}
    save(index,result)
    for start in range(0,len(ok),8):
        sheet=Image.new('RGB',(1600,590*((min(8,len(ok)-start)+3)//4)),'white');draw=ImageDraw.Draw(sheet)
        for j,x in enumerate(ok[start:start+8]):
            im=ImageOps.contain(Image.open(ROOT/x['path']).convert('RGB'),(390,545));a=j%4*400;b=j//4*590
            sheet.paste(im,(a+(390-im.width)//2,b+35));draw.text((a+5,b+5),f'{style} original {x["index"]}',fill='black')
        sheet.save(original/f'contact_{start//8}.jpg',quality=94)
    print(style,result['state'],len(ok),'OF',len(urls),flush=True)
    return {'style':style,'state':result['state'],'evidence':index.relative_to(ROOT).as_posix(),'collected_images':len(ok)}

def main():
    sys.stdout.reconfigure(encoding='utf8');queue=load(QUEUE)
    pending=[r for r in queue['rows']if r['publication_state']=='PENDING_STYLE_AND_QUALITY_REVIEW']
    with ThreadPoolExecutor(max_workers=3)as pool:results=list(pool.map(collect,pending))
    current=load(QUEUE)
    assert current==queue,'Queue changed during collection; keep evidence and reconcile explicitly.'
    for result in results:
        if result.get('no_write'):continue
        row=next(x for x in current['rows']if x['style']==result['style'])
        row['source_review']=result['state']
        if result.get('evidence'):
            row.update(source_collection='CURRENT_SOURCE_COLLECTED',image_cache='CURRENT_EXACT_SOURCE_IMAGES_COLLECTED_PENDING_REVIEW',current_source_evidence=result['evidence'])
        fact=BASE/(result['style']+'准备')/'当前来源与色码核对.json'
        if fact.exists():
            row.update(source_fact_review='LOCAL_SOURCE_FACTS_DRAFT_NOT_PUBLISHED',source_fact_evidence=fact.relative_to(ROOT).as_posix())
    current['source_collection_observed_at']=now();save(QUEUE,current)
    print('SOURCE_ONLY_NO_CREATE',sum(not x.get('no_write')for x in results),'CURRENT_PREPARATIONS',flush=True)
if __name__=='__main__':main()
