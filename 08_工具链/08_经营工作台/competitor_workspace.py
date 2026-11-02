"""Project verified competitor shops and the user's own buyer research into one view."""
import json
from urllib.parse import urlparse

CATALOG='06_市场研究/01_竞品/出口商反查/competitors.json'

def _alibaba_url(value):
    parsed=urlparse(value or '')
    return parsed.scheme=='https' and (parsed.hostname=='alibaba.com' or (parsed.hostname or '').endswith('.alibaba.com'))

def _sales_url(value):
    parsed=urlparse(value or '')
    return _alibaba_url(value) or (parsed.scheme=='https' and (parsed.hostname=='accio.com' or (parsed.hostname or '').endswith('.accio.com')))

def list_competitors(app):
    catalog=json.loads((app.root/CATALOG).read_text(encoding='utf-8-sig'))
    buyers=app.customer_workspace.list_discovery(kind='candidate')
    existing=[{'id':b['id'],'company':b.get('company') or b.get('title') or ''} for b in buyers if b.get('id') and (b.get('company') or b.get('title'))]
    items=[];excluded=[]
    for row in catalog['competitors']:
        verification=row.get('store_verification') or {}
        company=row.get('company_en','');store=row.get('store_url','');source=verification.get('source_url','')
        related=[{'id':b['id'],'company':b.get('company') or b.get('title','')} for b in buyers if row['competitor_id'] in b.get('related_competitors',[])]
        if verification.get('status')!='verified' or not company or not _alibaba_url(store) or not _alibaba_url(source):
            if company:excluded.append({'company':company,'note':verification.get('note') or '店铺与公司关系尚未核实。','buyers':related})
            continue
        item={'id':row['competitor_id'],'company':company,'direction':row.get('product_direction',''),
              'store_url':store,'source_url':source,'checked_date':verification.get('checked_date',''),
              'buyers':related}
        sales=row.get('sales_observation') or {}
        if isinstance(sales.get('sold'),int) and _sales_url(sales.get('source_url','')):
            item['sales']={'sold':sales['sold'],'note':sales.get('note',''),'source_url':sales['source_url']}
        items.append(item)
    items.sort(key=lambda x:(-x.get('sales',{}).get('sold',-1),x['company'].casefold()))
    return {'items':items,'excluded':excluded,'existing_buyers':existing}
