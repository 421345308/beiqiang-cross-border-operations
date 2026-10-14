"""Expand the already-published2583 family; never create a second product.

Source route and per-colour size range remain explicit. Existing26 SKU IDs,
codes and images are preserved;46 source-reviewed combinations are appended.
"""
from pathlib import Path
from xml.etree import ElementTree as E
import argparse, copy, importlib.util, json, sys
from urllib.parse import urlparse
from decimal import Decimal
from collections import Counter

sys.path.insert(0,str(Path(__file__).parent))
import repair_luqi_material_roles as shared
from read_only_catalog import read_only_call, product_readiness
import publish_hot_rank_hr_a_batch as pub
import schema_publish_contract as contract
ROOT=shared.ROOT;BASE=shared.BASE;FOLDER=BASE/'2583-1准备/家族扩色';CANDIDATE=BASE/'2583准备';PID='1601976101204'
load,save,sha,rel,now=shared.load,shared.save,shared.sha,shared.rel,shared.now
COLOURS=['Black','Light Gray','Beige','Yellow','Green','Red']
SIZES={c:list(range(36,43 if c=='Red' else 49)) for c in COLOURS}
FIELDS=['saleProp','sku','productTitle','textDesc','scImages','detailImage','ladderPrice','scPrice']


def record_plan():
    FOLDER.mkdir(parents=True,exist_ok=True)
    source=load(CANDIDATE/'当前来源与色码核对.json')
    old=load(BASE/'2583-1准备/商品预检与图组策略.json')
    assert old['source']=='https://luqi.sooxie.com/detail/2429716' and source['source']=='https://luqi.sooxie.com/detail/2356506'
    assert source['confirmed_EU_by_color']==SIZES
    routes={c:{'source':old['source'] if c in COLOURS[:2] else source['source'],'source_artno':'2583-1' if c in COLOURS[:2] else '2583','supplier_color':{'Light Gray':'浅灰','Black':'黑色','Beige':'米色','Yellow':'黄色','Green':'绿色','Red':'红色'}[c],'EU':SIZES[c]} for c in COLOURS}
    plan={'at':now(),'state':'SOURCE_FAMILY_REVIEWED_ASSETS_PREPARED_NO_CREATE','product_id':PID,'model':'BQ-LQ2583-1','source_family':'Luqi2583','operation':'update','no_new_id':True,'family_review':{'supplier_title':'路崎2583款宽头情侣德迅鞋爆款加颜色','conclusion':'Same base family with colour-specific trim; expand the already-published original ID. Source family title is not sufficient alone: actual plain tongue/central lacekeeper, rounded lobed perforated toe overlays, double stitched flowing side panels, low collar, flat laces and concentric ring/edge-cluster sole compared across both raw sources. Colour-specific Y trim is a variation, not an independent product.','actual_photos_compared':['2583/01,08,10,12,18,26,27','2583-1/01,03,06,08,10,21'],'prior_separate_offer_conclusion':'Superseded for current execution; original creation receipts retained as history.'},'source_routes_by_color':routes,'EU_combinations':72,'existing_combinations_preserved':26,'new_combinations':46,'title':source['title_draft'],'highlights':['Wide toe box design: A rounded forefoot and layered toe panels define this lace-up walking style.','Synthetic leather upper: Perforated panels and curved stitched overlays give the shoe its layered casual design.','Lace-up construction: Flat laces, a tongue lace keeper and a low-cut collar form the photographed opening.','Rubber sole: The photographed underside shows concentric grooves and small edge clusters.','Colour and EU assortment: Black, Light Gray, Beige, Yellow and Green in EU36-48; Red in EU36-42.'],'pricing':source['pricing_draft'],'keep_general_faq_and_company_bundle':True,'preserve_existing_sku_ids_codes_pictures':True,'current_material_roles':{'Midsole Material':['Other'],'Outsole Material':['Rubber']},'next_action':'Upload reviewed new assets once, then fresh exact-ID get/render. Prepare/submit only after current material edit is approved; never replay pending updates.'}
    save(FOLDER/'家族来源与页面计划.json',plan)
    source.update(state='SAME_FAMILY_EXPANSION_PREPARED_NO_CREATE',status='SAME_FAMILY_EXPANSION_PREPARED_NO_CREATE',family_original_product_id=PID,photo_evidenced_colors=COLOURS,colors_without_photographed_SKU_in_current_set=[],pending_unphotographed_EU_by_color={},initial_offer_EU_by_color=SIZES,initial_offer_EU_combinations=72,current_offer_limits='Six real photographed colours across two matching supplier family pages. Red from2356506 is Red, not Pink from2429716. No recolouring or second product create.',source_routes_by_color=routes,family_plan=rel(FOLDER/'家族来源与页面计划.json'),next_action=plan['next_action'])
    source['product_highlights_draft']=plan['highlights'];source['image_role_plan']['M4']='Actual Yellow layered upper construction; replace repeated full-body wearing role.';source['image_role_plan']['D4']='Six real colour and their own EU ranges; replace obsolete two-colour size detail.'
    source['mark_review']['observation']='Specific RunBird hypothesis visually compared with official primary mark; no match observed. Keep actual decoration; no global IP or trademark ownership claim.'
    save(CANDIDATE/'当前来源与色码核对.json',source)
    print('FAMILY_PLAN_72EU_NO_CREATE_SAVED',flush=True)


def bank(client,cfg):
    rows=[]
    for filename in ['AI新增颜色审核.json','AI家族详情审核.json']:
        proof=load(CANDIDATE/'05_AI候选'/filename)
        rows+=proof['items']
    hero=load(CANDIDATE/'05_AI候选/AI主图审核.json')
    p=CANDIDATE/'05_AI候选/M1.png';rows.append({'role':'M1','path':'05_AI候选/M1.png','sha256':sha(p)})
    # The selected hero has already been visually compared with actual original01.
    assert hero and len(rows)==7 and len({r['role'] for r in rows})==7
    file=FOLDER/'图片银行.json';data=load(file) if file.exists() else {'items':{},'scope':'Seven reviewed new images for originalID family expansion; no product create.'}
    for row in rows:
        role=row['role'];path=CANDIDATE/row['path'];assert path.exists() and sha(path)==row['sha256'] and path.stat().st_size<4*1024*1024
        if role in data['items']:
            saved=data['items'][role]
            assert saved['sha256']==row['sha256']
            if saved['state']=='UPLOADED':continue
            assert saved['state']=='LOCAL_CALL_FAILED_BEFORE_HTTP_PROVEN' and saved.get('network_request_sent') is False,'Unknown upload must be reconciled, never repeated'
        current={**row,'state':'OUTCOME_UNKNOWN_NO_RETRY','at':now()};data['items'][role]=current;save(file,data)
        response=client.upload_image(cfg,path,None);current['response']=response;save(file,data)
        raw=response.get('upload_image_response',{});assert not client.api_error(response) and raw.get('file_id') and raw.get('photobank_url')
        url=raw['photobank_url'];url='https:'+url if url.startswith('//') else url.replace('http:','https:')
        assert urlparse(url).hostname=='sc04.alicdn.com'
        current.update(state='UPLOADED',url=url,file_id=str(raw['file_id']));save(file,data);print(role,'UPLOADED',flush=True)
    data['state']='COMPLETE';save(file,data)
    save(FOLDER/'图片银行公开映射.json',{'state':'COMPLETE','items':{k:{a:b for a,b in v.items() if a!='response'} for k,v in data['items'].items()}})


def sku_key(row):
    return tuple(sorted((v.get('propId'),v.get('propValueName')) for v in row.findall("./field[@id='props']/values/value")))


def prepare(client,cfg):
    if (FOLDER/'update_once.json').exists():print('EXISTING_LEDGER_READBACK_ONLY');return
    got=read_only_call(client,cfg,'alibaba.icbu.product.get',{'product_id':PID,'language':'ENGLISH'});save(FOLDER/'latest_preparation_get.json',got);p=got['product']
    if product_readiness(p['status'])!='APPROVED' or p['display']!='Y':
        save(FOLDER/'当前状态.json',{'state':product_readiness(p['status']),'at':now(),'scope':'Prior scoped material repair; colour family still local only. No new product created.','next_action':'Prepare other real styles; after approval fresh render and append46EU without recreating26SKUs.'});print('PRIOR_MATERIAL_REPAIR_'+product_readiness(p['status']));return
    attrs=shared.attributes(p);assert attrs['Model Number']==['BQ-LQ2583-1'] and [v.casefold() for v in attrs['Midsole Material']]==['other'] and attrs['Outsole Material']==['Rubber']
    rendered=read_only_call(client,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(PID),'cat_id':201334413,'language':'en_US'}});assert rendered.get('data');save(FOLDER/'prepared_before_get.json',got);save(FOLDER/'before_render.json',rendered);(FOLDER/'current_schema.xml').write_text(rendered['data'],encoding='utf-8')
    schema=E.fromstring(rendered['data']);root=pub.values_only(schema,operation='update',field_ids=FIELDS);plan=load(FOLDER/'家族来源与页面计划.json');new=load(FOLDER/'图片银行.json');assert new['state']=='COMPLETE';new=new['items'];old={x['role']:x for x in load(BASE/'2583-1准备/正式图片银行映射.json')}
    company=load(ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/bank.json');company=company.get('items',company);m6=company['C1']
    pub.set_main_images(root,[new['M1'],old['M2'],old['M3'],new['M4'],old['M5'],m6])
    pub.set_gallery(root,'detailImage',[old['D1'],old['D2'],old['D3'],new['D4']],[(300,'Detail shot')]*3+[(150,'Product dimensions')])
    pub.set_direct_value(root,'productTitle',plan['title']);pub.set_direct_value(root,'textDesc','\n'.join(plan['highlights']))
    sale=root.find("./field[@id='saleProp']/complex-value")
    def named_sale(name):
        matches=[f for f in schema.findall("./field[@id='saleProp']/fields/field") if f.get('name')==name]
        assert len(matches)==1,'Current semantic sales property absent or ambiguous'
        return sale.find("./field[@id='%s']"%matches[0].get('id'))
    color=named_sale('Color');size=named_sale('EUR Size')
    cid=color.get('id').removeprefix('p-');sid=size.get('id').removeprefix('p-')
    assert cid.isdigit() and sid.isdigit()
    original_colors=list(color.find('values'));assert [v.get('inputValue') for v in original_colors]==COLOURS[:2]
    markers={v.get('inputValue'):v.text for v in original_colors};size_markers={int(v.get('inputValue').removeprefix('EU ')):v.text for v in size.find('values')};assert set(size_markers)==set(range(36,49))
    for i,c in enumerate(COLOURS[2:],2):
        markers[c]=str(-200-i);E.SubElement(color.find('values'),'value',{'inputValue':c,'img':new['SKU_'+c]['url']}).text=markers[c]
    sku=root.find("./field[@id='sku']");original_rows=list(sku.findall('./complex-values'));assert len(original_rows)==26
    for c in COLOURS[2:]:
        for eu in SIZES[c]:
            row=E.SubElement(sku,'complex-values')
            for fid,typ in [('price','input'),('skuStock','multiInput')]:E.SubElement(row,'field',id=fid,type=typ)
            f=E.SubElement(row,'field',id='skuOuterId',type='input');E.SubElement(f,'value').text=f'BQ-LQ2583-1-{c.upper()}-EU{eu}'
            E.SubElement(row,'field',id='skuId',type='input');E.SubElement(row,'field',id='outerSupplyId',type='input')
            f=E.SubElement(row,'field',id='props',type='multiInput');vs=E.SubElement(f,'values')
            for prop,label,marker in [(cid,c,markers[c]),(sid,f'EU {eu}',size_markers[eu])]:E.SubElement(vs,'value',{'propValueId':marker,'propId':prop,'propName':'p-'+prop,'propValueName':label}).text=prop+':'+marker
    assert all(E.tostring(a)==E.tostring(b) for a,b in zip(original_rows,sku.findall('./complex-values')[:26]))
    assert len(sku.findall('./complex-values'))==72 and len({sku_key(r) for r in sku.findall('./complex-values')})==72
    from schema_publish_contract import validate_sku_property_pairs
    validate_sku_property_pairs(root)
    pub.set_direct_value(root,'scPrice','1');ladder=root.find("./field[@id='ladderPrice']/complex-value");ladder.clear()
    for i,(quantity,price) in enumerate(plan['pricing']['tiers']):
        f=E.SubElement(ladder,'field',id=f'ladderPrice_{i}',type='complex');cv=E.SubElement(f,'complex-value')
        for name,value in [('quantity',quantity),('price',price)]:f=E.SubElement(cv,'field',id=name,type='input');E.SubElement(f,'value').text=str(value)
    payload=FOLDER/'payload.xml';payload.write_text(E.tostring(root,encoding='unicode'),encoding='utf-8')
    manifest={'operation':'update','product_id':PID,'category_id':201334413,'facts_reviewed':True,'source_evidence':[rel(FOLDER/'家族来源与页面计划.json'),rel(CANDIDATE/'当前来源与色码核对.json')],'current_schema':'current_schema.xml','current_schema_sha256':sha(FOLDER/'current_schema.xml'),'schema_request_id':rendered['request_id'],'schema_acquired_at':now(),'payload_xml':'payload.xml','field_ids':FIELDS,'dependency_ids':[]}
    save(FOLDER/'manifest.json',manifest);listing=pub.load_submission_manifest(FOLDER/'manifest.json','update',PID);save(FOLDER/'prepared.json',{'at':now(),'state':'PREPARED_FRESH_CURRENT_TARGET','id':PID,'existing_SKUs':26,'target_SKUs':72,'fields':listing['field_ids'],'preserve_current_26_sku_ids':True,'no_new_id':True});print('PREPARED_72EU_ORIGINAL_ID')


def submit(client,cfg):
    ledger=FOLDER/'update_once.json'
    if ledger.exists():print('EXISTING_LEDGER_READBACK_ONLY');return
    listing=pub.load_submission_manifest(FOLDER/'manifest.json','update',PID)
    current=read_only_call(client,cfg,'alibaba.icbu.product.get',{'product_id':PID,'language':'ENGLISH'});save(FOLDER/'immediate_prewrite_get.json',current)
    assert current['product']['status']=='approved' and current['product']['display']=='Y'
    assert shared.stable_product(current['product'])==shared.stable_product(load(FOLDER/'prepared_before_get.json')['product']), 'Current product changed since preparation'
    with ledger.open('x',encoding='utf-8') as f:json.dump({'state':'STARTED_OUTCOME_UNKNOWN_NO_REPLAY','id':PID,'at':now()},f)
    receipt=pub.api_submit(client,cfg,listing,False,update_product_id=PID);save(FOLDER/'update_receipt.json',receipt);save(ledger,{'state':receipt['status'],'at':receipt['attempted_at'],'id':PID,'refs':receipt.get('refs')})
    save(FOLDER/'当前状态.json',{'state':receipt['status'],'at':now(),'id':PID,'target_EU':72,'no_new_id':True,'next_action':'Only formal readback; never replay this update.'});print(receipt['status'],PID)


def verify(client,cfg):
    assert (FOLDER/'update_once.json').exists()
    got=read_only_call(client,cfg,'alibaba.icbu.product.get',{'product_id':PID,'language':'ENGLISH'});save(FOLDER/'after_get.json',got);p=got['product'];at=now();state=product_readiness(p['status']);report={'id':PID,'at':at,'state':state,'status':p['status'],'display':p['display'],'actual_score':None,'no_new_id':True}
    if state!='APPROVED' or p['display']!='Y':save(FOLDER/'verification.json',report);print(json.dumps(report));return
    rendered=read_only_call(client,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(PID),'cat_id':201334413,'language':'en_US'}});save(FOLDER/'after_render.json',rendered)
    if not rendered.get('data'):report['state']='EDITABLE_SCHEMA_UNAVAILABLE';save(FOLDER/'verification.json',report);return
    schema=E.fromstring(rendered['data']);actual=contract.field_snapshot(schema);payload=E.parse(FOLDER/'payload.xml').getroot();expected=contract.field_snapshot(payload);before_schema=contract.field_snapshot(E.fromstring(load(FOLDER/'before_render.json')['data']));before=load(FOLDER/'prepared_before_get.json')['product'];plan=load(FOLDER/'家族来源与页面计划.json');checks={}
    for fid in FIELDS:
        if fid!='sku':checks['schema_'+fid]=contract.created_field_equivalent(fid,expected[fid],actual.get(fid))
    checks['other_schema_values_preserved']=all(contract.created_field_equivalent(fid,value,actual.get(fid)) for fid,value in before_schema.items() if fid not in FIELDS)
    excluded={'subject','main_image','product_sku','struct_detail','sourcing_trade','pc_detail_url','gmt_modified','status','display'}
    checks['non_target_formal_product_preserved']=all(p.get(k)==v for k,v in before.items() if k not in excluded)
    checks['other_struct_detail_preserved']={k:v for k,v in p['struct_detail'].items() if k not in ('detail_image','product_summary')}=={k:v for k,v in before['struct_detail'].items() if k not in ('detail_image','product_summary')}
    # textDesc is submitted as one newline-separated string. product.get
    # returns that same string, rather than our planning list of bullet lines.
    checks['highlights_exact']=p['struct_detail']['product_summary']=='\n'.join(plan['highlights'])
    checks['title_exact']=p['subject']==plan['title']
    checks['known_material_roles_unchanged']=shared.attributes(p)==shared.attributes(before)
    old_trade={k:v for k,v in before['sourcing_trade'].items() if k not in ('fob_min_price','fob_max_price')};new_trade={k:v for k,v in p['sourcing_trade'].items() if k not in ('fob_min_price','fob_max_price')};checks['trade_except_reviewed_prices_preserved']=old_trade==new_trade
    axes={str(x['attribute_id']):x['values'] for x in p['product_sku']['sku_attributes']};col={str(x['value_id']):x['system_value_name'] for x in axes['191288010']};sizes={str(x['value_id']):x['system_value_name'] for x in axes['222038415']}
    pairs=Counter();bindings={};expected_tiers=sorted((int(q),Decimal(pr)) for q,pr in plan['pricing']['tiers']);price_match=True
    for row in p['product_sku']['skus']:
        props=json.loads(row['attr2_value']);pairs[(col[str(props['191288010'])],sizes[str(props['222038415'])])]+=1;bindings[row['sku_code']]=str(row['sku_id']);price_match&=sorted((int(x['start_quantity']),Decimal(x['price'])) for x in row['bulk_discount_prices'])==expected_tiers
    checks['exact_72EU_pairs']=pairs==Counter((c,f'EU {n}') for c in COLOURS for n in SIZES[c])
    checks['no_duplicate_sku_ids']=len(bindings)==72 and len(set(bindings.values()))==72 and '0' not in bindings.values()
    old_bindings={r['sku_code']:str(r['sku_id']) for r in before['product_sku']['skus']};checks['original_26_sku_ids_and_codes_preserved']=len(old_bindings)==26 and all(bindings.get(code)==sid for code,sid in old_bindings.items())
    checks['all_72_sku_three_tiers_match']=price_match
    checks['price_range_exact']=Decimal(p['sourcing_trade']['fob_min_price'])==min(pr for _,pr in expected_tiers) and Decimal(p['sourcing_trade']['fob_max_price'])==max(pr for _,pr in expected_tiers)
    old_sales=pub.values_only(E.fromstring(load(FOLDER/'before_render.json')['data']),operation='update',field_ids=['saleProp']);new_sales=pub.values_only(schema,operation='update',field_ids=['saleProp'])
    old_colours=old_sales.findall("./field/complex-value/field[@id='p-191288010']/values/value");new_colours={x.get('inputValue'):x for x in new_sales.findall("./field/complex-value/field[@id='p-191288010']/values/value")}
    checks['existing_colour_sku_pictures_preserved']=all(contract._created_image_identity(x.get('img'))==contract._created_image_identity(new_colours[x.get('inputValue')].get('img')) for x in old_colours)
    new_bank=load(FOLDER/'图片银行.json')['items'];checks['new_four_colour_pictures_exact']=all(contract._created_image_identity(new_colours[c].get('img'))==contract._created_image_identity(new_bank['SKU_'+c]['url']) for c in COLOURS[2:])
    common=load(ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/通用FAQ与公司简介.json');company=load(ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/bank.json')['items']
    checks['general_eight_faq_exact']=p['struct_detail']['product_faq']==[{'question':x['question'],'answer':x['answers']} for x in common['companyFaqDesc']]
    checks['company_intro_exact']=p['struct_detail']['company_summary']==common['companyDesc']
    checks['company_six_and_roles_exact']=Counter((str(x['image_set']['id']),contract._created_image_identity(x['image_url'])) for x in p['struct_detail']['company_image']['images'])==Counter((r,contract._created_image_identity(company[c]['url'])) for c,r in [('C1','400'),('C2','550'),('C3','600'),('C4','450'),('C5','700'),('C6','700')])
    checks['six_main_four_details']=len(p['main_image']['images'])==6 and len(p['struct_detail']['detail_image']['images'])==4
    report.update(checks=checks,failed=[k for k,v in checks.items() if not v],sku_bindings=bindings,get_observed_at=at,state='FORMAL_FIELDS_PASS_PENDING_SCORE' if all(checks.values()) else 'FORMAL_MISMATCH',public_qa='NOT_PUBLICLY_RETESTED_BATCH_API_POLICY')
    enc=client.top_call(cfg,'alibaba.icbu.product.id.encrypt',{'product_id':PID,'language':'ENGLISH'});assert enc.get('secret_id')
    try:
        score=read_only_call(client,cfg,'alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});save(FOLDER/'score.json',score);result=score.get('result',{});report['actual_score']=result.get('final_score');diag=result.get('problem_map') or {};diag=json.loads(diag) if isinstance(diag,str) else diag;report['score_diagnostics']=diag
        if all(checks.values()) and report['actual_score'] is not None and Decimal(str(report['actual_score']))>=5 and not any(diag.get('extendProblemMap',{}).values()) and not diag.get('errorReasonList'):report['state']='FORMAL_FIELDS_SCORE_PASS'
    except shared.ReadBusinessError as exc:report['score_read_error']=exc.api_evidence
    save(FOLDER/'verification.json',report);save(FOLDER/'当前状态.json',{k:v for k,v in report.items() if k not in ('score_diagnostics','sku_bindings')});print(json.dumps({k:report[k] for k in ('id','state','actual_score','failed')}))


def sync():
    data=load(shared.REG);listing=next(l for l in data['listings'] if l['id']==PID);product=next(p for p in data['products'] if p['id']==listing['product_id']);plan=load(FOLDER/'家族来源与页面计划.json')
    report=load(FOLDER/'verification.json') if (FOLDER/'verification.json').exists() else load(FOLDER/'当前状态.json') if (FOLDER/'当前状态.json').exists() else {'state':'LOCAL_DESIGN_PREPARED_NO_CREATE','at':now()}
    evidence=[rel(FOLDER/name) for name in ('家族来源与页面计划.json','图片银行公开映射.json','prepared.json','update_once.json','update_receipt.json','verification.json') if (FOLDER/name).exists()]
    phase={'state':report['state'],'at':report['at'],'original_id':PID,'target_EU':72,'old26_sku_ids_preserved_in_payload':True,'additional46':46,'no_new_product_id':True,'evidence':evidence}
    listing.setdefault('optimization',{})['family_color_expansion']=phase;product['family_color_expansion']=copy.deepcopy(phase)
    for ref in evidence:
        if ref not in product['evidence']:product['evidence'].append(ref)
        if ref not in listing['evidence']:listing['evidence'].append(ref)
    queue_file=BASE/'质量复核_2026-10-09/全分类处理队列.json';queue=load(queue_file)
    for row in queue['rows']:
        if row['style'] in ('2583','2583-1'):row['family_expansion']=phase
    if report['state'] in ('FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE'):
        got=load(FOLDER/'after_get.json');p=got['product'];canonical=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/PID
        save(canonical/'formal_get.json',{'requested_product_id':PID,'observed_at_utc':report['get_observed_at'],'method':'alibaba.icbu.product.get','response':shared.sanitized(got),'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],'raw_response_file':rel(FOLDER/'after_get.json')});save(canonical/'formal_render.json',load(FOLDER/'after_render.json'))
        source_ids={s['url'].rstrip('/'):s['id'] for s in data['sources']};routes={c:{**v,'source_id':source_ids[v['source']]} for c,v in plan['source_routes_by_color'].items()}
        listing['formal_fields']={'file':rel(canonical/'formal_get.json'),'at':report['at'],'scope':'OriginalID six-colour72EU family expansion, preserved26SKU IDs and colour images; formal fields plus separately recorded actual score.'}
        listing['current_platform_fields']={**listing.get('current_platform_fields',{}),'at':report['at'],'title':p['subject'],'keywords':p.get('keywords',[]),'main_images':p['main_image']['images'],'status':p['status'],'display':p['display'],'category_id':p['category_id'],'url':p.get('pc_detail_url') or listing['url'],'colour_EU':SIZES,'sku_count':72};listing['catalog_fields']={**listing.get('catalog_fields',{}),**listing['current_platform_fields']};listing['url']=listing['current_platform_fields']['url']
        listing['source_routes_by_color']=routes;listing['local_sync']={**listing.get('local_sync',{}),'state':report['state'],'current_fields_file':rel(canonical/'formal_get.json'),'current_schema_file':rel(canonical/'formal_render.json'),'current_family_plan':rel(FOLDER/'家族来源与页面计划.json'),'family_verification':rel(FOLDER/'verification.json'),'observed_at':report['at']};listing['observation']={**listing.get('observation',{}),'audit':p['status'],'display':p['display'],'at':report['at'],'score':report['actual_score'],'sku_count':72,'scope':'OriginalID six-colour family formal API; no per-ID browser retest claimed.'};listing['notes']='2583/2583-1 shared base family on original ID; six photographed colours72EU with Red36-42, other five36-48. Existing26SKU IDs/codes/pictures retained, additional46 sourced by colour. Materialroles and currentV8/company generalFAQ preserved.'
        product['source_routes_by_color']=routes;product['related_source_ids']=sorted({v['source_id'] for v in routes.values()});product['local_assets']['current_fields_file']=rel(canonical/'formal_get.json');product['local_assets']['current_family_plan']=rel(FOLDER/'家族来源与页面计划.json');product['next_action']='六色72EU已正式绑定；评分按逐ID当前值，继续其他可执行路崎款，不重复创建2583。';product['notes']=['2583和2583-1为同一基础系列的配色与饰边变化，来源标题明确加颜色，已按两页实际结构和底纹核对；一个本店型号/原ID承接。','黑/浅灰来源2429716，其余四色来源2356506；Red不沿用另一页Pink文字。采购逐色回到真实货源，库存逐单核实。']
        product['local_assets']['asset_roots']=list(dict.fromkeys(product['local_assets'].get('asset_roots',[])+[rel(CANDIDATE/'05_AI候选')]))
        product['raw_packages']=list(dict.fromkeys(product.get('raw_packages',[])+[rel(BASE/'2583-1准备/01_产品来源原图'),rel(CANDIDATE/'01_产品来源原图')]))
        sync_media(p,report)
        retired=next((x for x in data['products'] if x['id']=='LQ-2583'),None)
        retired_dossier=None
        if retired:
            assert not any(l['product_id']=='LQ-2583' for l in data['listings']), 'Candidate has existing listings; reconcile explicitly before merge'
            sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as workspace
            prior=workspace.build(data);retired_dossier=Path(retired.get('dossier_path',''))
            for key in ('aliases','evidence','raw_packages'):
                product[key]=list(dict.fromkeys(product.get(key,[])+retired.get(key,[])))
            data['products']=[x for x in data['products'] if x['id']!='LQ-2583']
            # Only remove an exact unchanged generated candidate entry, never
            # raw supplier assets or independent manual work.
            if retired_dossier and retired_dossier in prior:
                target=ROOT/retired_dossier
                assert target.resolve().is_relative_to(ROOT.resolve())
                if target.is_file() and workspace.view_matches(target,prior[retired_dossier]):
                    target.unlink()
                    if not any(target.parent.iterdir()):target.parent.rmdir()
        for row in queue['rows']:
            if row['style']=='2583':row.update(publication_state='MERGED_SOURCE_FAMILY_NO_EXTRA_CREATE',product_id=PID,EU_combinations=72,current_platform_evidence=rel(FOLDER/'verification.json'))
            if row['style']=='2583-1':row.update(publication_state='CREATED_APPROVED_Y',EU_combinations=72,current_platform_evidence=rel(FOLDER/'verification.json'),actual_score=report['actual_score'])
        summary_file=BASE/'本批正式商品汇总.json';summary=load(summary_file)
        for row in summary:
            if str(row['product_id'])==PID:row.update(status=p['status'],display=p['display'],sku_count=72,score=report['actual_score'],EU_labels_match=True,title_match=True,unmatched_fields=[],observed_at=report['at'],latest_review_scope='SOURCE_FAMILY_SIX_COLOURS_72EU_ORIGINAL26_SKU_IDS_PRESERVED',latest_review_file=rel(FOLDER/'verification.json'))
        save(summary_file,summary)
        plan['state']=report['state'];plan['formal_verification']=rel(FOLDER/'verification.json');plan['next_action']='原ID六色72EU正式字段与当前实际评分见核验，已同步逐色货源和本地素材；不再创建2583或重放扩色。继续其他路崎真实款。';save(FOLDER/'家族来源与页面计划.json',plan)
        facts=load(CANDIDATE/'当前来源与色码核对.json');facts.update(status=report['state'],state=report['state'],formal_original_product_id=PID,formal_EU_combinations=72,formal_verification=rel(FOLDER/'verification.json'),next_action=plan['next_action']);save(CANDIDATE/'当前来源与色码核对.json',facts)
    else:
        listing['current_repair_phase']={'state':report['state'],'at':report['at'],'scope':'Family expansion pending; last accepted fields have26EU, target72not claimed accepted.','evidence':evidence}
    if report['state'] in ('FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE'):listing.pop('current_repair_phase',None)
    save(queue_file,queue);save(shared.REG,data)
    sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as workspace
    for path,body in workspace.build(data).items():workspace.write_generated(ROOT/path,body)
    save(FOLDER/'双改核验.json',{'at':now(),'state':report['state'],'id':PID,'registry':rel(shared.REG),'no_extra_product_created':True,'target72not_claimed_until_formal_pass':True,'dossier_current':product.get('dossier_path')});print('FAMILY_LOCAL_SYNC',report['state'])


def sync_media(product,proof):
    from PIL import Image
    file=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json';data=load(file);mapping={}
    for row in load(BASE/'2583-1准备/正式图片银行映射.json'):
        path=Path(row['local_file']);assert path.is_relative_to(ROOT)
        mapping[contract._created_image_identity(row['url'])]={**row,'path':rel(path)}
    for row in load(FOLDER/'图片银行.json')['items'].values():mapping[contract._created_image_identity(row['url'])]={**row,'path':rel(CANDIDATE/row['path'])}
    for row in load(ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/bank.json')['items'].values():mapping[contract._created_image_identity(row['url'])]=row
    sd=product['struct_detail'];roles={'main':product['main_image']['images'],'details':[x['image_url'] for x in sd['detail_image']['images']],'company':[x['image_url'] for x in sd['company_image']['images']],'sku':[v['image_url'] for a in product['product_sku']['sku_attributes'] for v in a['values'] if v.get('image_url')],'html':[]}
    for urls in roles.values():
        for url in urls:
            row=mapping[contract._created_image_identity(url)];path=ROOT/row['path'];assert path.is_file() and sha(path)==row['sha256'];w,h=Image.open(path).size
            data['assets'][url]={'state':'SAVED','file':row['path'],'sha256':row['sha256'],'bytes':path.stat().st_size,'width':w,'height':h,'pixel_qa':'Selected actual-source-preserving local image visually reviewed; formal CDN asset identity matches official upload. No new browser or remote pixel claim.','at':proof['get_observed_at']}
    data['products'][PID]=roles;data['urls']=len(data['assets']);data['saved_urls']=sum(x.get('state')=='SAVED' for x in data['assets'].values());data['unique_files']=len({x['sha256'] for x in data['assets'].values() if x.get('state')=='SAVED'});data['errors']=sum(x.get('state')!='SAVED' for x in data['assets'].values());save(file,data)
    save(FOLDER/'本地素材绑定核验.json',{'at':now(),'id':PID,'state':'CURRENT_FORMAL_CDN_IDENTITY_LOCAL_SHA_MATCH','roles':roles,'source_file':rel(file),'scope':'Known original and new official image bank identities mapped to already-reviewed local assets; no download, new original packet or duplicate local copy.'})


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('plan','bank','prepare','submit','verify','sync'));args=ap.parse_args()
    if args.mode=='plan':record_plan();return
    if args.mode=='sync':sync();return
    spec=importlib.util.spec_from_file_location('alibaba_client',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client);cfg=client.load_config(client.DEFAULT_CONFIG)
    original_http=client.http_json;client.http_json=lambda request,timeout=25:original_http(request,timeout=timeout)
    if args.mode=='bank':bank(client,cfg)
    elif args.mode=='prepare':prepare(client,cfg)
    elif args.mode=='submit':submit(client,cfg)
    else:verify(client,cfg)


if __name__=='__main__':main()
