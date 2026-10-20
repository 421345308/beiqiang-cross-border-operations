"""Build editable colour/EU diagrams using unchanged current, reviewed photographs.

This is a native SVG information layout, not photographic retouching. The raster
photographs are embedded without cropping, recolouring, resampling or reconstruction.
"""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
from html import escape
import argparse,base64,hashlib,json,math,mimetypes,subprocess,sys,re
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s
import schema_publish_contract as c
from repair_source_assortment import axes,key
from svg_photo_reference import photo_data_url

NODE='C:/Users/spq/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'

def eu_number(label):
    match=re.fullmatch(r'(?:EU\s*)?(\d{2})',label.strip(),flags=re.I)
    assert match,'Unsupported size label: '+label
    return match.group(1)

def diagram(rows,detail,include_sizes=True):
    horizontal=len(rows)==2
    cols=1 if horizontal else 2 if detail or len(rows)<=4 else 3
    cardw=(900-(cols-1)*22)/cols;cardh=360 if detail else 325
    rowcount=math.ceil(len(rows)/cols);height=185+rowcount*(cardh+20)+100
    if not detail:height=max(height,1000)
    ystart=175;header='Colour & Size Selection'if include_sizes else'Colour Selection'
    subtitle=f'{len(rows)} colour options'+(' · European sizes'if include_sizes else'')
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1000" height="{height}" viewBox="0 0 1000 {height}">',
        '<rect width="1000" height="100%" fill="#ffffff"/>',
        f'<text x="50" y="74" fill="#092b50" font-family="Arial,sans-serif" font-size="48" font-weight="700">{escape(header)}</text>',
        '<rect x="50" y="99" width="76" height="6" rx="3" fill="#f47720"/>',
        f'<text x="50" y="142" fill="#4f6072" font-family="Arial,sans-serif" font-size="25">{escape(subtitle)}</text>']
    all_sizes=[]
    for i,r in enumerate(rows):
        last_count=len(rows)%cols
        offset=(cols-last_count)*(cardw+22)/2 if last_count and i//cols==rowcount-1 else 0
        x=50+(i%cols)*(cardw+22)+offset;y=ystart+(i//cols)*(cardh+20)
        file=s.ROOT/r['file'];data=photo_data_url(str(file))
        photo_h=cardh-20 if horizontal else cardh-102
        photo_w=cardw*0.64 if horizontal else cardw-20
        label_x=x+cardw*0.81 if horizontal else x+cardw/2
        label_y=y+cardh*0.47 if horizontal else y+cardh-58
        svg +=[f'<rect x="{x}" y="{y}" width="{cardw}" height="{cardh}" rx="17" fill="#fafbfd" stroke="#e0e6ed"/>',
            f'<image x="{x+10}" y="{y+10}" width="{photo_w}" height="{photo_h}" preserveAspectRatio="xMidYMid meet" xlink:href="{data}"/>',
            f'<text x="{label_x}" y="{label_y}" text-anchor="middle" fill="#092b50" font-family="Arial,sans-serif" font-size="{25 if cols==3 else 29}" font-weight="700">{escape(r["colour"])}</text>']
        sizes=r['EU'];compact=(sizes[0]+'–'+sizes[-1])if all(int(sizes[j+1])-int(sizes[j])==1 for j in range(len(sizes)-1))else', '.join(sizes)
        if include_sizes:svg.append(f'<text x="{label_x}" y="{label_y+42 if horizontal else y+cardh-21}" text-anchor="middle" fill="#4f6072" font-family="Arial,sans-serif" font-size="24">EU {escape(compact)}</text>')
        all_sizes+=sizes
    footer='Select your preferred colour'+(' and size'if include_sizes else'')+' assortment.'
    svg.append(f'<text x="50" y="{height-34}" fill="#526277" font-family="Arial,sans-serif" font-size="22">{escape(footer)}</text></svg>')
    return ''.join(svg)

def main():
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--family',required=True);a=ap.parse_args()
    registry=s.load(ProductRegistry(s.ROOT));cache=s.load(s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json')['assets'];native={c._created_image_identity(u):r for u,r in cache.items()if r.get('file')and(s.ROOT/r['file']).is_file()}
    grouped={}
    for listing in registry['listings']:
        if listing['product_id']!=a.family or listing['id']in s.PROTECTED:continue
        f=s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/listing['id']/'formal_get.json'
        if not f.exists():continue
        p=s.load(f)['response']['product']
        if p['status']!='approved'or p['display']!='Y':continue
        ax=axes(p);pairs=[key(row,ax)for row in p['product_sku']['skus']];colours=next(x['values']for x in p['product_sku']['sku_attributes']if str(x['attribute_id'])=='191288010');rows=[]
        for colour in colours:
            label=colour['system_value_name'];photo=native.get(c._created_image_identity(colour['image_url']));assert photo,colour['image_url'];assert photo.get('sha256')==s.sha(s.ROOT/photo['file']),'Native media index does not match unchanged master'
            sizes=sorted({eu_number(eu)for cc,eu in pairs if cc==label},key=int);assert sizes
            rows.append({'colour':label,'EU':sizes,'file':photo['file'],'sha256':photo['sha256'],'url':colour['image_url']})
        rows=sorted(rows,key=lambda row:row['colour'])
        digest=hashlib.sha256(json.dumps([(r['colour'],r['EU'])for r in rows],sort_keys=True).encode()).hexdigest()[:12];group=grouped.setdefault(digest,{'rows':rows,'ids':[]});group['ids'].append(listing['id'])
    index=[]
    for digest,g in grouped.items():
        folder=s.ROOT/'99_临时区/商品质量全店复核/图文重建'/a.family/digest;folder.mkdir(parents=True,exist_ok=True)
        for role,detail in [('main',False),('detail',True)]:
            svg=folder/(role+'.svg');svg.write_text(diagram(g['rows'],detail),encoding='utf8');png=folder/(role+'.png');subprocess.run([NODE,str(Path(__file__).parent/'render_native_diagram.cjs'),str(svg),str(png)],check=True)
        record={'family':a.family,'matrix_key':digest,'ids':g['ids'],'rows':g['rows'],'state':'NATIVE_LAYOUT_REVIEW_REQUIRED','photos_unchanged':True,'editable_svg':True,'files':{role:s.rel(folder/(role+'.png'))for role in ('main','detail')}};s.save(folder/'图稿依据.json',record);index.append(record)
    s.save(s.ROOT/'99_临时区/商品质量全店复核/图文重建'/a.family/'索引.json',index);print('NATIVE_COLOUR_DIAGRAMS',a.family,len(index))

if __name__=='__main__':main()
