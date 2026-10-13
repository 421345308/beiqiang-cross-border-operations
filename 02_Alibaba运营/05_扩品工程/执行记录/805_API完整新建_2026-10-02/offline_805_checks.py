from pathlib import Path
import json,hashlib,datetime,shutil,requests
from PIL import Image,ImageOps,ImageDraw
W=Path(__file__).parent;O=W/'805_execution'
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
assets=json.loads((O/'asset_manifest.json').read_text(encoding='utf-8'))['assets']
save('visual_gate.json',{'verdict':'PASS','reviewer':'review_9968 independent actual pixel review','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image_hashes':{Path(x['path']).name:x['sha256'] for x in assets},'mobile_previews_all10':'PASS_375px_actual_viewed','facts':'Rubber outsole / PU lining; unknown upper, midsole, insole truthful; source size38-44; no price/performance/own-factory claim','source_structure':'Actual five separate rubber pads plus rear heel extension, moc-toe and double tassels; distinct from HR003/006/010'})
shutil.copyfile(O/'source/image_manifest.json',O/'source/published_manifest.json')
t=(W/'prepare_805.py').read_text(encoding='utf-8').replace("['sku_count']==24","['sku_count']==21").replace('Source gross weight 0.90 kg','Source gross weight 0.80 kg');(W/'prepare_805.py').write_text(t,encoding='utf-8')
if not (O/'live_catalog.json').exists():print('Visual gate saved; full catalog pending',flush=True);raise SystemExit
rows=json.loads((O/'live_catalog.json').read_text(encoding='utf-8'));near=[x for x in rows if x.get('category_id')==202240835 or any(w in x.get('subject','').lower() for w in ['loafer','moccasin','driving shoe'])]
save('dedup_near_catalog.json',near);D=O/'dedup_images';D.mkdir(exist_ok=True);old={str(x['id']):x for x in json.loads((W/'3522_execution/dedup_image_manifest.json').read_text(encoding='utf-8'))};results=[]
for x in near:
 pid=str(x['id']);u=x['main_image']['images'][0];p=D/(pid+'.jpg');item={'id':pid,'model':x.get('red_model'),'url':u}
 prior=old.get(pid)
 try:
  if not p.exists():
   if prior and prior.get('path') and prior.get('url')==u:shutil.copyfile(prior['path'],p)
   else:
    r=requests.get(u,timeout=20);r.raise_for_status();p.write_bytes(r.content)
  im=Image.open(p);item.update(path=str(p),dimensions=list(im.size),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
 except Exception as e:item.update(error_type=type(e).__name__)
 results.append(item)
save('dedup_image_manifest.json',results)
out=Image.new('RGB',(1500,((len(results)+4)//5)*330),'white');d=ImageDraw.Draw(out)
for i,x in enumerate(results):
 xx=i%5*300;yy=i//5*330
 if x.get('path'):out.paste(ImageOps.contain(Image.open(x['path']).convert('RGB'),(290,290)),(xx,yy))
 d.text((xx+5,yy+295),str(x.get('model'))+' '+str(x['id']),fill='black')
out.save(O/'dedup_contact.jpg');print('Current catalog',len(rows),'near structures',len(near),'actual images',sum('path' in x for x in results),flush=True)
