"""Read-only contact sheets of current gallery images, with exact URL/slot records."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import hashlib
import json
from pathlib import Path
from urllib.request import Request,urlopen
from PIL import Image,ImageDraw
import argparse

ROOT=Path(__file__).resolve().parents[2]
DETAILS=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'
OUT=ROOT/'99_临时区/商品对应/图审'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--all-links',action='store_true');args=parser.parse_args()
    data=json.loads((ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json').read_text(encoding='utf-8-sig'))
    listings={x['id']:x for x in data['listings']}
    targets=data['bq_ease_optimization']['targets']
    chosen={}
    for pid in targets:
        family=listings[pid]['product_id']
        if args.all_links:chosen[pid]=pid;continue
        if family not in chosen or '-R' in listings[pid]['model']:
            chosen[family]=pid
    OUT.mkdir(parents=True,exist_ok=True)
    cachefile=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json'
    assets=json.loads(cachefile.read_text(encoding='utf-8')).get('assets',{}) if cachefile.exists() else {}
    tasks=[]
    for family,pid in sorted(chosen.items()):
        p=json.loads((DETAILS/pid/'formal_get.json').read_text(encoding='utf-8'))['response']['product']
        for slot,url in enumerate(p['main_image']['images']):
            tasks.append((family,pid,slot,url))
    def fetch(task):
        family,pid,slot,url=task
        record=assets.get(url,{})
        path=ROOT/record['file'] if record.get('file') else None
        if path and path.is_file():
            raw=path.read_bytes()
        else:
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'image/jpeg'}),timeout=25) as response:raw=response.read()
        return task,Image.open(BytesIO(raw)).convert('RGB')
    pictures={}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for task,pic in pool.map(fetch,tasks):pictures[task[:3]]=pic
    families=sorted(chosen)
    for start in range(0,len(families),4):
        chunk=families[start:start+4]
        sheet=Image.new('RGB',(6*280,len(chunk)*310),'#f1f3f3')
        draw=ImageDraw.Draw(sheet)
        for row,family in enumerate(chunk):
            pid=chosen[family]
            for slot in range(6):
                pic=pictures.get((family,pid,slot))
                if pic is None:continue
                pic.thumbnail((270,270))
                x=slot*280+(280-pic.width)//2;y=row*310+30
                sheet.paste(pic,(x,y))
                draw.text((slot*280+8,row*310+8),f'{family} {pid} M{slot+1}',fill='#111111')
        sheet.save(OUT/f'{"links" if args.all_links else "gallery"}_{start//4+1}.jpg',quality=90)
    (OUT/('link_slot_urls.json' if args.all_links else 'slot_urls.json')).write_text(json.dumps({'families':chosen,'images':[{'family':family,'id':pid,'slot':slot+1,'url':url} for family,pid,slot,url in tasks]},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'families':len(chosen),'images':len(tasks),'sheets':(len(chosen)+3)//4},ensure_ascii=False))


if __name__=='__main__':main()
