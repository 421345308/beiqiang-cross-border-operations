"""Read-only audit of all six current main-image slots.
Uses current API-derived URLs from the existing machine audit, caches images,
and emits per-slot quantitative flags for human review. No online writes.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
import csv,hashlib,io,json
from PIL import Image,ImageStat,ImageDraw
ROOT=Path(r'C:\Users\spq\Desktop\贝强')
BASE=ROOT/'02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04'
SRC=ROOT/'02_Alibaba运营/06_图片与检查记录/API全量六图复审_2026-09-03_修复后/主图机器审计.csv'
OUT=BASE/'全六图视觉二次审计_2026-09-04'; CACHE=OUT/'cache'; OUT.mkdir(exist_ok=True); CACHE.mkdir(exist_ok=True)
def get(row):
    url=row['url']; f=CACHE/(hashlib.sha1(url.encode()).hexdigest()+'.jpg')
    if not f.exists():
        try: f.write_bytes(urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read())
        except Exception: return row,None,f
    try:return row,Image.open(f).convert('RGB'),f
    except Exception:return row,None,f
def met(im):
    im=im.resize((256,256)); pix=list(im.getdata());
    border=pix[:256]+pix[-256:]+[im.getpixel((x,0)) for x in range(256)]+[im.getpixel((x,255)) for x in range(256)]
    avg=[sum(p[i] for p in border)/len(border) for i in range(3)]
    var=sum(sum((p[i]-avg[i])**2 for i in range(3))**.5 for p in border)/len(border)
    edge=[]
    for y in range(256):
        for x in range(256):
            if x<38 or x>=218 or y<38 or y>=218: edge.append(pix[y*256+x])
    chroma=sum(max(p)-min(p)>40 and min(p)<210 for p in edge)/len(edge)
    dark=sum(max(p)<110 for p in edge)/len(edge)
    return var,chroma,dark
def main():
    rows=list(csv.DictReader(SRC.open(encoding='utf-8-sig',newline='')))
    with ThreadPoolExecutor(max_workers=16) as pool: result=list(pool.map(get,rows))
    out=[]
    for row,im,f in result:
        flags=[]
        if im is None: flags.append('DOWNLOAD_OR_DECODE_ERROR')
        else:
            var,chroma,dark=met(im)
            if float(row.get('occupancy_box_area') or 0)<.20: flags.append('LOW_OCCUPANCY')
            if float(row.get('occupancy_box_area') or 0)>.96: flags.append('EDGE_CROP_OR_FULL_CANVAS')
            if var>30: flags.append('COMPLEX_OR_COLLAGE_BACKGROUND')
            if chroma>.16 or dark>.20: flags.append('EDGE_GRAPHIC_OR_DARK_BACKGROUND')
        row['visual_flags']=';'.join(flags) or 'HEURISTIC_PASS'; row['cache']=str(f); out.append(row)
    fn=OUT/'全六图逐槽视觉筛查.csv'
    with fn.open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    # review subset only; all rows remain in CSV
    flagged=[r for r in out if r['visual_flags']!='HEURISTIC_PASS']
    cards=[]
    for r in flagged:
        try:
            im=Image.open(r['cache']); im.thumbnail((180,180)); card=Image.new('RGB',(320,230),'white');card.paste(im,((180-im.width)//2,2)); d=ImageDraw.Draw(card);d.text((4,185),f"{r['product_id']}  M{r['image_position']}",fill='black');d.text((4,201),r['model'][:30],fill='black');d.text((4,216),r['visual_flags'][:43],fill='red');cards.append(card)
        except: pass
    cols=4; sheet=Image.new('RGB',(cols*320,((len(cards)+cols-1)//cols)*230),(230,230,230))
    for i,c in enumerate(cards):sheet.paste(c,((i%cols)*320,(i//cols)*230))
    sheet.save(OUT/'全六图疑似异常联系表.jpg',quality=90)
    print(json.dumps({'total':len(out),'flagged':len(flagged),'download_errors':sum('DOWNLOAD' in r['visual_flags'] for r in out)},ensure_ascii=False))
if __name__=='__main__':main()
