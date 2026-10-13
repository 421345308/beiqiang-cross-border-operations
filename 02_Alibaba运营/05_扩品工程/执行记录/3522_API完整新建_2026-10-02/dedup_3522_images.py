from pathlib import Path
import json,requests,hashlib
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageOps,ImageDraw
O=Path(__file__).parent/'3522_execution';D=O/'dedup_images';D.mkdir(exist_ok=True)
rows=json.loads((O/'dedup_near_catalog.json').read_text(encoding='utf-8'))
def get(x):
 p=D/(str(x['id'])+'.jpg');u=x['main_image']['images'][0]
 try:
  if not p.exists():
   r=requests.get(u,timeout=25);r.raise_for_status();p.write_bytes(r.content)
  im=Image.open(p);return {'id':x['id'],'model':x.get('red_model'),'url':u,'path':str(p),'dimensions':list(im.size),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 except Exception as e:return {'id':x['id'],'model':x.get('red_model'),'error_type':type(e).__name__}
with ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(get,rows))
(O/'dedup_image_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
out=Image.new('RGB',(1500,((len(result)+4)//5)*330),'white');d=ImageDraw.Draw(out)
for i,x in enumerate(result):
 cx=i%5*300;cy=i//5*330
 if x.get('path'):out.paste(ImageOps.contain(Image.open(x['path']).convert('RGB'),(290,290)),(cx,cy))
 d.text((cx+5,cy+290),str(x.get('model'))+' '+str(x['id']),fill='black')
out.save(O/'dedup_contact.jpg');print('Verified candidate main photos',sum('path' in x for x in result),'/',len(result),flush=True)
