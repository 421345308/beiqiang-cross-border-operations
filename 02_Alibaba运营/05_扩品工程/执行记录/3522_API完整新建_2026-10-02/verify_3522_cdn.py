from pathlib import Path
import requests,json,hashlib
from PIL import Image,ImageChops,ImageStat,ImageOps,ImageDraw
from concurrent.futures import ThreadPoolExecutor
O=Path(__file__).parent/'3522_execution';D=O/'official_cdn';D.mkdir(exist_ok=True)
rows=json.loads((O/'upload_ledger.json').read_text(encoding='utf-8'))['uploads']
def get(x):
 p=D/(x['name']+'.jpg')
 try:
  if not p.exists():
   r=requests.get(x['official_url'],timeout=25);r.raise_for_status();p.write_bytes(r.content)
  h=hashlib.sha256(p.read_bytes()).hexdigest();im=Image.open(p).convert('RGB');original=Image.open(x['path']).convert('RGB');same=im.size==original.size;mean=ImageStat.Stat(ImageChops.difference(im,original)).mean if same else None
  return {'name':x['name'],'path':str(p),'official_url':x['official_url'],'sha256':h,'matches_uploaded_bytes':h==x['sha256'],'dimensions':list(im.size),'source_dimensions':list(original.size),'mean_absolute_channel_difference':mean,'pixel_comparison':'PASS_SAME_SIZE_SMALL_RECOMPRESSION_DIFFERENCE' if same and max(mean)<3 else 'REVIEW_REQUIRED','limits':'Small numerical difference supports recompression consistency; actual visual review still required.'}
 except Exception as e:return {'name':x['name'],'error_type':type(e).__name__,'status':'NETWORK_READ_PENDING'}
with ThreadPoolExecutor(max_workers=3) as pool:a=list(pool.map(get,rows))
(O/'official_cdn_readback.json').write_text(json.dumps(a,indent=2),encoding='utf-8')
assert all(x.get('pixel_comparison')=='PASS_SAME_SIZE_SMALL_RECOMPRESSION_DIFFERENCE' for x in a)
out=Image.new('RGB',(1500,((len(a)+4)//5)*330),'white');d=ImageDraw.Draw(out)
for i,x in enumerate(a):
 cx=i%5*300;cy=i//5*330;out.paste(ImageOps.contain(Image.open(x['path']).convert('RGB'),(290,290)),(cx,cy));d.text((cx+5,cy+295),x['name'],fill='black')
out.save(O/'official_cdn_contact.jpg')
print('13 official CDN files: same dimensions, small JPEG recompression differences retained; contact ready',flush=True)
