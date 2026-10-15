"""Append source-reviewed colours on 1601981563053; preserve its 13 Beige SKUs.

Current product facts live in the exact target's family plan, not this code.
Uploads and update have separate once-only ledgers. No new product creation.
"""
from pathlib import Path
from xml.etree import ElementTree as E
from collections import Counter
from decimal import Decimal
import argparse,copy,hashlib,importlib.util,json,sys
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).parent))
import publish_reviewed_luqi as initial
import repair_luqi_material_roles as shared
import publish_hot_rank_hr_a_batch as pub
import schema_publish_contract as contract
from read_only_catalog import read_only_call,product_readiness
ROOT=shared.ROOT;BASE=shared.BASE;CANDIDATE=BASE/'2569准备';FOLDER=CANDIDATE/'家族扩色';PID='1601981563053';MODEL='BQ-LQ2569';CATEGORY=32299
load,save,sha,rel,now=shared.load,shared.save,shared.sha,shared.rel,shared.now
COLOURS=['Beige','Black','Green','Pink'];SIZES={c:list(range(36,43 if c=='Pink' else 49))for c in COLOURS}
FIELDS=['saleProp','sku','productTitle','textDesc','scImages','detailImage']


def plan_checked():
    p=load(FOLDER/'家族来源与页面计划.json')
    assert p['product_id']==PID and p['model']==MODEL and p['category_id']==CATEGORY and p['EU_combinations']==46 and p['existing_combinations_preserved']==13 and p['new_combinations']==33
    assert {c:r['EU'] for c,r in p['source_routes_by_color'].items()}==SIZES
    evidence=load(ROOT/p['source_identity_evidence']);index=load(ROOT/p['source_image_index'])
    assert evidence['state']=='ACTUAL_FOUR_COLOUR_SOURCE_IDENTITY_REVIEW_PASS_PENDING_ASSETS' and evidence['sha256']==index['source_HTML_sha256'] and evidence['source']==index['source'] and index['collected_images']==28
    assert evidence['source_price_cny']==p['pricing']['source_cny']=='59.00'
    return p


def bank(client,cfg):
    plan_checked();proof=load(FOLDER/'图组验收.json');assert proof['state']=='VISUAL_PASS_PENDING_UPLOAD' and len(proof['items'])==5
    assert {x['role']for x in proof['items']}=={'M5','D4','SKU_Black','SKU_Green','SKU_Pink'}
    path=FOLDER/'图片银行.json';data=load(path)if path.exists()else{'state':'IN_PROGRESS','items':{}}
    for item in proof['items']:
        role=item['role'];file=ROOT/item['path'];assert sha(file)==item['sha256'] and file.stat().st_size<4194304
        if role in data['items']:
            old=data['items'][role];assert old['sha256']==item['sha256']
            if old['state']=='UPLOADED':continue
            assert old['state']=='LOCAL_CALL_FAILED_BEFORE_HTTP_PROVEN' and old.get('network_request_sent')is False,'Unknown upload requires reconciliation, no replay'
        row={**item,'state':'OUTCOME_UNKNOWN_NO_RETRY','at':now()};data['items'][role]=row;save(path,data)
        try:result=client.upload_image(cfg,file,None)
        except client.ClientError as exc:
            before=initial.failed_tls_handshake_before_http(exc)
            if before:row.update(state='LOCAL_CALL_FAILED_BEFORE_HTTP_PROVEN',network_request_sent=False,transport_evidence=before)
            save(path,data);raise
        row['response']=result;save(path,data);raw=result.get('upload_image_response',{});assert not client.api_error(result)and raw.get('file_id')and raw.get('photobank_url')
        url=raw['photobank_url'];url='https:'+url if url.startswith('//')else url.replace('http:','https:');assert urlparse(url).hostname=='sc04.alicdn.com'
        row.update(state='UPLOADED',url=url,file_id=str(raw['file_id']));save(path,data);print(role,'UPLOADED',flush=True)
    data['state']='COMPLETE';save(path,data);save(FOLDER/'图片银行公开映射.json',{'state':'COMPLETE','items':{k:{a:b for a,b in v.items()if a!='response'}for k,v in data['items'].items()}})


def prepare(client,cfg):
    assert not(FOLDER/'update_once.json').exists(),'Existing update ledger: verify/sync only'
    plan=plan_checked();new=load(FOLDER/'图片银行.json');assert new['state']=='COMPLETE';new=new['items'];old=load(CANDIDATE/'图片银行.json')['items']
    got=read_only_call(client,cfg,'alibaba.icbu.product.get',{'product_id':PID,'language':'ENGLISH'});p=got['product'];assert p['status']=='approved'and p['display']=='Y'and shared.attributes(p)['Model Number']==[MODEL]and len(p['product_sku']['skus'])==13
    save(FOLDER/'prepared_before_get.json',got)
    rendered=read_only_call(client,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(PID),'cat_id':CATEGORY,'language':'en_US'}});assert rendered.get('data')and rendered.get('request_id');save(FOLDER/'before_render.json',rendered);schema=E.fromstring(rendered['data']);(FOLDER/'current_schema.xml').write_text(rendered['data'],encoding='utf8')
    root=pub.values_only(schema,operation='update',field_ids=FIELDS);company=load(ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/bank.json')['items']
    assert contract._created_image_identity(p['main_image']['images'][5])==contract._created_image_identity(company['C1']['url'])
    pub.set_main_images(root,[old['M1'],old['M2'],old['M3'],old['M4'],new['M5'],company['C1']])
    pub.set_gallery(root,'detailImage',[old['D1'],old['D2'],old['D3'],new['D4']],[(300,'Detail shot')]*3+[(150,'Product dimensions')])
    pub.set_direct_value(root,'productTitle',plan['title']);pub.set_direct_value(root,'textDesc','\n'.join(plan['highlights']))
    sale=root.find("./field[@id='saleProp']/complex-value")
    defs={f.get('name'):f.get('id')for f in schema.findall("./field[@id='saleProp']/fields/field")};color=sale.find("./field[@id='%s']"%defs['Color']);size=sale.find("./field[@id='%s']"%defs['EUR Size']);cid=color.get('id').removeprefix('p-');sid=size.get('id').removeprefix('p-')
    assert(cid,sid)==('191288010','222038415'),'Current observed footwear axes required; do not borrow unverified IDs'
    original_colors=list(color.find('values'));assert [v.get('inputValue')for v in original_colors]==['Beige'];markers={v.get('inputValue'):v.text for v in original_colors};size_markers={int(v.get('inputValue').removeprefix('EU ')):v.text for v in size.find('values')};assert set(size_markers)==set(range(36,49))
    for n,c in enumerate(COLOURS[1:],1):markers[c]=str(-200-n);E.SubElement(color.find('values'),'value',{'inputValue':c,'img':new['SKU_'+c]['url']}).text=markers[c]
    sku=root.find("./field[@id='sku']");original_rows=list(sku.findall('./complex-values'));assert len(original_rows)==13
    for c in COLOURS[1:]:
        for eu in SIZES[c]:
            row=E.SubElement(sku,'complex-values')
            for fid,typ in [('price','input'),('skuStock','multiInput')]:E.SubElement(row,'field',id=fid,type=typ)
            f=E.SubElement(row,'field',id='skuOuterId',type='input');E.SubElement(f,'value').text=f'{MODEL}-{c.upper()}-EU{eu}'
            E.SubElement(row,'field',id='skuId',type='input');E.SubElement(row,'field',id='outerSupplyId',type='input');vs=E.SubElement(E.SubElement(row,'field',id='props',type='multiInput'),'values')
            for prop,label,marker in [(cid,c,markers[c]),(sid,f'EU {eu}',size_markers[eu])]:E.SubElement(vs,'value',{'propValueId':marker,'propId':prop,'propName':'p-'+prop,'propValueName':label}).text=prop+':'+marker
    assert all(E.tostring(a)==E.tostring(b)for a,b in zip(original_rows,sku.findall('./complex-values')[:13]))
    assert len(sku.findall('./complex-values'))==46 and len({sku_key(r)for r in sku.findall('./complex-values')})==46;contract.validate_sku_property_pairs(root)
    payload=FOLDER/'payload.xml';payload.write_text(E.tostring(root,encoding='unicode'),encoding='utf8')
    manifest={'operation':'update','product_id':PID,'category_id':CATEGORY,'facts_reviewed':True,'source_evidence':[rel(FOLDER/'家族来源与页面计划.json'),plan['source_identity_evidence']],'current_schema':'current_schema.xml','current_schema_sha256':sha(FOLDER/'current_schema.xml'),'schema_request_id':rendered['request_id'],'schema_acquired_at':now(),'payload_xml':'payload.xml','field_ids':FIELDS,'dependency_ids':[]};save(FOLDER/'manifest.json',manifest);listing=pub.load_submission_manifest(FOLDER/'manifest.json','update',PID);save(FOLDER/'prepared.json',{'at':now(),'state':'PREPARED_FRESH_CURRENT_TARGET','id':PID,'existing_SKUs':13,'target_SKUs':46,'fields':listing['field_ids'],'preserve_current_13_sku_ids':True,'no_new_id':True});print('PREPARED_ORIGINAL13_APPEND33_TARGET46')


# The once-only update submission and readback implementation is shared in
# structure with the proven 2583 expansion. Exact target counts/category and
# the current plan are verified here; no prior product facts are inherited.


def sku_key(row):
    return tuple(sorted((v.get('propId'),v.get('propValueName')) for v in row.findall("./field[@id='props']/values/value")))



def submit(client,cfg):
    ledger=FOLDER/'update_once.json'
    if ledger.exists():print('EXISTING_LEDGER_READBACK_ONLY');return
    listing=pub.load_submission_manifest(FOLDER/'manifest.json','update',PID)
    current=read_only_call(client,cfg,'alibaba.icbu.product.get',{'product_id':PID,'language':'ENGLISH'});save(FOLDER/'immediate_prewrite_get.json',current)
    assert current['product']['status']=='approved' and current['product']['display']=='Y'
    assert shared.stable_product(current['product'])==shared.stable_product(load(FOLDER/'prepared_before_get.json')['product']), 'Current product changed since preparation'
    with ledger.open('x',encoding='utf-8') as f:json.dump({'state':'STARTED_OUTCOME_UNKNOWN_NO_REPLAY','id':PID,'at':now()},f)
    receipt=pub.api_submit(client,cfg,listing,False,update_product_id=PID);save(FOLDER/'update_receipt.json',receipt);save(ledger,{'state':receipt['status'],'at':receipt['attempted_at'],'id':PID,'refs':receipt.get('refs')})
    save(FOLDER/'当前状态.json',{'state':receipt['status'],'at':now(),'id':PID,'target_EU':46,'no_new_id':True,'next_action':'Only formal readback; never replay this update.'});print(receipt['status'],PID)



def verify(client,cfg):
    assert (FOLDER/'update_once.json').exists()
    got=read_only_call(client,cfg,'alibaba.icbu.product.get',{'product_id':PID,'language':'ENGLISH'});save(FOLDER/'after_get.json',got);p=got['product'];at=now();state=product_readiness(p['status']);report={'id':PID,'at':at,'state':state,'status':p['status'],'display':p['display'],'actual_score':None,'no_new_id':True}
    if state!='APPROVED' or p['display']!='Y':save(FOLDER/'verification.json',report);print(json.dumps(report));return
    rendered=read_only_call(client,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(PID),'cat_id':CATEGORY,'language':'en_US'}});save(FOLDER/'after_render.json',rendered)
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
    checks['all_trade_values_preserved']=p['sourcing_trade']==before['sourcing_trade']
    axes={str(x['attribute_id']):x['values'] for x in p['product_sku']['sku_attributes']};col={str(x['value_id']):x['system_value_name'] for x in axes['191288010']};sizes={str(x['value_id']):x['system_value_name'] for x in axes['222038415']}
    pairs=Counter();bindings={};expected_tiers=sorted((int(q),Decimal(pr)) for q,pr in plan['pricing']['tiers']);price_match=True
    for row in p['product_sku']['skus']:
        props=json.loads(row['attr2_value']);pairs[(col[str(props['191288010'])],sizes[str(props['222038415'])])]+=1;bindings[row['sku_code']]=str(row['sku_id']);price_match&=sorted((int(x['start_quantity']),Decimal(x['price'])) for x in row['bulk_discount_prices'])==expected_tiers
    checks['exact_46EU_pairs']=pairs==Counter((c,f'EU {n}') for c in COLOURS for n in SIZES[c])
    checks['no_duplicate_sku_ids']=len(bindings)==46 and len(set(bindings.values()))==46 and '0' not in bindings.values()
    old_bindings={r['sku_code']:str(r['sku_id']) for r in before['product_sku']['skus']};checks['original_13_sku_ids_and_codes_preserved']=len(old_bindings)==13 and all(bindings.get(code)==sid for code,sid in old_bindings.items())
    current_rows={r['sku_code']:r for r in p['product_sku']['skus']};checks['original13_whole_formal_sku_rows_preserved']=all(current_rows.get(r['sku_code'])==r for r in before['product_sku']['skus'])
    checks['all_46_sku_three_tiers_match']=price_match
    checks['price_range_exact']=Decimal(p['sourcing_trade']['fob_min_price'])==min(pr for _,pr in expected_tiers) and Decimal(p['sourcing_trade']['fob_max_price'])==max(pr for _,pr in expected_tiers)
    old_sales=pub.values_only(E.fromstring(load(FOLDER/'before_render.json')['data']),operation='update',field_ids=['saleProp']);new_sales=pub.values_only(schema,operation='update',field_ids=['saleProp'])
    old_colours=old_sales.findall("./field/complex-value/field[@id='p-191288010']/values/value");new_colours={x.get('inputValue'):x for x in new_sales.findall("./field/complex-value/field[@id='p-191288010']/values/value")}
    checks['existing_colour_sku_pictures_preserved']=all(contract._created_image_identity(x.get('img'))==contract._created_image_identity(new_colours[x.get('inputValue')].get('img')) for x in old_colours)
    new_bank=load(FOLDER/'图片银行.json')['items'];checks['new_three_colour_pictures_exact']=all(contract._created_image_identity(new_colours[c].get('img'))==contract._created_image_identity(new_bank['SKU_'+c]['url']) for c in COLOURS[1:])
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


def sync_media(product,proof):
    from PIL import Image
    file=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json';cache=load(file);mapping={}
    for bankfile in (CANDIDATE/'图片银行.json',FOLDER/'图片银行.json',ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/bank.json'):
        for row in load(bankfile)['items'].values():mapping[contract._created_image_identity(row['url'])]=row
    sd=product['struct_detail'];roles={'main':product['main_image']['images'],'details':[x['image_url']for x in sd['detail_image']['images']],'company':[x['image_url']for x in sd['company_image']['images']],'sku':[v['image_url']for a in product['product_sku']['sku_attributes']for v in a['values']if v.get('image_url')],'html':[]}
    for urls in roles.values():
        for url in urls:
            row=mapping[contract._created_image_identity(url)];path=ROOT/row['path'];assert sha(path)==row['sha256'];w,h=Image.open(path).size
            cache['assets'][url]={'state':'SAVED','file':row['path'],'sha256':row['sha256'],'bytes':path.stat().st_size,'width':w,'height':h,'pixel_qa':'Actual-source local image reviewed; official CDN identity matched. No per-ID browser assertion.','at':proof['get_observed_at']}
    cache['products'][PID]=roles;cache['urls']=len(cache['assets']);cache['saved_urls']=sum(x.get('state')=='SAVED'for x in cache['assets'].values());cache['unique_files']=len({x['sha256']for x in cache['assets'].values()if x.get('state')=='SAVED'});cache['errors']=sum(x.get('state')!='SAVED'for x in cache['assets'].values());save(file,cache)
    merged={**load(CANDIDATE/'图片银行.json')['items'],**load(FOLDER/'图片银行.json')['items']};save(FOLDER/'当前素材映射.json',{'state':'CURRENT_FORMAL_CDN_IDENTITY_LOCAL_SHA_MATCH','at':now(),'id':PID,'roles':roles,'items':{k:{a:b for a,b in v.items()if a!='response'}for k,v in merged.items()},'scope':'Current selection overlay; initial13EU uploads remain intact historical receipts.'});save(FOLDER/'本地素材绑定核验.json',{'at':now(),'id':PID,'state':'CURRENT_FORMAL_CDN_IDENTITY_LOCAL_SHA_MATCH','roles':roles,'source_file':rel(file)})


def sync():
    plan=plan_checked();report=load(FOLDER/'verification.json');data=load(shared.REG);listing=next(x for x in data['listings']if x['id']==PID);product=next(x for x in data['products']if x['id']==listing['product_id']);facts=load(CANDIDATE/'当前来源与色码核对.json')
    evidence=[rel(FOLDER/name)for name in ('家族来源与页面计划.json','补充来源身份核验.json','图组验收.json','图片银行公开映射.json','prepared.json','manifest.json','update_once.json','update_receipt.json','verification.json','score.json')if(FOLDER/name).exists()]
    phase={'state':report['state'],'at':report['at'],'original_id':PID,'target_EU':46,'existing13_sku_ids_preserved_in_payload':True,'additional33':33,'no_new_product_id':True,'evidence':evidence,'next_action':'Only exact-ID verification/score and local sync; never replay update or create a second product.'};listing.setdefault('optimization',{})['family_color_expansion']=copy.deepcopy(phase);product['family_color_expansion']=copy.deepcopy(phase)
    for obj in (product,listing):obj['evidence']=list(dict.fromkeys(obj.get('evidence',[])+evidence))
    qfile=BASE/'质量复核_2026-10-09/全分类处理队列.json';queue=load(qfile);q=next(x for x in queue['rows']if x['style']=='2569');q['family_expansion']=copy.deepcopy(phase)
    summaryfile=BASE/'本批正式商品汇总.json';summary=load(summaryfile);row=next(x for x in summary if str(x['product_id'])==PID)
    issuesfile=BASE/'待补资料与局部问题.json';issues=load(issuesfile)
    accepted=report['state']in('FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE')
    if accepted:
        got=load(FOLDER/'after_get.json');p=got['product'];canonical=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/PID
        save(canonical/'formal_get.json',{'requested_product_id':PID,'observed_at_utc':report['get_observed_at'],'method':'alibaba.icbu.product.get','response':shared.sanitized(got),'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],'raw_response_file':rel(FOLDER/'after_get.json'),'acceptance_state':report['state']});save(canonical/'formal_render.json',load(FOLDER/'after_render.json'))
        idx=load(ROOT/plan['source_image_index']);url=idx['source'];sid='src-'+hashlib.sha256(url.encode()).hexdigest()[:12];alternate=next((s for s in data['sources']if s['id']==sid),None)
        if alternate is None:
            alternate={'id':sid,'url':url,'shop_url':'https://jiangshang.sooxie.com','supplier':'江上鞋业','model':'2569','price':'59.00','currency':'CNY','unit':'双','price_terms':'公开参考价；接单逐色核数量、包装、运费和可供条件。','observed_at':idx['observed_at'],'evidence':[plan['source_image_index'],plan['source_identity_evidence'],rel(FOLDER/'家族来源与页面计划.json')]};data['sources'].append(alternate)
        assert alternate['url']==url and not any(x['id']!=PID and(x.get('bound_source_id')==sid or any(v.get('source_id')==sid for v in x.get('source_routes_by_color',{}).values()))for x in data['listings'])
        alternate['latest_price_review']={'observed_at':idx['observed_at'],'price_cny':'59.00','evidence':plan['source_identity_evidence'],'scope':'Exact photographed colour source reference, not physical stock or fixed quotation.'}
        sources={s['url'].rstrip('/'):s['id']for s in data['sources']};routes={c:{**v,'source_id':sources[v['source']]}for c,v in plan['source_routes_by_color'].items()}
        current={**listing.get('current_platform_fields',{}),'at':report['get_observed_at'],'title':p['subject'],'keywords':p.get('keywords',[]),'main_images':p['main_image']['images'],'status':p['status'],'display':p['display'],'category_id':p['category_id'],'url':p.get('pc_detail_url')or listing['url'],'colour_EU':SIZES,'sku_count':46}
        listing.update(current_platform_fields=current,catalog_fields=copy.deepcopy(current),url=current['url'],source_routes_by_color=copy.deepcopy(routes),formal_fields={'file':rel(canonical/'formal_get.json'),'at':report['get_observed_at'],'scope':'OriginalID46EU, original13SKU IDs/codes/images preserved,33actual-source colour combinations appended.'},local_sync={'state':report['state'],'current_fields_file':rel(canonical/'formal_get.json'),'current_schema_file':rel(canonical/'formal_render.json'),'source_fact_file':rel(CANDIDATE/'当前来源与色码核对.json'),'current_family_plan':rel(FOLDER/'家族来源与页面计划.json'),'family_verification':rel(FOLDER/'verification.json'),'at':report['at']},observation={'audit':p['status'],'display':p['display'],'at':report['get_observed_at'],'score':report['actual_score'],'sku_count':46,'scope':'OriginalID four-colour API verification; no per-ID public UI assertion.'})
        listing.pop('current_repair_phase',None);product['source_routes_by_color']=copy.deepcopy(routes);product['related_source_ids']=list(dict.fromkeys(product.get('related_source_ids',[])+[sid]));product.pop('deferred_source_options',None);product['local_assets'].update(current_fields_file=rel(canonical/'formal_get.json'),current_family_plan=rel(FOLDER/'家族来源与页面计划.json'),current_image_map=rel(FOLDER/'当前素材映射.json'));product['next_action']='四色46EU正式字段和颜色货源已同步，原米色13SKU保留；实际评分以本次家族扩色核验为准。只验原ID，不重复创建2569。'
        q.update(publication_state='CREATED_APPROVED_Y',EU_combinations=46,actual_score=report['actual_score'],score_status=report['state'],current_platform_evidence=rel(FOLDER/'verification.json'),preparation_evidence=rel(FOLDER/'prepared.json'),local_issue='',deferred_source_options={},deferred_EU_combinations=0,current_visual_evidence=rel(FOLDER/'图组验收.json'));row.update(url=listing['url'],status=p['status'],display=p['display'],sku_count=46,score=report['actual_score'],observed_at=report['get_observed_at'],latest_review_scope=report['state'],latest_review_file=rel(FOLDER/'verification.json'));row.pop('pending_target_EU',None);issues['active'].pop('2569',None)
        facts.setdefault('initial_offer_EU_by_color',{'Beige':list(range(36,49))});facts.setdefault('initial_offer_EU_combinations',13);facts.update(state='CREATED_'+report['state'],source_EU_by_color=copy.deepcopy(SIZES),source_EU_combinations=46,title_draft=plan['title'],product_highlights_draft=plan['highlights'],deferred_source_options={},current_family_plan=rel(FOLDER/'家族来源与页面计划.json'),formal_verification=rel(FOLDER/'verification.json'),current_execution={'script':'08_工具链/01_业务脚本/国际站扩品/expand_luqi_2569_colours.py','directory':rel(FOLDER),'operation':'ExistingID family expansion, no create'},next_action=product['next_action'])
        facts['publish_profile']['buyer_colours']=[{'buyer':c,'supplier_key':c,'supplier_label':routes[c]['supplier_color'],'supplier_artno':'2569','source_url':routes[c]['source'],'image_role':'M2'if c=='Beige'else'SKU_'+c}for c in COLOURS]
        facts['source_routes_by_color']=copy.deepcopy(routes);facts['source_color_aliases']={c:r['supplier_color']for c,r in routes.items()};facts['variant_sources']=[{'source':url,'artno':'2569','observed_at':idx['observed_at'],'source_price_cny':'59.00','source_EU_by_color':copy.deepcopy(SIZES),'current_source_evidence':plan['source_identity_evidence'],'source_HTML_sha256':idx['source_HTML_sha256'],'current_image_index':plan['source_image_index'],'current_image_index_sha256':sha(ROOT/plan['source_image_index'])}]
        facts['publication'].update(actual_score=report['actual_score'],formal_verification=rel(FOLDER/'verification.json'),local_sync_at=now(),family_expansion_EU=46);save(CANDIDATE/'当前来源与色码核对.json',facts)
        sync_media(p,report);plan.update(state=report['state'],formal_verification=rel(FOLDER/'verification.json'),next_action=product['next_action']);save(FOLDER/'家族来源与页面计划.json',plan)
    else:
        listing['current_repair_phase']={'state':report['state'],'at':report['at'],'scope':'Colour expansion pending; last accepted snapshot13EU is retained,46not yet accepted.','evidence':evidence};product['next_action']='新增三色33EU扩色仅回读原ID；米色13EU旧正式快照保留，目标46尚未验收；不重放写入。'
        facts.update(current_family_plan=rel(FOLDER/'家族来源与页面计划.json'),family_expansion=copy.deepcopy(phase),current_execution={'script':'08_工具链/01_业务脚本/国际站扩品/expand_luqi_2569_colours.py','directory':rel(FOLDER),'operation':'Existing-ID colour expansion pending; initial13 snapshot remains accepted'},next_action=product['next_action']);save(CANDIDATE/'当前来源与色码核对.json',facts)
        if product.get('deferred_source_options'):product['deferred_source_options']['reason']='Supplementary actual colour photos reviewed; original-ID expansion awaits formal readback.'
        q.update(publication_state='SUBMITTED_'+report['state']+'_FAMILY_COLOURS',current_platform_evidence=rel(FOLDER/'verification.json'),local_issue='Existing13 accepted snapshot retained;33colour expansion pending formal readback.')
        row.update(status=report['status'],display=report['display'],score=report.get('actual_score'),latest_review_scope=report['state'],latest_review_file=rel(FOLDER/'verification.json'),observed_at=report['at'],pending_target_EU=46)
        issues['active']['2569']={'state':'COLOUR_EXPANSION_PENDING','product_id':PID,'last_accepted_EU':13,'target_EU':46,'additional_EU':33,'source_photos':'Four actual colours independently reviewed; no recolouring.','evidence':evidence}
    queue['state_counts']=dict(Counter(x['publication_state']for x in queue['rows']));queue['observed_at']=now();issues['observed_at']=now();save(qfile,queue);save(summaryfile,summary);save(issuesfile,issues)
    for work in data['workstreams']:
        if work['name']=='路崎宽头/户外全分类':work.update(status='已创建商品逐ID核当前审核、全字段、实际评分与双改；2569扩色按家族核验独立记录。',next_action='2569已取得原ID，扩色只核此ID，不新建；2520实物标记仍待核。当前数量和正式状态以本批汇总与全分类队列为准。')
    data['updated_on']=now()[:10];save(shared.REG,data)
    sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as workspace
    for path,body in workspace.build(data).items():workspace.write_generated(ROOT/path,body)
    save(FOLDER/'双改核验.json',{'at':now(),'state':report['state'],'id':PID,'target_EU':46,'accepted_EU':46 if accepted else 13,'preserved_original_SKUs':13,'additional_SKUs':33,'no_extra_product_created':True,'dossier_current':product.get('dossier_path')});print('FOUR_COLOUR_FAMILY_LOCAL_SYNC',report['state'])


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('bank','prepare','submit','verify','sync'));args=ap.parse_args()
    if args.mode=='sync':sync();return
    spec=importlib.util.spec_from_file_location('alibaba_client',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client);cfg=client.load_config(client.DEFAULT_CONFIG);native=client.native_http_json;client.http_json=lambda request,timeout=25:native(request,timeout=timeout)
    {'bank':bank,'prepare':prepare,'submit':submit,'verify':verify}[args.mode](client,cfg)


if __name__=='__main__':main()
