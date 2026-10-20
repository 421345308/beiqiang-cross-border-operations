"""Apply the owner's exact R1811 new-colour 999 inquiry-marker confirmation.

Inventory update is a delta API: a saved attempt is never automatically replayed.
Only the 33 added Green/Pink/Off White EU35–45 SKUs per reviewed ID can change.
999 is a seller-side inquiry marker, never evidence of physical availability.
"""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
from collections import Counter
from decimal import Decimal
import argparse, copy, json, sys
sys.path.insert(0, str(Path(__file__).parent))
import revise_catalog_content as s
from repair_source_assortment import axes, key
from read_only_catalog import read_only_call

IDS = ('1601939683302', '1601939743040', '1601939747001')
BASE = s.BASE/'配色与尺码修正/BQ015/库存标记'
RAW = s.RAW/'库存标记'
CONFIRMATION = '负责人明确答复：新增项也填 999 可询货标记。范围为R1811新增绿、粉、米白EU35–45；不代表实物现货或保供数量。'

def inventory_rows(response):
    rows = response.get('result', {}).get('data_list', [])
    if isinstance(rows, dict): rows = rows.get('data', [])
    assert isinstance(rows, list) and rows
    assert len({str(r['sku_id']) for r in rows}) == len(rows)
    return {str(r['sku_id']): r for r in rows}

def retained_product(product):
    result = copy.deepcopy(product)
    result.pop('gmt_modified', None)
    for row in result['product_sku']['skus']: row.pop('inventory_dto_list', None)
    # The inventory service reorders attributes without changing their values.
    result['attributes'] = sorted(result.get('attributes',[]),key=lambda x:json.dumps(x,sort_keys=True))
    return result

def main():
    sys.stdout.reconfigure(encoding='utf8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['prepare','submit','verify','sync'])
    a = ap.parse_args()
    if a.mode == 'sync': return sync()
    api, cfg = s.client()
    def read(method, params): return read_only_call(api,cfg,method,params)
    def get(pid): return read('alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'})
    def inv(pid): return read('alibaba.icbu.product.sku.inventory.get',{'product_id':pid,'language':'en_US'})
    for pid in IDS:
        public, raw = BASE/pid, RAW/pid
        ledger = public/'update_once.json'
        if a.mode == 'prepare':
            assert not ledger.exists(), 'Existing delta attempt: read only'
            got, stock = get(pid), inv(pid)
            s.save(raw/'before_get.json',got); s.save(raw/'before_inventory.json',stock)
            p = got['product']; rows = inventory_rows(stock)
            original = s.load(s.RAW/'配色与尺码修正/BQ015'/pid/'before_get.json')['product']
            old_ids = {str(r['sku_id']) for r in original['product_sku']['skus']}
            actual = {str(r['sku_id']):r for r in p['product_sku']['skus']}
            new_ids = set(actual)-old_ids
            assert len(old_ids)==33 and len(new_ids)==33 and len(actual)==66 and set(rows)==set(actual)
            assert p['status']=='approved' and p['display']=='Y'
            expected = Counter((c,str(eu)) for c in ('Green','Pink','Off White') for eu in range(35,46))
            assert Counter(key(actual[i],axes(p)) for i in new_ids)==expected
            changes = []
            for i in sorted(new_ids,key=int):
                row = rows[i]; delta = 999-int(row['inventory'])
                if delta:
                    changes.append({'sku_id':int(i),'inventory_code':row['inventory_code'],
                                    'inventory':abs(delta),'operate':'plus' if delta>0 else 'sub'})
            request = {'product_id':int(pid),'inventory_list':changes}
            s.save(raw/'request.json',request)
            s.save(public/'prepared.json',{'id':pid,'at':s.now(),'confirmation':CONFIRMATION,
                'target':999,'marker_only':True,'new_sku_ids':sorted(new_ids,key=int),
                'retained_sku_ids':sorted(old_ids,key=int),'change_count':len(changes),
                'request_sha256':s.sha(raw/'request.json'),
                'identity_evidence':s.rel(s.BASE/'配色与尺码修正/BQ015/计划.json')})
            print('PREPARED',pid,len(changes),flush=True)
        elif a.mode == 'submit':
            assert not ledger.exists(), 'Never replay an inventory delta'
            prepared = s.load(public/'prepared.json')
            assert s.sha(raw/'request.json')==prepared['request_sha256']
            got, stock = get(pid), inv(pid)
            s.save(raw/'immediate_prewrite_get.json',got);s.save(raw/'immediate_prewrite_inventory.json',stock)
            assert got['product']==s.load(raw/'before_get.json')['product']
            assert inventory_rows(stock)==inventory_rows(s.load(raw/'before_inventory.json'))
            request = s.load(raw/'request.json'); assert request['inventory_list']
            with ledger.open('x',encoding='utf8') as f:
                json.dump({'at':s.now(),'state':'WRITE_UNKNOWN_NO_REPLAY','request_sha256':prepared['request_sha256']},f)
            result = api.top_call(cfg,'alibaba.icbu.product.inventory.update',
                                  {'request_param':json.dumps(request,separators=(',',':'))})
            s.save(raw/'update_receipt.json',result);s.save(public/'update_receipt.json',s.sanitized(result))
            # The response is evidence only; the independent verification decides completion.
            state = 'RESPONSE_RECEIVED_VERIFY_REQUIRED' if not api.api_error(result) else 'API_ERROR_READ_BEFORE_ANY_ACTION'
            s.save(ledger,{'at':s.now(),'state':state,'request_sha256':prepared['request_sha256']})
            print(pid,state,flush=True)
        else:
            assert ledger.exists()
            prepared = s.load(public/'prepared.json'); before = s.load(raw/'before_get.json')['product']
            old_stock = inventory_rows(s.load(raw/'before_inventory.json'))
            got, stock = get(pid), inv(pid)
            s.save(raw/'after_get.json',got); s.save(raw/'after_inventory.json',stock)
            p = got['product']; rows = inventory_rows(stock)
            checks = {'all_66_ids':set(rows)==set(old_stock) and len(rows)==66,
                'new_33_marker':all(int(rows[i]['inventory'])==999 for i in prepared['new_sku_ids']),
                'old_33_inventory_unchanged':all(rows[i]==old_stock[i] for i in prepared['retained_sku_ids']),
                'all_other_formal_fields':retained_product(p)==retained_product(before),
                'approved_visible':p['status']=='approved' and p['display']=='Y'}
            form = {str(r['sku_id']):r for r in p['product_sku']['skus']}
            checks['formal_get_matches_inventory'] = all(
                len(form[i].get('inventory_dto_list',[]))==1 and
                int(form[i]['inventory_dto_list'][0]['inventory'])==int(row['inventory'])
                for i,row in rows.items())
            enc = read('alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'})
            score = read('alibaba.icbu.product.score.get',{'product_id':enc['secret_id']})
            s.save(raw/'score.json',score)
            result = score.get('result',{}); diag = result.get('problem_map') or {}
            if isinstance(diag,str): diag=json.loads(diag)
            checks['score'] = Decimal(str(result.get('final_score') or 0))>=5 and not diag.get('errorReasonList') and not any((diag.get('extendProblemMap')or{}).values())
            report = {'id':pid,'at':s.now(),'state':'FORMAL_FIELDS_SCORE_PASS' if all(checks.values()) else 'FORMAL_DIFFERENCE_DIAGNOSE_NO_REPLAY',
                'confirmation':CONFIRMATION,'checks':checks,'failed':[k for k,v in checks.items() if not v],
                'score':result.get('final_score'),'diagnostics':diag,'sku_count':len(rows),
                'new_sku_count':33,'marker':999,'physical_stock_claim':False,'status':p['status'],'display':p['display']}
            s.save(public/'verification.json',report)
            print(json.dumps({k:report[k] for k in ('id','state','score','failed')},ensure_ascii=False),flush=True)

def sync():
    file=ProductRegistry(s.ROOT);data=s.load(file)
    for pid in IDS:
        public,raw=BASE/pid,RAW/pid;report=s.load(public/'verification.json')
        assert all(v is True for k,v in report['checks'].items() if k!='score')
        listing=next(x for x in data['listings'] if x['id']==pid)
        product=next(x for x in data['products'] if x['id']==listing['product_id'])
        canonical=s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid
        current=s.load(canonical/'formal_get.json')
        assert current.get('observed_at_utc','')<=report['at'],'Newer formal snapshot must be reconciled first'
        s.save(canonical/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':report['at'],
            'method':'alibaba.icbu.product.get','response':s.sanitized(s.load(raw/'after_get.json')),
            'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],
            'raw_response_file':s.rel(raw/'after_get.json')})
        refs=[s.rel(public/x) for x in ('prepared.json','update_receipt.json','verification.json')]
        phase={'at':report['at'],'state':report['state'],'score':report['score'],'scope':CONFIRMATION,'evidence':refs}
        listing.setdefault('optimization',{})['inventory_marker_revision']=phase
        product['inventory_marker_revision']=phase
        for obj in (listing,product):obj['evidence']=list(dict.fromkeys(obj.get('evidence',[])+refs))
        listing['formal_fields']={'file':s.rel(canonical/'formal_get.json'),'at':report['at'],'scope':CONFIRMATION}
        listing.setdefault('observation',{}).update(at=report['at'],score=report['score'],audit=report['status'],display=report['display'],sku_count=66)
        listing.setdefault('current_platform_fields',{}).update(at=report['at'],sku_count=66,inventory_marker=999,physical_stock_verified=False)
        listing.setdefault('catalog_fields',{}).update(listing['current_platform_fields'])
        listing.setdefault('local_sync',{}).update(state=report['state'],observed_at=report['at'],current_fields_file=s.rel(canonical/'formal_get.json'),inventory_verification=refs[-1])
        source=next(x for x in data['sources'] if x['id']=='src-2064f015e244')
        source.setdefault('current_assortment',{}).update(at=report['at'],state='EXACT_COLOR_EU_AND_MARKER_VERIFIED' if report['checks']['score'] else 'EXACT_COLOR_EU_AND_MARKER_VERIFIED_SCORE_PENDING',score=report['score'],inventory=CONFIRMATION)
        product['next_action']='六色EU35–45、66SKU、颜色图绑定和999可询货标记已正式核对；继续主图信息层次优化。'
    s.save(file,data)
    sys.path.insert(0,str(s.ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as w
    assert not w.validate(data,s.ROOT)
    for path,body in w.build(data).items():w.write_generated(s.ROOT/path,body)
    print('INVENTORY_SOURCE_AND_LOCAL_SYNCHRONIZED',flush=True)

if __name__=='__main__':main()
