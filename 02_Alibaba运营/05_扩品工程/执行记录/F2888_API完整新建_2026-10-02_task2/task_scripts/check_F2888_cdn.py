from pathlib import Path
import json,hashlib,datetime,concurrent.futures
from urllib.request import Request,urlopen
from PIL import Image
W=Path(__file__).resolve().parent;O=W/'F2888_execution';D=O/'cdn_actual';D.mkdir(exist_ok=True)
assert json.loads((O/'resume_authorization.json').read_text(encoding='utf-8'))['authorized']
uploads=json.loads((O/'upload_ledger.json').read_text(encoding='utf-8'))['uploads'];company=json.loads((O/'company_v3_manifest.json').read_text(encoding='utf-8'))
rows=[{'name':x['name'],'url':x['official_url'],'sha256':x['sha256'],'kind':'product_or_SKU'} for x in uploads]+[{'name':x['role'],'url':x['official_url'],'sha256':x['sha256'],'kind':'approved_v3_company'} for x in company]
def check(row):
 extension='.png' if row['kind']=='product_or_SKU' else '.jpg';file=D/(row['name']+extension)
 try:
  with urlopen(Request(row['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as response:raw=response.read();status=response.status
  file.write_bytes(raw);actual=hashlib.sha256(raw).hexdigest();pixels=list(Image.open(file).size)
  return dict(row,HTTP_status=status,file=str(file),actual_sha256=actual,pixels=pixels,exact_hash_match=actual==row['sha256'])
 except Exception as error:return dict(row,error_type=type(error).__name__,error=str(error),exact_hash_match=False)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(check,rows))
report={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'Independent download from returned official Alibaba image-bank URLs; no source image processing','checks':results,'verdict':'PASS' if all(x['exact_hash_match'] for x in results) else 'INCOMPLETE_OR_HASH_DIFFERENCE','scope':'CDN asset identity only, not public page layout or SKU click QA'}
(O/'cdn_independent_acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(report['verdict'],sum(x['exact_hash_match'] for x in results),'of',len(results),'official CDN assets match approved exact hashes.',flush=True)
