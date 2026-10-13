from pathlib import Path
import json,shutil,hashlib
from PIL import Image
W=Path(__file__).parent;O=W/'805_execution';rows=json.loads((O/'dedup_image_manifest.json').read_text(encoding='utf-8'))
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
for x in rows:
 if str(x['id'])=='1601969920294':
  p=O/'dedup_images/1601969920294.jpg';shutil.copyfile(W/'3522_execution/official_cdn/M1.jpg',p);x['reuse_provenance']='3522 official CDN M1 URL same token; official_cdn_readback.json plus actual prior visual verification'
 else:p=O/'dedup_images'/(str(x['id'])+'.jpg')
 if p.exists():
  x.update(path=str(p),dimensions=list(Image.open(p).size),sha256=hashlib.sha256(p.read_bytes()).hexdigest());x.pop('error_type',None)
save('dedup_image_manifest.json',rows);print('Confirmed original main images',sum('path' in x for x in rows),'of',len(rows),flush=True)
