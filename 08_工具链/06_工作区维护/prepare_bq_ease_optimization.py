"""Evidence-scoped title preparation for existing verified BQ slip-on products."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
DETAILS = ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'


def main():
    data=json.loads(REGISTRY.read_text(encoding='utf-8-sig'))
    products={p['id']:p for p in data['products']}
    targets=[]
    for listing in data['listings']:
        pid=listing['product_id']
        if not re.fullmatch(r'BQ\d{3}',pid):
            continue
        form=products[pid].get('local_assets',{}).get('current_fields_file')
        if not form:
            continue
        text=(ROOT/form).read_text(encoding='utf-8-sig')
        closure_lines=[line for line in text.splitlines() if re.search(r'(Closure\s*(?:Type|type)?|闭合)',line)]
        if not any(re.search(r'\bSlip[- ]On\b',line,re.I) for line in closure_lines):
            continue
        if any('Backless' in line for line in closure_lines):
            continue
        # The original first thirty source links remain read-only; edit existing extensions.
        number=int(pid[2:])
        if number<=30 and not re.search(r'-[ROW][123]\b',listing['model']):
            continue
        snap=DETAILS/listing['id']/'formal_get.json'
        if not snap.exists():
            continue
        actual=json.loads(snap.read_text(encoding='utf-8'))['response']['product']
        attrs={a.get('attribute_name'):a.get('value_name') for a in actual.get('attributes',[])}
        if attrs.get('Closure Type')!='Slip-On' or actual.get('status')!='approved' or actual.get('display')!='Y':
            continue
        old=actual['subject']
        gender="Kids' " if re.search(r'\bkids\b',old,re.I) else "Girls' " if re.search(r'\bgirls\b',old,re.I) else "Women's " if re.search(r'\bwomen\b|women\x27s',old,re.I) and not re.search(r'\bmen\b',old,re.I) else "Men's " if re.search(r'\bmen\b|men\x27s',old,re.I) and not re.search(r'\bwomen\b',old,re.I) else ''
        knit='Knit' if re.search(r'\bknit(?:ted)?\b',old,re.I) and re.search(r'\bknit(?:ted)?\b',text,re.I) else 'Textile'
        sock=bool(re.search(r'\bsock\b',old,re.I) and re.search(r'\bsock\b',text,re.I))
        key='High Top Slip-On Knit Sock Sneakers' if sock and re.search(r'High Top',old,re.I) else f'Slip-On {knit} Walking Shoes'
        wide=' Wide Toe Box' if attrs.get('Fit Type')=='Wide Toe Box' and pid in {'BQ001','BQ002'} else ''
        role='OEM ODM Private Label' if '-O' in listing['model'] else 'Wholesale Casual Footwear' if '-W' in listing['model'] else 'for Daily Wear'
        title=f'{gender}{key}{wide} Easy On and Off {role}'
        if len(title)>128 or any(word in title for word in ['Hands Free','Anti Slip','Orthopedic']):
            raise ValueError('Invalid proposed claim/length')
        request={'product_id':listing['id'],'family':pid,'model':listing['model'],'category_id':actual['category_id'],'before_title':old,'title':title,'source_fields_file':form,'source_closure_lines':closure_lines,'facts_scope':'本地闭合结构与同ID正式Slip-On字段交叉一致；Easy On Off表达套脚穿脱，不承诺免手/医疗/性能','image_order':None,'state':'LOCAL_DRAFT','next_action':'核当前Schema、图片角色与影响字段，提交后正式/公开验收'}
        dest=DETAILS/listing['id']/'穿脱优化'
        dest.mkdir(exist_ok=True)
        (dest/'拟改字段.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding='utf-8')
        listing['optimization']={'state':'LOCAL_DRAFT','next_action':request['next_action'],'evidence':[(dest/'拟改字段.json').relative_to(ROOT).as_posix()]}
        targets.append(request)
    data['bq_ease_optimization']={'targets':[x['product_id'] for x in targets],'families':sorted({x['family'] for x in targets}),'scope':'既有BQ已核Slip-On链接；前30源款只读保护；没有宽楦证据不加宽楦，未核袜套不写Sock','state':'LOCAL_DRAFT'}
    REGISTRY.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'target_links':len(targets),'families':len({x['family'] for x in targets}),'examples':[{'id':x['product_id'],'title':x['title']} for x in targets[:4]]},ensure_ascii=False))


if __name__=='__main__':
    main()
