"""Collect a specified publicly linked shoe page and product-only photographs."""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit,urljoin
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from PIL import Image,ImageOps,ImageDraw
from datetime import datetime,timezone
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'99_临时区/HR实源替换/货源发现'
def collect(url):
    host=urlsplit(url).hostname;assert host and host.endswith('.sooxie.com') and '/detail/'in url
    name=host.split('.')[0]+'_'+url.rstrip('/').split('/')[-1];folder=BASE/name;folder.mkdir(parents=True,exist_ok=True)
    with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30)as response:raw=response.read()
    soup=BeautifulSoup(raw,'html.parser');details=soup.select_one('.shop-details');assert details
    text=soup.get_text(' ',strip=True);assert '商品已下架'not in text,'Source is currently offline'
    urls=[]
    for photo in soup.select('#photoBig img,#details img'):
        src=photo.get('data-url')or photo.get('src')
        if not src:continue
        src=urljoin(url,src)
        if urlsplit(src).hostname=='images.xiecdn.com' and src not in urls:urls.append(src)
    assert urls and ('一件代发'in text or '上门拿货'in text)
    (folder/'source.html').write_bytes(raw);(folder/'text.txt').write_text(text,encoding='utf8')
    page={'url':url,'title':soup.title.get_text(),'observed_at':datetime.now(timezone.utc).isoformat(),'public_text_file':(folder/'text.txt').relative_to(ROOT).as_posix(),'actual_product_images':urls,'excluded_sidebar_images':True,'public_specs_text':details.get_text(' ',strip=True)}
    (folder/'page.json').write_text(json.dumps(page,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    rows=[];photos=folder/'photos';photos.mkdir(exist_ok=True)
    for n,src in enumerate(urls,1):
        path=photos/f'{n:02}.jpg'
        if not path.exists():
            with urlopen(Request(src,headers={'User-Agent':'Mozilla/5.0','Referer':url}),timeout=30)as response:path.write_bytes(response.read())
        rows.append({'index':n,'url':src,'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'dimensions':list(Image.open(path).size)})
    (folder/'images.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for start in range(0,len(rows),8):
        sheet=Image.new('RGB',(1600,590*((min(8,len(rows)-start)+3)//4)),'white');draw=ImageDraw.Draw(sheet)
        for j,row in enumerate(rows[start:start+8]):
            im=ImageOps.contain(Image.open(ROOT/row['path']).convert('RGB'),(390,545));x=j%4*400;y=j//4*590;sheet.paste(im,(x+(390-im.width)//2,y+35));draw.text((x+5,y+5),str(row['index'])+' '+name,fill='black')
        sheet.save(folder/f'图审_{start//8+1}.jpg',quality=94)
    print(name,'CURRENT_PUBLIC_PRODUCT_PHOTOS',len(rows),page['public_specs_text'],flush=True)
def main():
    with ThreadPoolExecutor(max_workers=min(3,len(sys.argv)-1))as pool:list(pool.map(collect,sys.argv[1:]))
if __name__=='__main__':sys.stdout.reconfigure(encoding='utf8');main()
