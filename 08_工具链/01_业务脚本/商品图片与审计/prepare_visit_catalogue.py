"""Collect an expanded buyer catalogue from local, source-mapped evidence."""
import argparse
import json
import re
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def short_title(subject):
    s=subject.lower()
    for word,title in [('chelsea','Chelsea Boot'),('boot','Lace Up Boot'),('clog','Casual Clog'),
                       ('mule','Casual Mule'),('slide','Casual Slide'),('sandal','Summer Sandal'),
                       ('loafer','Casual Loafer'),('slip-on','Slip On Casual'),('slip on','Slip On Casual'),
                       ('outdoor','Outdoor Casual Shoe'),('sneaker','Casual Sneaker')]:
        if word in s:return title
    return 'Lace Up Casual Shoe'


def size_text(sizes,eu=True):
    if not sizes:return 'Size details on request'
    if all(str(x).isdigit() and 25<=int(x)<=55 for x in sizes):
        values=sorted(set(int(x) for x in sizes))
        if values==list(range(values[0],values[-1]+1)):
            return ('EU ' if eu else 'Sizes ')+str(values[0])+'-'+str(values[-1])
    return ('EU ' if eu else 'Sizes ')+' / '.join(str(x) for x in sizes)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=args.root;out=args.output;out.mkdir(parents=True,exist_ok=True)
    old=root/'04_客户开发/06_报价与产品册/full_catalog_2026-10-04'
    mapping={x['code']:x for x in read(old/'source_mapping_internal.json') if x.get('identity')}
    ledger=read(root/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json')
    products={x['id']:x for x in ledger['products']};sources={x['id']:x for x in ledger['sources']}
    rows=[];urls=set();excluded=[]
    for item in read(old/'catalogue_public_data.json'):
        row=dict(item);meta=mapping[row['code']];p=products.get(row['code'],{})
        raw=[root/x for x in p.get('raw_packages',[])]
        source_url=meta.get('source_url')
        own=meta['identity']=='OWN_FACTORY_ORIGINAL_PACKAGE'
        if own:
            assert Path(meta['original_package']).is_dir(),row['code']
        elif not any(x.exists() for x in raw) and not source_url:
            excluded.append({'code':row['code'],'reason':'No accessible mapped raw package or confirmed source URL'})
            continue
        model=meta.get('source_model') or meta.get('supplier_model') or row['code']
        if not model.isascii():model=row['code']
        row.update({'image':str(old/row['image']),'origin':'Beiqiang factory' if own else 'Partner-sourced',
                    'model':model,
                    'source_url':source_url,'evidence':meta.get('facts') or meta.get('evidence'),
                    'group':'Beiqiang factory styles' if own else 'More casual & knit styles'})
        if source_url:urls.add(source_url)
        rows.append(row)
    # HR replacement evidence has current photographs, color/size facts and adopted source IDs.
    base=root/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
    for fact_path in sorted(base.glob('*/来源事实.json')):
        code=fact_path.parent.name;p=products.get(code,{})
        if p.get('source_state')!='ADOPTED':continue
        fact=read(fact_path);fact=fact.get('source',fact)
        url=fact.get('url');source=sources.get(p.get('adopted_source_id'),{})
        if not url or url!=source.get('url') or url in urls:continue
        plan_path=fact_path.parent/'事实与页面计划.json';manifest_path=fact_path.parent/'素材清单.json'
        if not plan_path.exists() or not manifest_path.exists():continue
        plan=read(plan_path);manifest=read(manifest_path)
        if manifest.get('state')!='VISUAL_PASS':continue
        sku=next((v for k,v in manifest['items'].items() if k.startswith('SKU_')),None)
        if not sku:continue
        image=root/sku['path']
        if not image.is_file():continue
        clean=out/'source_images'/f'{code}.jpg';clean.parent.mkdir(exist_ok=True)
        im=Image.open(image).convert('RGB');im=im.crop((0,0,im.width,round(im.height*0.85)))
        im.save(clean,quality=91)
        titles=plan.get('titles',{})
        subject=next(iter(titles.values()),'Casual shoe') if isinstance(titles,dict) else str(titles)
        title=short_title(subject)
        group='Sandals, loafers & easy wear' if any(x in title for x in ['Sandal','Loafer','Clog','Mule','Slide']) else 'More casual & knit styles'
        if 'Boot' in title:group='Outdoor & boot collection'
        rows.append({'code':code,'model':fact.get('artno') or source.get('model') or code,
                     'title':title,'size':size_text(fact.get('sizes_eu') or plan.get('sizes') or []),
                     'colors':fact.get('colors') or plan.get('colors') or [],'notes':'',
                     'image':str(clean),'origin':'Partner-sourced','group':group,
                     'source_url':url,'evidence':str(fact_path),'source_photo':str(image)})
        urls.add(url)
    # Original Luqi source photographs; retain only adopted sources, not candidate products.
    base=root/'02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08'
    research={x['url']:x for x in read(base/'分类总清单.json')['products']}
    omit={'1680','2132','2409','2415','2772','9705','25019','2575','2576'}
    for p in ledger['products']:
        source=sources.get(p.get('adopted_source_id'),{})
        if p['source_state']!='ADOPTED' or not source.get('supplier','').startswith('路崎'):continue
        model=source['model'];url=source['url']
        if url in urls or model in omit:continue
        raw=base/f'{model}准备/01_产品来源原图'
        photos=sorted(x for x in raw.glob('*.jpg') if not x.name.startswith('contact'))
        if not photos or url not in research:continue
        facts=research[url]
        listed=next((x for x in ledger['listings'] if x['product_id']==p['id'] and x.get('current_platform_fields',{}).get('title')),None)
        subject=listed['current_platform_fields']['title'] if listed else ''
        title=short_title(subject)
        group='Outdoor & boot collection' if 'Boot' in title or 'Outdoor' in title else 'More casual & knit styles'
        # Public color labels are not translated speculatively. Supply the exact size range only.
        rows.append({'code':p['id'],'model':model,'title':title,'size':size_text(facts.get('sizes',[])),
                     'colors':[],'notes':'Color options on request.','image':str(photos[0]),
                     'origin':'Partner-sourced','group':group,'source_url':url,
                     'evidence':str(base/'分类总清单.json'),'source_photo':str(photos[0])})
        urls.add(url)
    corrections={'HR035':'High Top Casual Sneaker','HR057':'Sock Style Slip On',
                 'HR061':'Lace Up Ankle Shoe','HR062':'Textile Casual Slip On',
                 'HR066':'Sock Style High Top','LQ-0323F':'Lace Up Ankle Shoe',
                 'LQ-1628':'Lined Casual High Top'}
    for row in rows:
        if row['code'] in corrections:row['title']=corrections[row['code']]
        title=row['title'].lower()
        if 'junior' in title:
            row['group']='Junior size styles'
        elif row['origin']=='Partner-sourced' and any(x in title for x in ['loafer','mule','clog','slide','sandal','mary jane']):
            row['group']='Sandals, loafers & easy wear'
    assert {'BQ008','BQ009'}<={r['code'] for r in rows}
    assert len({r['code'] for r in rows})==len(rows)
    payload={'styles':rows,'excluded':excluded,'ledger_date':ledger['updated_on']}
    (out/'catalogue_inventory.local.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    for start in range(0,len(rows),25):
        sheet=Image.new('RGB',(1500,1500),'#eeeeee');d=ImageDraw.Draw(sheet)
        for j,item in enumerate(rows[start:start+25]):
            im=ImageOps.contain(Image.open(item['image']).convert('RGB'),(285,255));x=j%5*300;y=j//5*300
            sheet.paste(im,(x+(300-im.width)//2,y));d.text((x+8,y+260),item['code']+' / '+item['model'],fill='black')
            d.text((x+8,y+278),item['title'],fill='black')
        sheet.save(out/f'review_{start//25}.jpg')
    print('Styles:',len(rows),'Factory:',sum(x['origin']=='Beiqiang factory' for x in rows),'Excluded:',excluded)


if __name__=='__main__':main()
