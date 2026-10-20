"""Build current per-family image review sheets from exact formal CDN bindings."""
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
import sys,argparse
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s
import schema_publish_contract as c

def main():
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser();ap.add_argument('--families',required=True);a=ap.parse_args()
    registry=s.load(s.ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json');cache=s.load(s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json')['assets'];by_identity={c._created_image_identity(url):r for url,r in cache.items()if r.get('file')and(s.ROOT/r['file']).exists()}
    out=s.ROOT/'99_临时区/商品质量全店复核/整组现图';records=[]
    for family in a.families.split(','):
        p=next(x for x in registry['products']if x['id']==family)
        ids=[x['id']for x in registry['listings']if x['product_id']==family and x['id']not in s.PROTECTED]
        selected=[]
        for pid in ids:
            f=s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid/'formal_get.json'
            if not f.exists():continue
            got=s.load(f)['response']['product']
            if got['status']=='approved'and got['display']=='Y':selected.append((pid,got))
        if not selected:continue
        pid,got=selected[0];images=[('M'+str(i+1),u)for i,u in enumerate(got['main_image']['images'])]+[('D'+str(i+1),r['image_url'])for i,r in enumerate(got['struct_detail']['detail_image']['images'])]
        sheet=Image.new('RGB',(2400,530*((len(images)+5)//6)),'white');draw=ImageDraw.Draw(sheet);row={'family':family,'canonical_id':pid,'sibling_ids':[x[0]for x in selected],'images':[]}
        for i,(role,url)in enumerate(images):
            record=by_identity.get(c._created_image_identity(url),{});f=s.ROOT/record.get('file','NOT_FOUND');x=i%6*400;y=i//6*530
            draw.text((x+8,y+8),family+' '+pid+' '+role,fill='black')
            if f.is_file():
                native=Image.open(f).convert('RGBA');matte=Image.new('RGBA',native.size,'white');matte.alpha_composite(native);thumb=ImageOps.contain(matte.convert('RGB'),(390,470));sheet.paste(thumb,(x+(400-thumb.width)//2,y+32));record={**record,'dimensions':list(native.size)}
            else:draw.text((x+10,y+100),'MISSING NATIVE FILE',fill='red')
            row['images'].append({'role':role,'url':url,'file':record.get('file'),'dimensions':record.get('dimensions'),'sha256':record.get('sha256')})
        out.mkdir(parents=True,exist_ok=True);sheet.save(out/(family+'.jpg'),quality=95);s.save(out/(family+'.json'),row);records.append({'family':family,'native_missing':sum(not r['file']for r in row['images']),'images':len(images)})
    print(records)

if __name__=='__main__':main()
