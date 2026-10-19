"""Download exact public source product photos for inspection, no listing writes."""
from pathlib import Path
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from PIL import Image,ImageOps,ImageDraw
import argparse,json,hashlib,sys,time
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'99_临时区/商品质量全店复核'
def main():
    sys.stdout.reconfigure(encoding='utf8');p=argparse.ArgumentParser();p.add_argument('--families',required=True);args=p.parse_args();sources=json.loads((BASE/'来源复核/当前来源索引.json').read_text(encoding='utf8'))['items']
    for family in args.families.split(','):
        row=next(x for x in sources if family in x['families']);folder=BASE/'补色原图'/family;folder.mkdir(parents=True,exist_ok=True)
        def fetch(pair):
            i,u=pair;file=folder/f'{i:02}.jpg'
            if not file.exists():
                for attempt in range(3):
                    try:
                        with urlopen(Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':row['url'],'Accept':'image/jpeg'}),timeout=40)as response:raw=response.read()
                        break
                    except Exception:
                        if attempt==2:raise
                        time.sleep(attempt+1)
                file.write_bytes(raw)
            im=Image.open(file);return {'index':i,'url':u,'file':file.relative_to(ROOT).as_posix(),'dimensions':list(im.size),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
        with ThreadPoolExecutor(max_workers=4)as pool:items=list(pool.map(fetch,enumerate(row['product_images'],1)))
        for start in range(0,len(items),8):
            group=items[start:start+8];sheet=Image.new('RGB',(1600,550*((len(group)+3)//4)),'white');draw=ImageDraw.Draw(sheet)
            for j,item in enumerate(group):
                im=ImageOps.contain(Image.open(ROOT/item['file']).convert('RGB'),(390,510));x=j%4*400;y=j//4*550;sheet.paste(im,(x+(390-im.width)//2,y+30));draw.text((x+5,y+5),str(item['index'])+' '+str(item['dimensions']),fill='black')
            sheet.save(folder/f'总览_{start//8+1:02}.jpg',quality=95)
        (folder/'来源图片索引.json').write_text(json.dumps({'source_id':row['id'],'url':row['url'],'observed_at':row['at'],'colors':row['colors'],'sizes':row['sizes'],'items':items},ensure_ascii=False,indent=2),encoding='utf8');print(family,'EXACT_SOURCE_IMAGES',len(items),flush=True)
if __name__=='__main__':main()
