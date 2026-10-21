"""Index current main/product-detail images for local text diagnostics, not approval."""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
import hashlib,sys
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s
import schema_publish_contract as c

def main():
    d=s.load(ProductRegistry(s.ROOT));cache=s.load(s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json')['assets'];identities={c._created_image_identity(u):r for u,r in cache.items()if r.get('file')and(s.ROOT/r['file']).is_file()};items={};missing=[];ids=[]
    current={str(r['id'])for r in s.load(s.RAW/'全店图片续修/当前目录/catalog.json')['products']}
    for listing in d['listings']:
        pid=listing['id'];f=s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid/'formal_get.json'
        if pid in s.PROTECTED or pid not in current or not f.exists():continue
        p=s.load(f)['response']['product']
        if p['status']!='approved'or p['display']!='Y':continue
        ids.append(pid)
        for role,u in [('M'+str(i+1),u)for i,u in enumerate(p['main_image']['images'])]+[('D'+str(i+1),r['image_url'])for i,r in enumerate(p['struct_detail']['detail_image']['images'])]:
            identity=c._created_image_identity(u);key=hashlib.sha256(str(identity).encode()).hexdigest();native=identities.get(identity,{})
            row=items.setdefault(key,{'key':key,'url':u,'file':str((s.ROOT/native['file']).resolve())if native.get('file')else None,'sha256':native.get('sha256'),'dimensions':[native.get('width'),native.get('height')],'bindings':[]})
            row['bindings'].append({'family':listing['product_id'],'id':pid,'role':role})
            if not row['file']:missing.append({'id':pid,'url':u,'role':role})
    result={'at':s.now(),'scope_ids':len(ids),'unique_images':len(items),'native_missing':missing,'items':list(items.values())}
    s.save(s.RAW/'全店图片续修/OCR输入.json',result);print('CURRENT_OCR_INDEX',len(ids),len(items),'MISSING',len(missing))

if __name__=='__main__':main()
