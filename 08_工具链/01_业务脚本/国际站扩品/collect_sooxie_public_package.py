"""Collect a specified publicly linked shoe page and product-only photographs."""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit,urljoin
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from PIL import Image,ImageOps,ImageDraw
from datetime import datetime,timezone
import hashlib,json,sys,argparse
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'99_临时区/HR实源替换/货源发现'
def collect(url,resume=False):
    host=urlsplit(url).hostname;assert host and host.endswith('.sooxie.com') and '/detail/'in url
    name=host.split('.')[0]+'_'+url.rstrip('/').split('/')[-1];folder=BASE/name;folder.mkdir(parents=True,exist_ok=True)
    raw=(folder/'source.html').read_bytes()if resume else None
    if raw is None:
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
    old=json.loads((folder/'page.json').read_text(encoding='utf8'))if(folder/'page.json').exists()else None
    if old:assert old['url']==url and old['actual_product_images']==urls,'Changed source photo order needs separate identity review before cache reuse'
    if resume:
        assert old and old['excluded_sidebar_images'];page=old
    else:
        (folder/'source.html').write_bytes(raw);(folder/'text.txt').write_text(text,encoding='utf8')
        page={'url':url,'title':soup.title.get_text(),'observed_at':datetime.now(timezone.utc).isoformat(),'public_text_file':(folder/'text.txt').relative_to(ROOT).as_posix(),'actual_product_images':urls,'excluded_sidebar_images':True,'public_specs_text':details.get_text(' ',strip=True)}
        (folder/'page.json').write_text(json.dumps(page,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    rows=[];photos=folder/'photos';photos.mkdir(exist_ok=True)
    error_file=folder/'图片读取错误.json';errors=json.loads(error_file.read_text(encoding='utf8'))if error_file.exists()else[]
    denied={x['index']for x in errors if x.get('http_status')in [403,429]};consecutive_forbidden=0
    for n,src in enumerate(urls,1):
        path=photos/f'{n:02}.jpg'
        if not path.exists():
            if n in denied:continue
            try:
                with urlopen(Request(src,headers={'User-Agent':'Mozilla/5.0','Referer':url}),timeout=30)as response:path.write_bytes(response.read())
            except HTTPError as exc:
                errors.append({'index':n,'url':src,'http_status':exc.code,'observed_at':datetime.now(timezone.utc).isoformat(),'scope':'Normal public image read failed; this URL not retried. No authentication, TLS or permission change.'})
                error_file.write_text(json.dumps(errors,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
                if exc.code==429:break
                if exc.code==403:
                    consecutive_forbidden+=1
                    if consecutive_forbidden>=3:break
                continue
        consecutive_forbidden=0
        rows.append({'index':n,'url':src,'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'dimensions':list(Image.open(path).size)})
    (folder/'images.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (folder/'图片采集范围.json').write_text(json.dumps({'state':'COMPLETE_PUBLIC_PHOTOS'if len(rows)==len(urls)else'PARTIAL_PUBLIC_PHOTOS','page_image_count':len(urls),'collected_indices':[r['index']for r in rows],'uncollected_indices':[n for n in range(1,len(urls)+1)if n not in {r['index']for r in rows}],'errors_file':error_file.relative_to(ROOT).as_posix()if errors else None,'scope':'Only successfully read and reviewed source frames may be used; missing image never invented. Page observation date preserved on photo-only resume.'},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for start in range(0,len(rows),8):
        sheet=Image.new('RGB',(1600,590*((min(8,len(rows)-start)+3)//4)),'white');draw=ImageDraw.Draw(sheet)
        for j,row in enumerate(rows[start:start+8]):
            im=ImageOps.contain(Image.open(ROOT/row['path']).convert('RGB'),(390,545));x=j%4*400;y=j//4*590;sheet.paste(im,(x+(390-im.width)//2,y+35));draw.text((x+5,y+5),str(row['index'])+' '+name,fill='black')
        sheet.save(folder/f'图审_{start//8+1}.jpg',quality=94)
    print(name,'CURRENT_PUBLIC_PRODUCT_PHOTOS',len(rows),'OF',len(urls),page['public_specs_text'],flush=True)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('urls',nargs='+');parser.add_argument('--resume-photos',action='store_true');args=parser.parse_args()
    with ThreadPoolExecutor(max_workers=min(3,len(args.urls)))as pool:list(pool.map(lambda url:collect(url,args.resume_photos),args.urls))
if __name__=='__main__':sys.stdout.reconfigure(encoding='utf8');main()
