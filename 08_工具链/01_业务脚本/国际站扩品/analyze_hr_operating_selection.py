"""Use collected seller product metrics, never quality score, to select source directions."""

import sys as _registry_sys
from pathlib import Path as _RegistryPath
_registry_sys.path.insert(0, str(_RegistryPath(__file__).resolve().parents[3]/"08_工具链/06_工作区维护"))
from product_registry import ProductRegistry
from pathlib import Path
from datetime import datetime,timezone
import json,re,sys,time
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
DATA=ROOT/'99_临时区/HR实源替换/商品经营数据'
REG=ProductRegistry(ROOT)
METRICS=['exposure','clicks','ctr_percent','visitors','inquiries','tm_people']
def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,x):
    if hasattr(p, 'write_registry'):
        return p.write_registry(x)
    raw=(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    temporary=p.with_name(p.name+'.operating-selection.tmp')
    temporary.write_bytes(raw)
    for attempt in range(3):
        try:temporary.replace(p);break
        except OSError:
            if attempt==2:raise
            time.sleep(1)
def main():
    reg=load(REG);listings={l['id']:l for l in reg['listings']};periods={}
    for key,name,wanted in [('recent_week','week40_effective.json',(382,81960,1151,1757,31)),('previous_month','month09_effective.json',(357,155218,1986,3470,63))]:
        raw=load(DATA/name);rows={}
        for row in raw['rows']:
            pid=re.search(r'_(\d+)\.html',row['links'][0]).group(1)
            assert pid not in rows and len(row['values'])==6
            values=[None if v.strip() in ['--','-',''] else float(v.strip().removesuffix('%')) for v in row['values']]
            for i,v in enumerate(values):assert v is None or v>=0 and (i==2 or v.is_integer())
            rows[pid]={'id':pid,'title_during_period':row['cells'][0].split('\n')[0],**dict(zip(METRICS,values))}
        actual=(len(rows),*(sum(r[k]or 0 for r in rows.values())for k in ['exposure','clicks','visitors','inquiries']))
        assert actual==wanted,(key,actual,wanted)
        periods[key]={'period_label':raw['period_label'],'start':raw['period_start'],'end':raw['period_end'],'source_file':(DATA/name).relative_to(ROOT).as_posix(),'rows':rows,'table_checksum':actual,'complete_visible_table':True,'not_returned_is_not_zero':True}
    output=[]
    for product in reg['products']:
        family=product['id']
        if not(family.startswith('HR')or family=='DZ14546082-A'):continue
        ids=[l['id']for l in reg['listings']if l.get('product_id')==family]
        aggregate={};linkrows=[]
        for key,period in periods.items():
            returned=[period['rows'][pid]for pid in ids if pid in period['rows']]
            sums={k:sum(x[k]or 0 for x in returned) if returned else None for k in METRICS if k!='ctr_percent'}
            aggregate[key]={**sums,'weighted_ctr_percent':sums['clicks']/sums['exposure']*100 if sums['exposure'] else None,'returned_link_count':len(returned),'missing_ids':[pid for pid in ids if pid not in period['rows']]}
            linkrows += [{'period':key,**x}for x in returned]
        week=aggregate['recent_week'];month=aggregate['previous_month']
        contact=any(x['inquiries']or x['tm_people']for x in [week,month])
        if family=='DZ14546082-A':decision='OWNER_EXPLICIT_SIMILAR_ATHLETIC_STYLE'
        elif contact:decision='CONTACT_SIGNAL_KEEP_SIMILAR_DIRECTION'
        elif (week['clicks']or 0)>=10 and (week['weighted_ctr_percent']or 0)>=1.4:decision='CLICK_SIGNAL_KEEP_DIRECTION'
        elif any(x['exposure'] is not None and x['exposure']>=200 and (x['weighted_ctr_percent']or 0)<0.7 for x in [week,month]):decision='WEAK_CLICK_SIGNAL_OTHER_STYLE_ALLOWED'
        elif all((x['exposure']or 0)<200 for x in [week,month]):decision='INSUFFICIENT_TRAFFIC_COST_AND_CROSSBORDER_FIT_SELECTION'
        else:decision='NO_CLEAR_CONTACT_SIGNAL_COST_AND_CROSSBORDER_FIT_SELECTION'
        action='已有真实供货鞋款保持；依经营数据优化，不能因低曝光或少询盘重新重复换款。'if product['source_state']=='ADOPTED'else'有联系/点击信号优先保留相近方向并补实源。'if decision in ['CONTACT_SIGNAL_KEEP_SIMILAR_DIRECTION','CLICK_SIGNAL_KEEP_DIRECTION','OWNER_EXPLICIT_SIMILAR_ATHLETIC_STYLE']else'不强求旧虚拟鞋型；选跨境适配、供货入口有效、成本有价格空间的其他实鞋。低曝光不证明不受欢迎。'
        output.append({'family':family,'source_state':product['source_state'],'ids':ids,'periods':aggregate,'link_rows':linkrows,'decision':decision,'action':action})
        for pid in ids:
            listings[pid].setdefault('optimization',{})['operating_selection']={'at':datetime.now(timezone.utc).isoformat(),'decision':decision,'evidence':'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换/经营数据与选款.json','not_quality_score':True,'historical_period_does_not_prove_new_replacement_demand':True}
    result={'at':datetime.now(timezone.utc).isoformat(),'state':'OFFICIAL_VISIBLE_WEEK_MONTH_TABLES_CHECKSUM_PASS','owner_basis':'2026-10-13 final instruction: actual seller metrics instead of premium/quality flag; weak source-missing products may change style; DZ explicitly similar athletic direction','periods':{k:{a:v for a,v in p.items()if a!='rows'}for k,p in periods.items()},'families':output,'limitations':['Missing table rows are not zero or offline proof.','Periods overlap neither each other nor recentOct13 HR replacements; returned titles/images refer to styles during those periods.','Per-family visitor/inquiry sums across IDs are row sums, not deduplicated buyers.','Contact/click signals indicate owner-store engagement; not global sales proof or future conversion guarantee.','Only source-missing concepts are eligible for style replacement; already adopted actual shoes are retained.'],'private_raw_data_not_public_git':True}
    save(BASE/'经营数据与选款.json',result);save(REG,reg)
    sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as w
    assert not w.validate(reg)
    for p,data in w.build(reg).items():w.write_generated(ROOT/p,data)
    print('WEEK_MONTH_CHECKSUM_PASS',len(output),'FAMILIES')
    for x in output:
        if x['decision']in ['CONTACT_SIGNAL_KEEP_SIMILAR_DIRECTION','CLICK_SIGNAL_KEEP_DIRECTION','OWNER_EXPLICIT_SIMILAR_ATHLETIC_STYLE']:print(x['family'],x['decision'],x['periods'])
if __name__=='__main__':sys.stdout.reconfigure(encoding='utf8');main()
