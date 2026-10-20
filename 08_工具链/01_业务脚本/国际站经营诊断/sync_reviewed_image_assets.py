"""Index exact uploaded masters and current formal colour bindings without network access."""
from pathlib import Path
from collections import defaultdict
import sys
from PIL import Image
sys.path.insert(0,str(Path(__file__).parent))
import revise_catalog_content as s
import schema_publish_contract as c


def main():
    sys.stdout.reconfigure(encoding='utf8')
    cachefile=s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json'
    cache=s.load(cachefile);added=0
    for folder in ('图库重做','配色与尺码修正'):
        for bankfile in (s.BASE/folder).glob('*/图片银行.json'):
            bank=s.load(bankfile)
            for row in bank.get('items',{}).values():
                if row.get('state')!='UPLOADED' or not row.get('url') or not row.get('file'):continue
                file=s.ROOT/row['file'];assert file.is_file()and s.sha(file)==row['sha256']
                with Image.open(file)as im:width,height=im.size
                old=cache['assets'].get(row['url'])
                if old:assert old['sha256']==row['sha256'],'Existing URL changed master'
                else:added+=1
                cache['assets'][row['url']]={'state':'SAVED','file':row['file'],'sha256':row['sha256'],'bytes':file.stat().st_size,'width':width,'height':height,'upload_evidence':s.rel(bankfile)}
    cache['saved_urls']=len(cache['assets']);cache['unique_files']=len({v['sha256']for v in cache['assets'].values()if v.get('sha256')})
    cache['content_media_revision']={'at':s.now(),'scope':'Exact locally reviewed uploaded masters, indexed from successful image-bank receipts. Does not assert every bank asset is currently bound.'}
    s.save(cachefile,cache)
    native={c._created_image_identity(u):r for u,r in cache['assets'].items()if r.get('file')and(s.ROOT/r['file']).is_file()}
    reg=s.load(s.ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json')
    current={str(p['id'])for p in s.load(s.RAW/'全店图片续修/当前目录/catalog.json')['products']};groups=defaultdict(dict);missing=[]
    for listing in reg['listings']:
        pid=listing['id']
        if pid not in current or pid in s.PROTECTED:continue
        snap=s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid/'formal_get.json'
        p=s.load(snap)['response']['product']
        if p['status']!='approved'or p['display']!='Y':continue
        axis=next((a for a in p['product_sku']['sku_attributes']if str(a['attribute_id'])=='191288010'),None)
        rows=[]
        for value in axis['values']if axis else[]:
            url=value.get('image_url');photo=native.get(c._created_image_identity(url))
            row={'colour':value['system_value_name'],'url':url,'native':photo}
            rows.append(row)
            if not photo:missing.append({'id':pid,'colour':row['colour'],'url':url})
        groups[listing['product_id']][pid]={'formal_file':s.rel(snap),'colours':rows}
    out={'at':s.now(),'scope':'Current exact per-ID formal colour image manifest. Binding contents are facts; visual acceptance remains in the source-specific repair evidence. Historical mislabelled filenames are not current colour truth.','families':dict(groups),'missing_native':missing}
    s.save(s.BASE/'当前颜色图片清单.json',out)
    print('INDEXED_NEW_UPLOADS',added,'CURRENT_FAMILIES',len(groups),'MISSING',len(missing))

if __name__=='__main__':main()
