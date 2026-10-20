"""Read every active SKU colour image, preserving sibling-specific bindings."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from io import BytesIO
from PIL import Image,ImageOps,ImageDraw,ImageFont
import json,hashlib,sys,time
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s

def main():
    sys.stdout.reconfigure(encoding='utf8');raw=s.ROOT/'99_临时区/商品质量全店复核/SKU颜色审查';raw.mkdir(parents=True,exist_ok=True);plan=s.load(s.PLAN_FILE);entries={};missing=[];undefined=[];ids=[]
    for cp in plan['items']:
        for pid in cp['ids']:
            if pid in cp['exclusions']:continue
            ids.append(pid);f=s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid/'formal_get.json';p=s.load(f)['response']['product']
            for axis in p.get('product_sku',{}).get('sku_attributes',[]):
                for value in axis['values']:
                    label=value.get('system_value_name')or''
                    if not label or 'unspecified'in label.lower()or'未指定'in label:undefined.append({'id':pid,'attribute':axis['attribute_id'],'value_id':value['value_id']})
                    if str(axis['attribute_id'])!='191288010':continue
                    url=value.get('image_url')
                    if not url:missing.append({'id':pid,'family':cp['family'],'colour':label});continue
                    key=(cp['family'],label,url);row=entries.setdefault(key,{'family':cp['family'],'colour':label,'url':url,'ids':[]});row['ids'].append(pid)
    urls=list(dict.fromkeys(r['url']for r in entries.values()))
    def fetch(u):
        key=hashlib.sha256(u.encode()).hexdigest();meta=raw/(key+'.json');file=raw/(key+'.img');preview=raw/(key+'.jpg')
        if meta.exists()and preview.exists():return u,s.load(meta)
        try:
            for attempt in range(3):
                try:
                    with urlopen(Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=35)as response:body=response.read()
                    break
                except Exception:
                    if attempt==2:raise
                    time.sleep(attempt+1)
            file.write_bytes(body);im=Image.open(BytesIO(body)).convert('RGBA');white=Image.new('RGBA',im.size,'white');white.alpha_composite(im);rgb=white.convert('RGB');ImageOps.contain(rgb,(500,500)).save(preview,quality=95);v={'url':u,'raw_sha256':hashlib.sha256(body).hexdigest(),'pixel_sha256_on_white':hashlib.sha256(rgb.tobytes()).hexdigest(),'dimensions':list(im.size),'preview':s.rel(preview),'white_alpha_matte':True};s.save(meta,v);return u,v
        except Exception as e:return u,{'url':u,'error':type(e).__name__}
    images={}
    with ThreadPoolExecutor(max_workers=4)as pool:
        for n,(u,v)in enumerate(pool.map(fetch,urls),1):
            images[u]=v
            if n%100==0:print('COLOUR_IMAGE_READ',n,len(urls),flush=True)
    families={}
    for row in entries.values():families.setdefault(row['family'],[]).append(row)
    try:font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    except OSError:font=ImageFont.load_default()
    rows=[]
    for fam,values in families.items():
        for start in range(0,len(values),6):rows.append((fam,values[start:start+6]))
    for start in range(0,len(rows),10):
        group=rows[start:start+10];sheet=Image.new('RGB',(1720,len(group)*235),'white');draw=ImageDraw.Draw(sheet)
        for i,(fam,values)in enumerate(group):
            y=i*235;draw.text((5,y+8),fam,fill='black',font=font)
            for j,row in enumerate(values):
                x=220+j*250;v=images[row['url']];draw.text((x,y+3),row['colour'][:28],fill='black',font=font)
                if v.get('preview'):
                    im=ImageOps.contain(Image.open(s.ROOT/v['preview']),(240,198));sheet.paste(im,(x,y+29))
                else:draw.text((x,y+80),'READ ERROR',fill='red',font=font)
        sheet.save(raw/('色图复核_'+str(start//10+1).zfill(2)+'.jpg'),quality=97)
    result={'at':s.now(),'scope_ids':len(ids),'families':len(families),'distinct_family_colour_URL_bindings':len(entries),'unique_urls':len(urls),'sheets':(len(rows)+9)//10,'state':'CONTACT_SHEETS_READY_NOT_COLOUR_ACCEPTANCE','missing_images':missing,'undefined_sku_labels':undefined,'read_errors':[v for v in images.values()if'error'in v],'bindings':list(entries.values()),'image_metadata':list(images.values())};s.save(s.BASE/'颜色绑定复核.json',result);print(json.dumps({k:v for k,v in result.items()if k not in('bindings','image_metadata')},ensure_ascii=False))

if __name__=='__main__':main()
