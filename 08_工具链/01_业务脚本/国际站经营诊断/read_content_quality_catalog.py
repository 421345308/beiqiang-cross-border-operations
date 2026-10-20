"""Read-only current catalog, product fields and one exact public source page."""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from urllib.parse import urljoin,urlsplit
import argparse,importlib.util,json,sys
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'99_临时区/商品质量全店复核'
sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/国际站扩品'))
from read_only_catalog import read_only_call,fetch_catalog

def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def now():return datetime.now(timezone.utc).isoformat()
def client():
 spec=importlib.util.spec_from_file_location('api',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api);api.http_json=api.native_http_json;return api,api.load_config(api.DEFAULT_CONFIG)

def source():
 url='https://baiyou877.sooxie.com/detail/2482094'
 with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30)as response:raw=response.read()
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'M001_source.html').write_bytes(raw);soup=BeautifulSoup(raw,'html.parser');details=soup.select_one('.shop-details');assert details
 images=[]
 for e in soup.select('#photoBig img,#details img'):
  src=urljoin(url,e.get('data-url')or e.get('src')or'')
  if urlsplit(src).hostname=='images.xiecdn.com'and src not in images:images.append(src)
 data={'url':url,'at':now(),'title':soup.title.get_text(),'colors':[x.get_text(' ',strip=True)for x in soup.select('#color em')],'sizes':[x.get_text(' ',strip=True)for x in soup.select('#size em')],'specs':details.get_text(' ',strip=True),'product_images':images,'scope':'Anonymous exact public source; no login, purchase or external mutation.'};save(OUT/'M001_source.json',data);(OUT/'M001_source_text.txt').write_text(soup.get_text(' ',strip=True),encoding='utf8');print(json.dumps(data,ensure_ascii=False),flush=True)

def collect(full=False):
 api,cfg=client();OUT.mkdir(parents=True,exist_ok=True)
 if full:catalog=fetch_catalog(api,cfg,OUT/'目录');ids=[str(p['id'])for p in catalog['products']]
 else:ids=['1601970169467']
 results=[]
 def one(pid):
  dest=OUT/'商品'/pid/'get.json'
  if dest.exists():
   old=json.loads(dest.read_text(encoding='utf8'))
   if old.get('observed_at','').startswith(datetime.now(timezone.utc).date().isoformat())and old.get('response',{}).get('product'):return {'id':pid,'state':'CURRENT_SAVED'}
  try:
   r=read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});assert r.get('product');save(dest,{'observed_at':now(),'id':pid,'response':r});return {'id':pid,'state':'SAVED','status':r['product']['status']}
  except Exception as e:return {'id':pid,'state':'ERROR','type':type(e).__name__}
 with ThreadPoolExecutor(max_workers=4)as pool:
  for result in pool.map(one,ids):
   results.append(result)
   if len(results)%40==0 or len(ids)==1:print(json.dumps({'processed':len(results),'total':len(ids),'last':result,'errors':sum(x['state']=='ERROR'for x in results)}),flush=True)
 save(OUT/'完整读取核验.json',{'at':now(),'items':results,'complete':len(results)==len(ids)and all(x['state']!='ERROR'for x in results)});print('FORMAL_COLLECTION',len(results),'ERRORS',sum(x['state']=='ERROR'for x in results),flush=True)

def photos():
 from PIL import Image,ImageOps,ImageDraw
 import hashlib
 data=json.loads((OUT/'M001_source.json').read_text(encoding='utf8'));folder=OUT/'M001原始图';folder.mkdir(exist_ok=True);rows=[]
 for i,url in enumerate(data['product_images'],1):
  p=folder/(str(i).zfill(2)+'.jpg')
  if not p.exists():
   with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':data['url']}),timeout=30)as response:p.write_bytes(response.read())
  rows.append({'index':i,'url':url,'file':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'dimensions':list(Image.open(p).size)})
 save(OUT/'M001原始图清单.json',rows)
 for start in range(0,len(rows),8):
  group=rows[start:start+8];sheet=Image.new('RGB',(1600,560*((len(group)+3)//4)),'white');draw=ImageDraw.Draw(sheet)
  for j,row in enumerate(group):
   im=ImageOps.contain(Image.open(ROOT/row['file']).convert('RGB'),(390,520));x=j%4*400;y=j//4*560;sheet.paste(im,(x+(390-im.width)//2,y+30));draw.text((x+5,y+5),str(row['index']),fill='black')
  sheet.save(OUT/('M001来源总览'+str(start//8+1)+'.jpg'),quality=95)
 print('M001_PHOTOS_SAVED',len(rows),flush=True)

def sources():
 registry=json.loads((ProductRegistry(ROOT)).read_text(encoding='utf8'));audit=json.loads((OUT/'全店内容检查.json').read_text(encoding='utf8'));families={r['family']for r in audit['rows']};products={p['id']:p for p in registry['products']};links={s['id']:s for s in registry['sources']};targets={}
 for f in families:
  product=products.get(f,{})
  keys=[product.get('adopted_source_id'),product.get('reference_source_id')]+[x.get('source_id')for x in product.get('source_routes_by_color',{}).values()]
  for sid in keys:
   if sid and sid in links and urlsplit(links[sid]['url']).hostname.endswith('sooxie.com'):targets.setdefault(sid,{'source':links[sid],'families':[]})['families'].append(f)
 def one(pair):
  sid,row=pair;dest=OUT/'来源复核'/f'{sid}.json'
  if dest.exists():
   existing=json.loads(dest.read_text(encoding='utf8'));existing['families']=sorted(set(row['families']));save(dest,existing);return existing
  url=row['source']['url'];result={'id':sid,'url':url,'families':sorted(set(row['families'])),'at':now()}
  try:
   with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35)as response:soup=BeautifulSoup(response.read(),'html.parser')
   detail=soup.select_one('.shop-details');assert detail
   result.update(state='EXACT_SOURCE_READ',title=soup.title.get_text(' ',strip=True),colors=[x.get_text(' ',strip=True)for x in soup.select('#color em')],sizes=[x.get_text(' ',strip=True)for x in soup.select('#size em')],specs=detail.get_text(' ',strip=True),product_images=list(dict.fromkeys(urljoin(url,x.get('data-url')or x.get('src')or'')for x in soup.select('#photoBig img,#details img')if urlsplit(urljoin(url,x.get('data-url')or x.get('src')or'')).hostname=='images.xiecdn.com')))
  except Exception as e:result.update(state='READ_FAILED_NO_SUPPLY_CONCLUSION',error=type(e).__name__)
  save(dest,result);return result
 results=[]
 with ThreadPoolExecutor(max_workers=4)as pool:
  for row in pool.map(one,targets.items()):
   results.append(row)
   if len(results)%25==0:print('SOURCE_READ',len(results),'/',len(targets),flush=True)
 save(OUT/'来源复核/当前来源索引.json',{'at':now(),'items':results,'scope':'Exact adopted routes only, observation not proof of stock; no inferred automatic SKU append.'});print('SOURCE_READ_COMPLETE',len(results),'ERRORS',sum(x['state']!='EXACT_SOURCE_READ'for x in results),flush=True)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf8');p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['source','sources','one','full','photos']);a=p.parse_args();source()if a.mode=='source'else sources()if a.mode=='sources'else photos()if a.mode=='photos'else collect(a.mode=='full')
