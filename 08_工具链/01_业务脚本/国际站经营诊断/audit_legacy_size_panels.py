"""Read-only exact-image matching for historical inferred-size panels.

Do not infer live impact merely from a family appearing in the old generator.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from io import BytesIO
from PIL import Image,ImageOps,ImageDraw
import json,hashlib,sys,time
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s

def main():
    sys.stdout.reconfigure(encoding='utf8');audit_file=s.BASE/'历史尺码图来源复核.json';audit=s.load(audit_file);cp=s.load(s.PLAN_FILE);plans={x['family']:x for x in cp['items']};root=s.ROOT;raw=root/'99_临时区/商品质量全店复核/历史尺码图';raw.mkdir(parents=True,exist_ok=True);jobs={};families={}
    for fam in audit['candidate_families']:
        if fam=='BQ018':continue
        p=plans[fam];asset=root/p['source_evidence'][0];asset=asset.parent;local={}
        for f in (asset/'02_详情页').glob('*size*'):
            if f.is_file()and f.suffix.lower()in('.jpg','.jpeg','.png'):
                im=Image.open(f).convert('RGB');local[f.as_posix()]={'sha256':s.sha(f),'pixels':hashlib.sha256(im.tobytes()).hexdigest(),'size':list(im.size)}
        families[fam]={'local_images':local,'ids':{}}
        for pid in p['ids']:
            canonical=root/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid/'formal_get.json'
            if canonical.exists():v=s.load(canonical)['response']['product'];observed=s.load(canonical)['observed_at_utc']
            else:
                frozen=s.load(root/'99_临时区/商品质量全店复核/商品'/pid/'get.json');v=frozen['response']['product'];observed=frozen['observed_at']
            urls=[r['image_url']for r in v['struct_detail']['detail_image']['images']];families[fam]['ids'][pid]={'observed_at':observed,'status':v['status'],'display':v['display'],'urls':urls}
            for u in urls:jobs[u]=None
    def fetch(url):
        h=hashlib.sha256(url.encode()).hexdigest();f=raw/(h+'.img');meta=raw/(h+'.json')
        if f.exists()and meta.exists():return url,s.load(meta)
        try:
            for attempt in range(3):
                try:
                    with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35)as r:body=r.read()
                    break
                except Exception:
                    if attempt==2:raise
                    time.sleep(attempt+1)
            f.write_bytes(body);im=Image.open(BytesIO(body)).convert('RGB');preview=raw/(h+'.jpg');ImageOps.contain(im,(500,500)).save(preview,quality=94);v={'url':url,'sha256':hashlib.sha256(body).hexdigest(),'pixels':hashlib.sha256(im.tobytes()).hexdigest(),'size':list(im.size),'preview':s.rel(preview)};s.save(meta,v);return url,v
        except Exception as e:return url,{'url':url,'error':type(e).__name__}
    with ThreadPoolExecutor(max_workers=4)as pool:images=dict(pool.map(fetch,jobs))
    matches=[]
    for fam,row in families.items():
        for pid,listing in row['ids'].items():
            for u in listing['urls']:
                image=images[u]
                for f,local in row['local_images'].items():
                    if image.get('sha256')==local['sha256']or(image.get('pixels')==local['pixels']and image.get('size')==local['size']):
                        matches.append({'family':fam,'id':pid,'url':u,'local_file':s.rel(Path(f)),'match':'EXACT_BYTES'if image['sha256']==local['sha256']else'EXACT_PIXELS','requires_visual_classification':'safe'in Path(f).stem.lower(),'status':listing['status'],'display':listing['display'],'observed_at':listing['observed_at']})
    audit.update(at=s.now(),image_match_scope='Latest local formal snapshots; immutable image URLs fetched directly. Exact byte/pixel matches only, no family-wide impact inference.',exact_matches=matches,matched_ids=len(set(x['id']for x in matches)),downloaded=len(images),download_errors=[v for v in images.values()if'error'in v]);s.save(audit_file,audit)
    selected=[x for x in matches if not x['requires_visual_classification']];unique={x['url']:x for x in selected}
    for start in range(0,len(unique),12):
        group=list(unique.values())[start:start+12];sheet=Image.new('RGB',(1500,((len(group)+3)//4)*395),'white');draw=ImageDraw.Draw(sheet)
        for i,row in enumerate(group):
            x=(i%4)*375;y=(i//4)*395;im=ImageOps.contain(Image.open(root/images[row['url']]['preview']),(365,365));sheet.paste(im,(x,y+25));draw.text((x+5,y+5),row['family']+' '+row['id'],fill='black')
        sheet.save(raw/('对应尺码图_'+str(start//12+1)+'.jpg'),quality=96)
    print(json.dumps({'exact_matched_ids':audit['matched_ids'],'matches':len(matches),'unique_matched_images':len(unique),'read_errors':len(audit['download_errors'])},ensure_ascii=False))

if __name__=='__main__':main()
