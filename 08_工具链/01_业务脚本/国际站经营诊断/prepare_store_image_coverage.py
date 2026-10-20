"""Freeze current catalog image coverage and all sibling M1 review sheets."""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
from collections import Counter
from PIL import Image,ImageDraw,ImageOps
import sys
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s
import schema_publish_contract as c

def main():
    sys.stdout.reconfigure(encoding='utf8');catalog=s.load(s.RAW/'全店图片续修/当前目录/catalog.json');current={str(r['id'])for r in catalog['products']};reg=s.load(ProductRegistry(s.ROOT));cache=s.load(s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json')['assets'];native={c._created_image_identity(u):r for u,r in cache.items()if r.get('file')and(s.ROOT/r['file']).is_file()}
    rows=[];m1={};missing=[];problems=[]
    for l in reg['listings']:
        pid=l['id']
        if pid not in current or pid in s.PROTECTED:continue
        snap=s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid/'formal_get.json'
        if not snap.exists():missing.append({'id':pid,'reason':'NO_FORMAL_SNAPSHOT'});continue
        p=s.load(snap)['response']['product']
        if p['status']!='approved'or p['display']!='Y':continue
        main=p['main_image']['images'];detail=[r['image_url']for r in p['struct_detail']['detail_image']['images']];identity=c._created_image_identity(main[0]);photo=native.get(identity)
        row={'id':pid,'family':l['product_id'],'formal_file':s.rel(snap),'main_count':len(main),'product_detail_count':len(detail),'main_image':main[0],'state':'AWAITING_IMAGE_ACCEPTANCE'}
        if len(main)!=6:problems.append({'id':pid,'reason':'MAIN_COUNT','count':len(main)})
        if len(set(c._created_image_identity(u)for u in main))!=len(main):problems.append({'id':pid,'reason':'EXACT_MAIN_DUPLICATE'})
        if photo:
            im=Image.open(s.ROOT/photo['file']);row['main_dimensions']=list(im.size);row['native_file']=photo['file'];row['sha256']=photo['sha256'];g=m1.setdefault(photo['sha256'],{'photo':photo,'bindings':[]});g['bindings'].append({'id':pid,'family':l['product_id']})
            if min(im.size)<800:problems.append({'id':pid,'reason':'SMALL_M1_SOURCE','dimensions':list(im.size)})
        else:missing.append({'id':pid,'reason':'NATIVE_M1_MISSING','url':main[0]})
        rows.append(row)
    out=s.ROOT/'99_临时区/商品质量全店复核/全店首图';out.mkdir(parents=True,exist_ok=True);items=sorted(m1.values(),key=lambda r:(r['bindings'][0]['family'],r['bindings'][0]['id']));sheets=[]
    for start in range(0,len(items),12):
        sheet=Image.new('RGB',(2000,1530),'white');draw=ImageDraw.Draw(sheet)
        for i,g in enumerate(items[start:start+12]):
            x=i%4*500;y=i//4*510;b=g['bindings'][0];draw.text((x+8,y+7),str(start+i)+' '+b['family']+' '+b['id']+' ('+str(len(g['bindings']))+' IDs)',fill='black');native_im=Image.open(s.ROOT/g['photo']['file']).convert('RGBA');matte=Image.new('RGBA',native_im.size,'white');matte.alpha_composite(native_im);im=ImageOps.contain(matte.convert('RGB'),(485,470));sheet.paste(im,(x+(500-im.width)//2,y+32))
        f=out/(str(start//12+1)+'.jpg');sheet.save(f,quality=96);sheets.append({'file':s.rel(f),'start':start,'end':min(start+12,len(items)),'state':'REVIEW_PENDING'})
    s.save(out/'首图索引.json',{'items':items,'sheets':sheets});s.save(s.BASE/'全店图片覆盖.json',{'at':s.now(),'actual_catalog_ids':len(current),'eligible_snapshots':len(rows),'unique_m1_photos':len(items),'missing':missing,'structural_diagnostics':problems,'sheets':sheets,'items':rows,'scope':'All current eligible original IDs, including every sibling M1. Technical checks and contact-sheet review do not by themselves prove native image semantics or product performance.'});print('ELIGIBLE',len(rows),'UNIQUE_M1',len(items),'SHEETS',len(sheets),'MISSING',len(missing),'DIAGNOSTICS',len(problems))

if __name__=='__main__':main()
