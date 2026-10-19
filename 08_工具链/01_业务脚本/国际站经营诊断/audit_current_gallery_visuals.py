"""Read-only image audit of an already frozen product.get collection.

Contact sheets are inspection artifacts, never listing assets. Image heuristics
flag candidates; they do not certify cropping, product identity or visual QA.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from io import BytesIO
import hashlib,json,sys
from PIL import Image,ImageOps,ImageDraw
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'99_临时区/商品质量全店复核'

def main():
    sys.stdout.reconfigure(encoding='utf8')
    rows=json.loads((BASE/'全店内容检查.json').read_text(encoding='utf8'))['rows']
    out=BASE/'主图审查';out.mkdir(exist_ok=True);cache=out/'缩略图';cache.mkdir(exist_ok=True)
    galleries={r['id']:json.loads((BASE/'商品'/r['id']/'get.json').read_text(encoding='utf8'))['response']['product']['main_image']['images'] for r in rows}
    urls=list(dict.fromkeys(u for v in galleries.values() for u in v))
    def fetch(u):
        h=hashlib.sha256(u.encode()).hexdigest();p=cache/(h+'.jpg');meta=cache/(h+'.json')
        if p.exists() and meta.exists():return u,json.loads(meta.read_text(encoding='utf8'))
        try:
            with urlopen(Request(u,headers={'User-Agent':'Mozilla/5.0','Accept':'image/jpeg'}),timeout=40)as response:raw=response.read()
            im=Image.open(BytesIO(raw)).convert('RGB');record={'url':u,'dimensions':list(im.size),'raw_sha256':hashlib.sha256(raw).hexdigest(),'preview':p.relative_to(ROOT).as_posix()};ImageOps.contain(im,(520,520)).save(p,quality=93);meta.write_text(json.dumps(record),encoding='utf8');return u,record
        except Exception as e:return u,{'url':u,'error':type(e).__name__}
    with ThreadPoolExecutor(max_workers=8)as pool:
        results={}
        for i,(u,v)in enumerate(pool.map(fetch,urls),1):
            results[u]=v
            if i%100==0:print('IMAGE_READ',i,'/',len(urls),flush=True)
    families={}
    for r in rows:families.setdefault(r['family'],r)
    selected=list(families.values())
    for start in range(0,len(selected),10):
        group=selected[start:start+10];sheet=Image.new('RGB',(1320,len(group)*192),'white');draw=ImageDraw.Draw(sheet)
        for i,row in enumerate(group):
            y=i*192;draw.text((3,y+5),row['family'],fill='black');draw.text((3,y+22),row['id'],fill='black')
            for j,u in enumerate(galleries[row['id']]):
                v=results[u];x=235+j*180
                if v.get('preview'):
                    im=ImageOps.contain(Image.open(ROOT/v['preview']),(174,166));sheet.paste(im,(x+(174-im.width)//2,y+18+(166-im.height)//2));draw.text((x,y+2),f'{j+1} {v["dimensions"]}',fill='black')
                else:draw.text((x,y+20),'READ ERROR',fill='red')
        sheet.save(out/f'家族图库_{start//10+1:02}.jpg',quality=95)
    (out/'图片与商品映射.json').write_text(json.dumps({'scope':len(rows),'families':len(families),'galleries':galleries,'images':list(results.values()),'errors':sum('error'in v for v in results.values()),'status':'CONTACT_SHEETS_READY_NOT_VISUAL_PASS'},ensure_ascii=False,indent=2),encoding='utf8')
    print('VISUAL_AUDIT_CONTACT_SHEETS',len(families),len(results),'ERRORS',sum('error'in v for v in results.values()),flush=True)
if __name__=='__main__':main()
