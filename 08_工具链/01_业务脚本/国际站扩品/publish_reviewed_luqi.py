"""Reviewed Luqi real-source offers, explicit current Schema, once-only create.

No historical builder defaults or physical-material transfers are used.
Original supplier colour aliases remain in the plan; buyer labels are explicit.
"""
from pathlib import Path
from xml.etree import ElementTree as E
from datetime import datetime,timezone
import argparse,copy,importlib.util,json,sys,hashlib
from urllib.parse import urlparse
from decimal import Decimal,ROUND_CEILING
sys.path.insert(0,str(Path(__file__).parent))
import repair_luqi_material_roles as shared
import publish_hot_rank_hr_a_batch as pub
import schema_publish_contract as contract
from read_only_catalog import read_only_call,product_readiness
ROOT=shared.ROOT;BASE=shared.BASE;FOLDER=BASE/'995准备';REG=shared.REG;STYLE='995';MODEL='BQ-LQ995';CATEGORY=201334413;PROFILE={};EU_BY_COLOR={}
SCHEMA_NAME='当前步行鞋Schema'
load,save,sha,rel,now=shared.load,shared.save,shared.sha,shared.rel,shared.now
CATALOG=ROOT/'99_临时区/路崎995/当前目录/catalog.json'
COLORS={'Black':('Black','SKU_Black'),'Beige Brown':('Black Khaki','SKU_BlackKhaki'),'Tan':('Earth Yellow','M1')}
FIELDS=['catId','icbuCatProp','saleProp','sku','productTitle','scImages','pkgMeasure','pkgWeight','ladderPeriod','priceUnit','shippingTemplate','ladderPrice','saleType','scPrice','minOrderQuantity','productDescType','detailImage','textDesc','companyImage','companyDesc','companyFaqDesc','logisticsProperty']
SUPPORTED_STYLES=('995','2576','1712','2418','868','822','2579','2575','2505','931','02412','0922','923','323','909','1628','2772','2132','9705','1680','0323F','117-1','2509','026','02505','2550','02503','K502','2539','924','1026','2593','020','ST-117','2569')


def configure(style):
    global STYLE,FOLDER,MODEL,CATEGORY,CATALOG,COLORS,PROFILE,EU_BY_COLOR,SCHEMA_NAME
    assert style in SUPPORTED_STYLES, 'Only individually reviewed current source profiles are enabled'
    STYLE=style;FOLDER=BASE/(style+'准备');MODEL='BQ-LQ'+style;CATALOG=ROOT/('99_临时区/路崎'+style+'/当前目录/catalog.json')
    facts=load(FOLDER/'当前来源与色码核对.json');assert facts['style']==style;PROFILE=facts['publish_profile'];CATEGORY=PROFILE['category_id'];assert CATEGORY in (201334413,202248402,32299)
    SCHEMA_NAME=PROFILE.get('schema_name','当前步行鞋Schema');assert SCHEMA_NAME in ('当前步行鞋Schema','当前雪地靴Schema','当前其他鞋类Schema')
    COLORS={v['buyer']:(v['supplier_key'],v['image_role']) for v in PROFILE['buyer_colours']};assert len(COLORS)==len(PROFILE['buyer_colours'])
    EU_BY_COLOR={c:facts['source_EU_by_color'][alias] for c,(alias,_) in COLORS.items()}
    assert all(v and all(type(n) is int for n in v) and len(v)==len(set(v)) for v in EU_BY_COLOR.values())


def scalar(parent,fid,typ='input',value=None):
    field=E.SubElement(parent,'field',id=fid,type=typ)
    if value is not None:E.SubElement(field,'value').text=str(value)
    return field


def choice(schema,fid,label):
    definition=schema.find("./field[@id='%s']"%fid)
    found=[o.get('value') for o in definition.findall('./options/option') if o.get('displayName').strip().casefold()==label.casefold()]
    assert len(found)==1,'Missing/ambiguous current option '+fid+'/'+label
    return found[0]


def attribute(schema,cv,name,texts):
    definitions=[d for d in schema.findall("./field[@id='icbuCatProp']/fields/field") if d.get('name')==name];assert len(definitions)==1
    d=definitions[0];typ=d.get('type');assert typ in ('singleCheck','multiCheck') and texts and (typ!='singleCheck' or len(texts)==1)
    f=scalar(cv,d.get('id'),typ);parent=E.SubElement(f,'values') if typ=='multiCheck' else f
    options={o.get('displayName').casefold():(o.get('value'),o.get('displayName')) for o in d.findall('./options/option')}
    for i,text in enumerate(texts):
        native=options.get(text.casefold())
        if native:value,label=native
        else:
            assert any(r.get('name')=='tipRule' and '负数' in r.get('value','') for r in d.findall('./rules/rule'))
            value,label=str(-701-i),text
        E.SubElement(parent,'value',inputValue=label).text=value


def failed_tls_handshake_before_http(exc):
    """Require the actual stdlib send -> connect -> TLS handshake stack.

    Response/read timeouts and generic network failures remain unknown. A
    failed initial TLS handshake precedes the business HTTP headers/body.
    Never retain signed URLs, exception messages or raw transport telemetry.
    """
    import traceback,ssl,http.client
    pending=[exc];seen=set();observed=[]
    while pending:
        current=pending.pop()
        if not isinstance(current,BaseException) or id(current) in seen:continue
        seen.add(id(current));frames=traceback.extract_tb(current.__traceback__)
        selected=[(Path(f.filename).resolve(),f.name) for f in frames]
        ssl_file=Path(ssl.__file__).resolve();http_file=Path(http.client.__file__).resolve()
        if all(pair in selected for pair in ((http_file,'send'),(http_file,'connect'),(ssl_file,'do_handshake'))) and not any(path==http_file and name in ('getresponse','_read_status') for path,name in selected):
            observed=[{'module':path.name,'function':name} for path,name in selected if path in (ssl_file,http_file)]
            return {'phase':'initial_tls_handshake','business_request_sent':False,'stdlib_stack':observed}
        pending.extend([current.__cause__,current.__context__,getattr(current,'reason',None)])
    return None


def bank(client,cfg):
    proof=load(FOLDER/'05_AI候选/整组验收.json');assert proof['state']=='VISUAL_PASS_PENDING_PUBLISH_PREFLIGHT'
    required={f'M{i}' for i in range(1,6)}|{f'D{i}' for i in range(1,5)}|{role for _,role in COLORS.values()}
    assert {x['role'] for x in proof['items']}==required and len(proof['items'])==len(required)
    file=FOLDER/'图片银行.json';data=load(file) if file.exists() else {'state':'IN_PROGRESS','items':{}}
    for item in proof['items']:
        role=item['role'];path=ROOT/item['path'];assert sha(path)==item['sha256'] and path.stat().st_size<4194304
        if role in data['items']:
            old=data['items'][role];assert old['sha256']==item['sha256']
            if old['state']=='UPLOADED':continue
            assert old['state']=='LOCAL_CALL_FAILED_BEFORE_HTTP_PROVEN' and old.get('network_request_sent') is False,'Unknown image upload must be reconciled before continuing'
        prior=data['items'].get(role);row={**item,'state':'OUTCOME_UNKNOWN_NO_RETRY','at':now()}
        if prior:row['previous_attempts']=prior.get('previous_attempts',[])+[{k:prior[k] for k in ('state','at','sha256','network_request_sent','transport_evidence') if k in prior}]
        data['items'][role]=row;save(file,data)
        try:result=client.upload_image(cfg,path,None)
        except client.ClientError as exc:
            before=failed_tls_handshake_before_http(exc)
            if before:row.update(state='LOCAL_CALL_FAILED_BEFORE_HTTP_PROVEN',network_request_sent=False,transport_evidence=before)
            else:row['transport_scope']='UNKNOWN_NO_REPLAY; no confirmed initial TLS handshake stack'
            save(file,data);raise
        row['response']=result;save(file,data);raw=result.get('upload_image_response',{})
        assert not client.api_error(result) and raw.get('file_id') and raw.get('photobank_url')
        url=raw['photobank_url'];url='https:'+url if url.startswith('//') else url.replace('http:','https:');assert urlparse(url).hostname=='sc04.alicdn.com'
        row.update(state='UPLOADED',url=url,file_id=str(raw['file_id']));save(file,data);print(role,'UPLOADED',flush=True)
    data['state']='COMPLETE';save(file,data);save(FOLDER/'图片银行公开映射.json',{'state':'COMPLETE','items':{k:{a:b for a,b in row.items() if a!='response'} for k,row in data['items'].items()}})


def prepare():
    assert not (FOLDER/'create_once.json').exists(),'Already attempted; read back or reconcile, never recreate'
    facts=load(FOLDER/'当前来源与色码核对.json');proof=load(FOLDER/'05_AI候选/整组验收.json');bank=load(FOLDER/'图片银行.json');assert bank['state']=='COMPLETE';assets=bank['items']
    fx=Decimal(str(facts['pricing_draft'].get('fx','6.6837')))
    expected_tiers=[[n,str((Decimal(facts['source_price_cny'])*m/fx).quantize(Decimal('.01'),rounding=ROUND_CEILING))]for n,m in ((2,Decimal('1.5')),(50,Decimal('1.4')),(100,Decimal('1.3')))]
    assert facts['pricing_draft']['tiers']==expected_tiers,'Current authorised cost markup requires rounding UP to USD cents'
    index=load(FOLDER/PROFILE.get('source_index','01_产品来源原图/当前来源图像索引.json'))
    assert index['style']==PROFILE.get('source_style',STYLE) and index['source']==facts['source'] and urlparse(facts['source']).hostname=='luqi.sooxie.com'
    assert 'Wide Toe Box' not in facts['title_draft'] or facts['wide_claim'].startswith('EXPLICIT_SOURCE_')
    assert proof.get('dedup_review'), 'Actual source and nearest physical-style review must precede create'
    catalog=load(CATALOG);assert catalog['complete'] and len(catalog['products'])==catalog['unique_ids']==catalog['total_item']
    registry=load(REG);sources={s['id']:s for s in registry['sources']};listings={l['id']:l for l in registry['listings']}
    assert not any(p.get('red_model')==MODEL for p in catalog['products'])
    assert not any(l.get('model')==MODEL for l in registry['listings']), 'Model already recorded locally; reconcile exact ID rather than create'
    source_urls={facts['source']}|{v['source_url'] for v in PROFILE['buyer_colours'] if v.get('source_url')}
    for v in PROFILE['buyer_colours']:
        if not v.get('source_url'):continue
        variant=next(x for x in facts['variant_sources'] if x['source']==v['source_url'])
        assert urlparse(variant['source']).hostname=='luqi.sooxie.com' and facts['source_EU_by_color'][v['supplier_key']]==variant['source_EU_by_color'][v['source_colour_key']]
        observed=load(ROOT/variant['current_source_evidence']);assert observed['source']==variant['source'] and observed['sha256']==variant['source_HTML_sha256']
        vi=ROOT/variant['current_image_index'];assert sha(vi)==variant['current_image_index_sha256'] and load(vi)['source']==variant['source']
    assert not any(sources.get(listings.get(str(p['id']),{}).get('bound_source_id'),{}).get('url','').rstrip('/') in source_urls for p in catalog['products']), 'Same source already bound; use existing ID instead'
    assert not any(sources.get(l.get('bound_source_id'),{}).get('url','').rstrip('/') in source_urls or any(route.get('source','').rstrip('/') in source_urls for route in l.get('source_routes_by_color',{}).values()) for l in registry['listings']), 'Source already bound in current registry, including creations after catalog snapshot'
    response=load(FOLDER/(SCHEMA_NAME+'.json'));schema=E.fromstring(response['data']);schema_file=FOLDER/(SCHEMA_NAME+'.xml');assert E.tostring(schema)==E.tostring(E.parse(schema_file).getroot())
    root=E.Element('itemSchema');defs={f.get('id'):f for f in schema.findall('./field')}
    for fid in FIELDS:root.append(E.Element('field',id=fid,type=defs[fid].get('type')))
    cv=E.SubElement(root.find("./field[@id='icbuCatProp']"),'complex-value')
    attribute(schema,cv,'Place of Origin',['China'])
    verified_format=E.fromstring(load(BASE/'2583-1准备/家族扩色/after_render.json')['data'])
    for name,value in [('Brand Name','Beiqiang'),('Model Number',MODEL)]:
        definition=next(f for f in schema.findall("./field[@id='icbuCatProp']/fields/field") if f.get('name')==name)
        reference=verified_format.find("./field[@id='icbuCatProp']/complex-value/field[@id='%s']"%definition.get('id'))
        assert reference is not None and reference.get('type')==definition.get('type'), 'Acquire an actually rendered representation for this current input field'
        cv.append(contract.serialize_product_attribute(schema,definition.get('id'),value,format_reference=reference))
    for name,labels in PROFILE['category_attributes'].items():attribute(schema,cv,name,labels)
    # Optional seasons/performance/width/US conversion are deliberately absent:
    # an unsupported optional value is not needed to describe this real shoe.
    for fid,value in [('catId',CATEGORY),('productTitle',facts['title_draft']),('pkgWeight','0.5'),('minOrderQuantity','2'),('productDescType','4'),('textDesc','\n'.join(facts['product_highlights_draft']))]:pub.set_direct_value(root,fid,str(value))
    for fid,label in [('priceUnit','Pair/Pairs'),('saleType','Unit'),('scPrice','Tiered pricing by quantity')]:pub.set_direct_value(root,fid,choice(schema,fid,label))
    package=E.SubElement(root.find("./field[@id='pkgMeasure']"),'complex-value')
    for name,value in [('length',34),('width',23),('height',13)]:scalar(package,name,value=value)
    period=E.SubElement(root.find("./field[@id='ladderPeriod']"),'complex-value');row=E.SubElement(scalar(period,'ladderPeriod_0','complex'),'complex-value');scalar(row,'quantity',value=100);scalar(row,'day',value=31)
    prices=E.SubElement(root.find("./field[@id='ladderPrice']"),'complex-value')
    tiers=facts['pricing_draft']['tiers']
    assert len(tiers)==3 and tiers[0][0]==2 and tiers[-1][0]==100
    for i,(quantity,price) in enumerate(tiers):
        row=E.SubElement(scalar(prices,f'ladderPrice_{i}','complex'),'complex-value');scalar(row,'quantity',value=quantity);scalar(row,'price',value=price)
    shipping=E.SubElement(root.find("./field[@id='shippingTemplate']"),'complex-value');definition=schema.find("./field[@id='shippingTemplate']/fields/field[@id='templateType']");option=next(o for o in definition.findall('./options/option') if o.get('displayName')=='FREIGHT_NEGOTIATION');scalar(shipping,'templateType','singleCheck',option.get('value'))
    cargo=[o for o in schema.findall("./field[@id='logisticsProperty']/options/option") if o.get('value')=='general_cargo_0'];assert len(cargo)==1 and cargo[0].get('displayName') in ('Ordinary goods','普货')
    normal=cargo[0].get('value');E.SubElement(E.SubElement(root.find("./field[@id='logisticsProperty']"),'values'),'value').text=normal
    sale=E.SubElement(root.find("./field[@id='saleProp']"),'complex-value');propdefs={f.get('name'):f for f in schema.findall("./field[@id='saleProp']/fields/field")}
    size_id=propdefs['EUR Size'].get('id');color_id=propdefs['Color'].get('id');sid=size_id.removeprefix('p-');cid=color_id.removeprefix('p-');assert sid.isdigit() and cid.isdigit()
    sizes=E.SubElement(scalar(sale,size_id,'multiCheck'),'values');colours=E.SubElement(scalar(sale,color_id,'multiCheck'),'values');sku=root.find("./field[@id='sku']")
    for n in sorted({n for values in EU_BY_COLOR.values() for n in values}):E.SubElement(sizes,'value',inputValue=f'EU {n}').text=str(-10000-n)
    for i,(colour,(alias,image_role)) in enumerate(COLORS.items()):
        marker=str(-200-i);E.SubElement(colours,'value',inputValue=colour,img=assets[image_role]['url']).text=marker
        for n in EU_BY_COLOR[colour]:
            row=E.SubElement(sku,'complex-values');scalar(row,'skuOuterId',value=f'{MODEL}-{colour.upper().replace(" ","-")}-EU{n}');props=E.SubElement(scalar(row,'props','multiInput'),'values')
            for prop,label,value in [(cid,colour,marker),(sid,f'EU {n}',str(-10000-n))]:E.SubElement(props,'value',propId=prop,propName='p-'+prop,propValueId=value,propValueName=label).text=prop+':'+value
    company=load(ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/bank.json');assert company['asset_version']==8;company=company['items']
    common=load(ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/通用FAQ与公司简介.json');assert len(common['companyFaqDesc'])==8
    sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/商品图片与审计'));from factory_assets import current_gallery_asset
    pub.set_main_images(root,[assets[f'M{i}'] for i in range(1,6)]+[current_gallery_asset()]);pub.set_gallery(root,'detailImage',[assets[f'D{i}'] for i in range(1,5)],[(300,'Detail shot')]*4)
    roles=[('C1',400),('C2',550),('C3',600),('C4',450),('C5',700),('C6',700)]
    options={o.get('value'):o.get('displayName') for o in schema.findall("./field[@id='companyImage']/fields/field[@id='gallery']/options/option")}
    pub.set_gallery(root,'companyImage',[company[k] for k,_ in roles],[(n,options[str(n)]) for _,n in roles]);pub.set_direct_value(root,'companyDesc',common['companyDesc'])
    faq=root.find("./field[@id='companyFaqDesc']")
    for item in common['companyFaqDesc']:
        row=E.SubElement(faq,'complex-values');scalar(row,'question',value=item['question']);scalar(row,'answers',value=item['answers'])
    xml=pub.values_only(root,operation='create',field_ids=FIELDS);assert not xml.findall(".//field[@id='skuStock']") and not xml.findall(".//field[@id='skuId']");assert len(sku.findall('./complex-values'))==sum(len(v) for v in EU_BY_COLOR.values())
    (FOLDER/'payload.xml').write_text(E.tostring(xml,encoding='unicode'),encoding='utf-8')
    evidence=rel(FOLDER/'05_AI候选/整组验收.json');candidate={'model_number':MODEL,'title':facts['title_draft'],'hero_url':assets['M1']['url'],'source':{'reference':facts['source'],'style':STYLE,'critical_facts':{'profile':'; '.join(facts['visible_structure'])},'evidence':[rel(FOLDER/'当前来源与色码核对.json'),evidence]},'search_intent':{'key':facts.get('search_intent') or facts['title_draft'],'evidence':[evidence]},'hero_review':{'url':assets['M1']['url'],'aliases':[assets['M1']['url'].replace('https:','')],'sha256':assets['M1']['sha256'],'content_key':f'Luqi{STYLE}_actual_source_selected_hero','label_status':'not_present','evidence':[evidence]}}
    records={}
    for product in catalog['products']:
        pid=str(product['id']);listing=listings.get(pid,{});source=sources.get(listing.get('bound_source_id'))
        if source:records[pid]={'source':{'reference':source['url'],'style':source['model'],'evidence':[rel(REG)]}}
    frozen_register=FOLDER/'source_register_precreate.json'
    if frozen_register.exists():assert frozen_register.read_bytes()==REG.read_bytes(), 'Prepared source snapshot differs; reconcile without overwriting evidence'
    else:frozen_register.write_bytes(REG.read_bytes())
    review={'candidate':candidate,'source_records':records,'observed_at':catalog['observed_at_utc'],'coverage_limit':f"Complete current{catalog['total_item']}ID metadata with registered source identities; exact source, nearest physical-style review and all selectedimages as recorded in visual proof. Not global all-angle or IP clearance.",'evidence_files':[{'path':str(CATALOG),'sha256':sha(CATALOG),'kind':'catalog_snapshot'},{'path':str(frozen_register),'sha256':sha(frozen_register),'kind':'source_register'},{'path':str(ROOT/evidence),'sha256':sha(ROOT/evidence),'kind':'visual_review'}]}
    save(FOLDER/'发布前差异化审查.json',review)
    manifest={'operation':'create','category_id':CATEGORY,'facts_reviewed':True,'source_evidence':[rel(FOLDER/'当前来源与色码核对.json'),evidence,'02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md'],'current_schema':SCHEMA_NAME+'.xml','current_schema_sha256':sha(schema_file),'schema_request_id':response['request_id'],'schema_acquired_at':datetime.fromtimestamp(schema_file.stat().st_mtime,timezone.utc).isoformat(),'payload_xml':'payload.xml','field_ids':FIELDS,'dependency_ids':[],'expected_model':MODEL,'differentiation_review':'发布前差异化审查.json','differentiation_review_sha256':sha(FOLDER/'发布前差异化审查.json')}
    save(FOLDER/'manifest.json',manifest);listing=pub.load_submission_manifest(FOLDER/'manifest.json','create',None)
    save(FOLDER/'prepared.json',{'at':now(),'state':'LOCAL_PREFLIGHT_PASS_NOT_CREATED','model':MODEL,'source':facts['source'],'source_price_cny':facts['source_price_cny'],'buyer_to_supplier_colour':{c:a for c,(a,_) in COLORS.items()},'EU_by_colour':EU_BY_COLOR,'EU_combinations':sum(len(v) for v in EU_BY_COLOR.values()),'fields':FIELDS,'expected_schema':contract.field_snapshot(E.fromstring(listing['xml'])),'differentiation':listing['differentiation_review'],'company_version':8,'general_faq_count':8,'materials':PROFILE['category_attributes'],'commercial_baseline':'Owner SOP MOQ2,34x23x13cm/.5kg,quantity100/day31; quotation and shipping confirmed per order. Price tiers use dated sourcecost/FX; not a market-lowest or net-profit promise.','inventory':'OMITTED_NOT_PHYSICAL_STOCK','keywords':'No deprecated keyword field submitted; buyer phrases covered naturally in title and product-specific highlights, no traffic-volume claim.'});print(STYLE,'CREATE_PREFLIGHT_PASS',sum(len(v) for v in EU_BY_COLOR.values()),'EU',flush=True)


def create(client,cfg):
    file=FOLDER/'create_once.json'
    if file.exists():print('EXISTING_CREATE_LEDGER_READBACK_OR_RECONCILE_ONLY');return
    listing=pub.load_submission_manifest(FOLDER/'manifest.json','create',None)
    with file.open('x',encoding='utf8') as f:json.dump({'state':'STARTED_OUTCOME_UNKNOWN_NO_REPLAY','model':MODEL,'at':now()},f)
    result=pub.api_submit(client,cfg,listing,False);save(FOLDER/'create_receipt.json',result);pid=pub.extract_product_id(result.get('response') or {})
    save(file,{'state':result['status'],'product_id':pid,'at':result['attempted_at'],'model':MODEL,'refs':result.get('refs')});print(json.dumps({'state':result['status'],'product_id':pid}),flush=True)


def verify(client,cfg):
    receipt=load(FOLDER/'create_receipt.json');pid=pub.extract_product_id(receipt.get('response') or {});assert pid and receipt['status']=='submitted_needs_readback'
    # A local post-response bookkeeping exception must never trigger create
    # again. Reconcile saved positive business result with exact-ID formal get.
    got=read_only_call(client,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});save(FOLDER/'after_get.json',got);p=got.get('product');assert p and shared.attributes(p).get('Model Number')==[MODEL]
    save(FOLDER/'create_once.json',{'state':receipt['status'],'product_id':pid,'at':receipt['attempted_at'],'model':MODEL,'refs':receipt.get('refs'),'reconciled_saved_receipt_and_exact_model_get':True,'get_request_id':got['request_id'],'no_replayed_create':True})
    report={'id':pid,'style':STYLE,'at':now(),'state':product_readiness(p['status']),'status':p['status'],'display':p['display'],'actual_score':None,'get_observed_at':now(),'inventory_write':'OMITTED_NOT_PHYSICAL_STOCK','public_qa':'NOT_PUBLICLY_TESTED_BATCH_API_POLICY'}
    if report['state']!='APPROVED' or p['display']!='Y':save(FOLDER/'verification.json',report);print(json.dumps(report));return
    rendered=read_only_call(client,cfg,'alibaba.icbu.product.schema.render',{'param_product_top_publish_request':{'product_id':int(pid),'cat_id':CATEGORY,'language':'en_US'}});save(FOLDER/'after_render.json',rendered)
    if not rendered.get('data'):report['state']='EDITABLE_SCHEMA_UNAVAILABLE';save(FOLDER/'verification.json',report);return
    schema=E.fromstring(rendered['data']);(FOLDER/'after_schema.xml').write_text(rendered['data'],encoding='utf8');actual=contract.field_snapshot(schema);expected=load(FOLDER/'prepared.json')['expected_schema'];checks={}
    overlay_file=FOLDER/'价格取整修正/current_expected_overlay.json'
    if overlay_file.exists():
        overlay=load(overlay_file);assert overlay['product_id']==pid and overlay['operation']=='price_rounding_only'
        receipt_file=ROOT/overlay['receipt'];assert receipt_file.parent==overlay_file.parent
        price_receipt=load(receipt_file);assert price_receipt['status']=='submitted_needs_readback'
        assert sha(overlay_file.parent/'payload.xml')==overlay['payload_sha256']
        assert set(overlay['expected_schema'])=={'ladderPrice'}
        expected=copy.deepcopy(expected);expected.update(overlay['expected_schema'])
    for fid,value in expected.items():
        if fid not in ('sku','icbuCatProp'):checks['schema_'+fid]=contract.created_field_equivalent(fid,value,actual.get(fid))
    # Exact9705 get and render both replace U+2019 with ASCII apostrophe.
    # Only this evidenced typography difference in textDesc is equivalent;
    # no punctuation, words, other fields or products are ignored.
    if STYLE=='9705' and not checks.get('schema_textDesc'):
        def straight_apostrophe(value):
            if isinstance(value,str):return value.replace('\u2019',"'")
            if isinstance(value,list):return [straight_apostrophe(v) for v in value]
            if isinstance(value,dict):return {k:straight_apostrophe(v) for k,v in value.items()}
            return value
        converted=straight_apostrophe(expected['textDesc'])
        assert converted!=expected['textDesc'], 'Do not accept an unevidenced mismatch'
        checks['schema_textDesc']=contract.created_field_equivalent('textDesc',converted,actual.get('textDesc'))
        report['text_format_scope']='9705 textDesc only: U+2019 to ASCII apostrophe, observed in exact-ID get and render; every word and all other fields still exact.'
    logistics=schema.findall("./field[@id='logisticsProperty']/values/value")
    # Current render adds only descriptive annotations to the SAME ordinary-
    # goods option. Check the exact ID, validity and its current option label;
    # do not ignore arbitrary attributes or accept a different goods class.
    options={o.get('value'):o.get('displayName') for o in schema.findall("./field[@id='logisticsProperty']/options/option")}
    ordinary_labels={'Ordinary goods','普货','普貨'}
    # Exact1712 render pairs English selected label with Chinese current
    # option label under the SAME ID. Exact02505 also returns Traditional
    # Chinese 普貨 for the option and Simplified 普货 for selected metadata.
    checks['schema_logisticsProperty']=len(logistics)==1 and logistics[0].text=='general_cargo_0' and set(logistics[0].attrib)<= {'valid','displayName'} and logistics[0].get('valid','true')=='true' and logistics[0].get('displayName') in ordinary_labels and options.get('general_cargo_0') in ordinary_labels
    sku=contract.verify_create_skus(expected['sku'],actual.get('sku'));checks['sku_schema_bindings']=sku['status']=='verified'
    attrs=shared.attributes(p);checks['formal_brand_model_materials']=attrs.get('Brand Name')==['Beiqiang'] and attrs.get('Model Number')==[MODEL] and all(sorted(v.casefold() for v in attrs.get(name,[]))==sorted(v.casefold() for v in labels) for name,labels in PROFILE['category_attributes'].items())
    checks['origin_china']=attrs.get('Place of Origin') in (['China'],['CN'])
    trade=p['sourcing_trade'];checks['moq_pair_usd']=str(trade['min_order_quantity'])=='2' and trade['fob_currency']=='USD' and trade['min_order_unit_type']=='Pair' and trade['fob_unit_type']=='Pair'
    checks['category_exact']=int(p['category_id'])==CATEGORY
    definitions={f.get('name'):f.get('id').removeprefix('p-') for f in E.parse(FOLDER/(SCHEMA_NAME+'.xml')).getroot().findall("./field[@id='saleProp']/fields/field")};cid,sid=definitions['Color'],definitions['EUR Size']
    axes={str(a['attribute_id']):a['values'] for a in p['product_sku']['sku_attributes']};col={str(v['value_id']):v['system_value_name'] for v in axes[cid]};sz={str(v['value_id']):v['system_value_name'] for v in axes[sid]}
    from collections import Counter
    pairs=Counter();tiers=sorted((int(q),Decimal(pr)) for q,pr in load(FOLDER/'当前来源与色码核对.json')['pricing_draft']['tiers']);price_match=True
    for row in p['product_sku']['skus']:
        prop=json.loads(row['attr2_value']);pairs[(col[str(prop[cid])],sz[str(prop[sid])])]+=1;price_match&=sorted((int(x['start_quantity']),Decimal(x['price'])) for x in row['bulk_discount_prices'])==tiers
    checks['exact_colour_EU_combinations']=pairs==Counter((c,f'EU {n}') for c in COLORS for n in EU_BY_COLOR[c]);checks['all_sku_three_tiers']=price_match
    facts=load(FOLDER/'当前来源与色码核对.json');expected_highlights='\n'.join(facts['product_highlights_draft'])
    if STYLE=='9705':expected_highlights=expected_highlights.replace('\u2019',"'")
    checks['title_and_highlights_exact']=p['subject']==facts['title_draft'] and p['struct_detail']['product_summary']==expected_highlights
    common=load(ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/通用FAQ与公司简介.json');company=load(ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/bank.json')['items'];sd=p['struct_detail'];checks['general8faq_exact']=sd['product_faq']==[{'question':x['question'],'answer':x['answers']} for x in common['companyFaqDesc']];checks['company_intro_exact']=sd['company_summary']==common['companyDesc'];checks['company6_roles_exact']=Counter((str(x['image_set']['id']),contract._created_image_identity(x['image_url'])) for x in sd['company_image']['images'])==Counter((r,contract._created_image_identity(company[c]['url'])) for c,r in [('C1','400'),('C2','550'),('C3','600'),('C4','450'),('C5','700'),('C6','700')])
    bank=load(FOLDER/'图片银行.json')['items'];sale=pub.values_only(schema,operation='update',field_ids=['saleProp']);colors={v.get('inputValue'):v.get('img') for v in sale.findall("./field/complex-value/field[@id='p-%s']/values/value"%cid)};checks['all_colour_images_exact']=set(colors)==set(COLORS) and all(contract._created_image_identity(colors[c])==contract._created_image_identity(bank[r]['url']) for c,(_,r) in COLORS.items())
    report.update(checks=checks,failed=[k for k,v in checks.items() if not v],sku_bindings=sku.get('bindings',{}),sku_diagnostic=sku.get('reason'),state='FORMAL_FIELDS_PASS_PENDING_SCORE' if all(checks.values()) else 'FORMAL_MISMATCH')
    enc=client.top_call(cfg,'alibaba.icbu.product.id.encrypt',{'product_id':pid,'language':'ENGLISH'});assert enc.get('secret_id')
    try:
        score=read_only_call(client,cfg,'alibaba.icbu.product.score.get',{'product_id':enc['secret_id']});save(FOLDER/'score.json',score);result=score.get('result',{});report['actual_score']=result.get('final_score');diag=result.get('problem_map') or {};diag=json.loads(diag) if isinstance(diag,str) else diag;report['score_diagnostics']=diag
        if all(checks.values()) and report['actual_score'] is not None:report['state']='FORMAL_FIELDS_SCORE_PASS' if Decimal(str(report['actual_score']))>=5 and not any(diag.get('extendProblemMap',{}).values()) and not diag.get('errorReasonList') else 'FORMAL_FIELDS_PASS_SCORE_BELOW_TARGET'
    except shared.ReadBusinessError as exc:report['score_read_error']=exc.api_evidence
    save(FOLDER/'verification.json',report);print(json.dumps({k:report[k] for k in ('id','state','actual_score','failed')}),flush=True)


def sync():
    from PIL import Image
    receipt=load(FOLDER/'create_receipt.json');pid=pub.extract_product_id(receipt.get('response') or {});assert pid and receipt['status']=='submitted_needs_readback'
    report=load(FOLDER/'verification.json');got=load(FOLDER/'after_get.json');p=got['product'];assert shared.attributes(p)['Model Number']==[MODEL]
    registry=load(REG);product=next(x for x in registry['products'] if x['id']=='LQ-'+STYLE);facts=load(FOLDER/'当前来源与色码核对.json');source=next(s for s in registry['sources'] if s['url'].rstrip('/')==facts['source']);sid=source['id']
    product['dossier_path']=f'02_Alibaba运营/02_单品优化记录/商品档案/LQ-{STYLE}/README.md'
    product['classification']={**product.get('classification',{}),'local_intent_candidates':PROFILE['local_intent'],'state':'REAL_SOURCE_PHOTOS_AND_CURRENT_SCHEMA_REVIEWED','platform_category_ids':[CATEGORY],'platform_category_state':'CURRENT_EXACT_ID_API_OBSERVED'}
    source['latest_price_review']={'observed_at':facts['observed_at'],'price_cny':facts['source_price_cny'],'evidence':rel(FOLDER/'当前来源与色码核对.json'),'scope':'公开来源当次标价；非实物库存、已采购或固定报价。'}
    source['evidence']=list(dict.fromkeys(source.get('evidence',[])+[rel(FOLDER/'当前来源与色码核对.json')]))
    routes={}
    for v in PROFILE['buyer_colours']:
        url=v.get('source_url',facts['source']);route_source=next(s for s in registry['sources'] if s['url'].rstrip('/')==url);route_id=route_source['id'];colour=v['buyer']
        routes[colour]={'source':url,'source_id':route_id,'source_artno':v.get('supplier_artno',PROFILE.get('source_artno',STYLE)),'supplier_color':v['supplier_label'],'EU':EU_BY_COLOR[colour]}
        if url!=facts['source']:
            variant=next(x for x in facts['variant_sources'] if x['source']==url)
            route_source['latest_price_review']={'observed_at':variant['observed_at'],'price_cny':variant['source_price_cny'],'evidence':variant['current_source_evidence'],'scope':'Exact variant public reference cost, not stock or fixed quotation.'}
            route_source['evidence']=list(dict.fromkeys(route_source.get('evidence',[])+[variant['current_source_evidence'],rel(FOLDER/'当前来源与色码核对.json')]))
            product['related_source_ids']=list(dict.fromkeys(product.get('related_source_ids',[])+[route_id]))
    assert not any(l['model']==MODEL and l['id']!=pid for l in registry['listings']), 'Model already has another ID; reconcile rather than append'
    listing=next((l for l in registry['listings'] if l['id']==pid),None)
    if listing is None:
        listing={'id':pid,'product_id':'LQ-'+STYLE,'model':MODEL,'url':p.get('pc_detail_url') or f'https://www.alibaba.com/product-detail/_{pid}.html','record_type':'已创建实款；审核与评分分列','source_relation':'SOURCE_REVIEWED_CREATE_PENDING_FORMAL_ACCEPTANCE','evidence':[]};registry['listings'].append(listing)
    canonical=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid;canonical.mkdir(parents=True,exist_ok=True)
    save(canonical/'formal_get.json',{'requested_product_id':pid,'observed_at_utc':report['get_observed_at'],'method':'alibaba.icbu.product.get','response':shared.sanitized(got),'sanitized_fields':['owner_member','owner_member_display_name','owner_member_id'],'raw_response_file':rel(FOLDER/'after_get.json'),'acceptance_state':report['state']})
    if (FOLDER/'after_render.json').exists():save(canonical/'formal_render.json',load(FOLDER/'after_render.json'))
    evidence=[rel(FOLDER/name) for name in ('当前来源与色码核对.json','prepared.json','manifest.json','图片银行公开映射.json','create_once.json','create_receipt.json','verification.json','score.json') if (FOLDER/name).exists()]
    current={'at':report['get_observed_at'],'title':p['subject'],'keywords':p.get('keywords',[]),'main_images':p['main_image']['images'],'category_id':p['category_id'],'status':p['status'],'display':p['display'],'url':listing['url'],'scope':'ExactID formal product read; current audit/score accepted only if the separate verification state passes.'}
    listing.update(current_platform_fields=current,catalog_fields=copy.deepcopy(current),formal_fields={'file':rel(canonical/'formal_get.json'),'at':report['get_observed_at'],'scope':'当前API商品对象；审核、字段和实际评分按独立verification状态，不把待审当完成'},local_sync={'state':report['state'],'current_fields_file':rel(canonical/'formal_get.json'),'current_schema_file':rel(canonical/'formal_render.json') if (canonical/'formal_render.json').exists() else None,'source_fact_file':rel(FOLDER/'当前来源与色码核对.json'),'at':report['at']},observation={'audit':p['status'],'display':p['display'],'at':report['get_observed_at'],'score':report['actual_score'],'scope':'Full exact-ID API read, not browser presentation or physicalstock proof.'})
    listing.setdefault('optimization',{})['real_source_creation']={'state':report['state'],'source_id':sid,'source_artno':PROFILE.get('source_artno',STYLE),'at':report['at'],'evidence':evidence,'inventory_write':'OMITTED','next_action':'Only formal readback and exact field/score diagnosis; never repeat create or upload successful assets.'}
    listing['evidence']=list(dict.fromkeys(listing['evidence']+evidence));product['evidence']=list(dict.fromkeys(product.get('evidence',[])+evidence));product.setdefault('local_assets',{}).update(current_fields_file=rel(canonical/'formal_get.json'),source_fact_file=rel(FOLDER/'当前来源与色码核对.json'),asset_roots=[rel(FOLDER/'05_AI候选')],state=report['state']);original_root=ROOT/PROFILE['source_original_root'] if PROFILE.get('source_original_root') else FOLDER/PROFILE.get('original_dir','01_产品来源原图');assert original_root.is_dir();product['raw_packages']=[rel(original_root)];product['next_action']=f'仅回读原ID审核、全字段与实际评分；不重复上传或创建{STYLE}，其他路崎款独立推进。'
    product['source_routes_by_color']=routes;listing['source_routes_by_color']=copy.deepcopy(routes)
    deferred=facts.get('deferred_source_options',{})
    if deferred:
        assert not set(deferred)&set(facts['source_EU_by_color']) and all(v and len(v)==len(set(v)) for v in deferred.values())
        product['deferred_source_options']={'colours':copy.deepcopy(deferred),'EU_combinations':sum(map(len,deferred.values())),'reason':'Clear independent actual colour photos pending; these choices are not published.','evidence':rel(FOLDER/'当前来源与色码核对.json')}
    for root in PROFILE.get('additional_original_roots',[]):
        path=ROOT/root;assert path.is_dir();product['raw_packages']=list(dict.fromkeys(product['raw_packages']+[rel(path)]))
    accepted=report['state'] in ('FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE','FORMAL_FIELDS_PASS_SCORE_BELOW_TARGET')
    if accepted:
        listing['bound_source_id']=sid;listing['source_relation']='REAL_SOURCE_FORMAL_FIELDS_PASS';product.update(source_state='ADOPTED',adopted_source_id=sid,candidate_source_ids=[])
        listing['record_type']='当前实款正式绑定';product['next_action']=f'当前实款、来源、图文和{sum(map(len,EU_BY_COLOR.values()))}EU正式一致；实际评分按当前核验，无需再创建{STYLE}，继续剩余路崎款。'
        if deferred:product['next_action']+=f' 本款另有{sum(map(len,deferred.values()))}EU颜色组合待清晰实图，未发布；资料齐后仅扩原ID。'
        cache_path=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json';cache=load(cache_path);bank=load(FOLDER/'图片银行.json')['items'];mapping={contract._created_image_identity(row['url']):row for row in bank.values()}
        for row in load(ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/bank.json')['items'].values():mapping[contract._created_image_identity(row['url'])]=row
        sd=p['struct_detail'];roles={'main':p['main_image']['images'],'details':[x['image_url'] for x in sd['detail_image']['images']],'company':[x['image_url'] for x in sd['company_image']['images']],'sku':[v['image_url'] for a in p['product_sku']['sku_attributes'] for v in a['values'] if v.get('image_url')],'html':[]}
        for urls in roles.values():
            for url in urls:
                row=mapping[contract._created_image_identity(url)];path=ROOT/row['path'];assert sha(path)==row['sha256'];w,h=Image.open(path).size;cache['assets'][url]={'state':'SAVED','file':row['path'],'sha256':row['sha256'],'bytes':path.stat().st_size,'width':w,'height':h,'pixel_qa':'Selected local actual-source-preserving image reviewed; formal CDN identity matches official upload, no browser claim.','at':report['get_observed_at']}
        cache['products'][pid]=roles;cache['urls']=len(cache['assets']);cache['saved_urls']=sum(x.get('state')=='SAVED' for x in cache['assets'].values());cache['unique_files']=len({x['sha256'] for x in cache['assets'].values() if x.get('state')=='SAVED'});cache['errors']=sum(x.get('state')!='SAVED' for x in cache['assets'].values());save(cache_path,cache)
    queue_file=BASE/'质量复核_2026-10-09/全分类处理队列.json';queue=load(queue_file)
    row=next(r for r in queue['rows'] if r['style']==STYLE);row.update(publication_state='CREATED_APPROVED_Y' if accepted else 'SUBMITTED_'+report['state'],product_id=pid,EU_combinations=sum(map(len,EU_BY_COLOR.values())),actual_score=report['actual_score'],score_status=report['state'],current_platform_evidence=rel(FOLDER/'verification.json'),preparation_evidence=rel(FOLDER/'prepared.json'))
    selected=load(FOLDER/'05_AI候选/整组验收.json');assert selected['state']=='VISUAL_PASS_PENDING_PUBLISH_PREFLIGHT'
    legacy_995=STYLE=='995' and selected.get('all_eleven_full_images_and_contact_actually_viewed') is True and len(selected['items'])==11
    assert all(sha(ROOT/x['path'])==x['sha256'] and (x.get('decision')=='SELECTED_VISUAL_PASS' or legacy_995 and 'decision' not in x) for x in selected['items'])
    row.update(source_collection='CURRENT_SOURCE_COLLECTED',image_cache='CURRENT_SOURCE_AND_FINAL_ASSETS',title_quality='LOCAL_REVIEW_PASS_FORMAL_MATCH' if accepted else 'LOCAL_REVIEW_PASS_PENDING_FORMAL',image_quality='BUYER_ROLE_REVIEW_PASS',image_apply_scope='PASS_COMPLETE_IMAGE_SCHEMA' if accepted else 'LOCAL_SELECTED_PENDING_FORMAL',current_source_evidence=rel(FOLDER/'当前来源与色码核对.json'),current_visual_evidence=rel(FOLDER/'05_AI候选/整组验收.json'),browser_policy='CURRENT_BATCH_FULL_API_NO_PER_PRODUCT_BROWSER')
    row['local_issue']='Source material wording conflict handled by omitting composition claims; see current source facts.' if facts.get('material_conflicts') else ''
    if deferred:
        row.update(deferred_source_options=copy.deepcopy(deferred),deferred_EU_combinations=sum(map(len,deferred.values())),local_issue='Only selected colours are published; other source colours await clear independent actual photos. Excluded conflicting source frames remain excluded.')
        issue_file=BASE/'待补资料与局部问题.json';issues=load(issue_file);issues['active'][STYLE]={'state':'PARTIAL_SOURCE_COLOURS_PENDING','published_colour_scope':list(COLORS),'published_EU_combinations':sum(map(len,EU_BY_COLOR.values())),'product_id':pid,'publication_state':report['state'],'deferred_source_options':copy.deepcopy(deferred),'deferred_EU_combinations':sum(map(len,deferred.values())),'issue':'Selected colour scope only; other colours not published. Excluded conflicting underside photos not adopted.','evidence':[rel(FOLDER/'当前来源与色码核对.json'),rel(FOLDER/'身份一致性核验.json')]};issues['observed_at']=now();save(issue_file,issues)
    from collections import Counter
    queue['state_counts']=dict(Counter(r['publication_state'] for r in queue['rows']));queue['observed_at']=now()
    for work in registry['workstreams']:
        if work['name']=='路崎宽头/户外全分类':
            pending=[r['style'] for r in queue['rows'] if r['publication_state'].startswith(('HOLD_','PENDING_'))]
            deferred_counts={r['style']:r['deferred_EU_combinations'] for r in queue['rows'] if r.get('deferred_EU_combinations')}
            work.update(status='已创建商品逐ID核审核、全字段、实际评分与双改；来源合并不重复新建；部分颜色待修与已发布范围分列。',next_action=f'已取得ID仅回读或原ID修正，不重建。来源/单款准备待办：{pending}；未发布的颜色EU组合：{deferred_counts}。当前数量与通过状态见本批正式汇总及全分类队列。')
    registry['updated_on']=datetime.now(timezone.utc).date().isoformat();save(queue_file,queue);save(REG,registry)
    summary_file=BASE/'本批正式商品汇总.json';summary=load(summary_file);row=next((r for r in summary if str(r['product_id'])==pid),None)
    if row is None:row={'style':STYLE,'product_id':pid};summary.append(row)
    row.update(url=listing['url'],status=p['status'],display=p['display'],sku_count=len(p.get('product_sku',{}).get('skus',[])),score=report['actual_score'],observed_at=report['get_observed_at'],latest_review_scope=report['state'],latest_review_file=rel(FOLDER/'verification.json'));save(summary_file,summary)
    sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as workspace
    for path,body in workspace.build(registry).items():workspace.write_generated(ROOT/path,body)
    facts['state']='CREATED_'+report['state'];facts['publication']={'product_id':pid,'audit':p['status'],'display':p['display'],'actual_score':report['actual_score'],'formal_verification':rel(FOLDER/'verification.json'),'local_sync_at':now(),'no_replayed_create':True};facts['next_action']='仅回读和诊断原ID；不重复创建或重传成功素材。' if report['state']!='FORMAL_FIELDS_SCORE_PASS' else '该款正式字段、评分与来源已通过；继续其他款，不重复创建。'
    if deferred:facts['next_action']+=f' 本款另有{sum(map(len,deferred.values()))}EU颜色组合未发布，待清晰实图后仅扩原ID。'
    save(FOLDER/'当前来源与色码核对.json',facts)
    double_proof={'at':now(),'id':pid,'state':report['state'],'source_id':sid,'source_url':facts['source'],'current_dossier':product.get('dossier_path'),'no_duplicate_create':True,'color_aliases':load(FOLDER/'prepared.json')['buyer_to_supplier_colour']}
    if deferred:double_proof.update(published_EU_combinations=sum(map(len,EU_BY_COLOR.values())),deferred_source_options=copy.deepcopy(deferred),deferred_EU_combinations=sum(map(len,deferred.values())))
    save(FOLDER/'双改核验.json',double_proof);print(STYLE,'LOCAL_SYNC',pid,report['state'])


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('schema','bank','prepare','create','verify','sync'));ap.add_argument('--style',required=True,choices=SUPPORTED_STYLES);ap.add_argument('--http-transport',choices=('urllib','native'),default='urllib',help='Existing official-client verified-TLS transport; no trust/proxy overrides or unknown write replay');args=ap.parse_args();configure(args.style)
    if args.mode in ('verify','sync')and(FOLDER/'create_receipt.json').exists():
        pid=pub.extract_product_id(load(FOLDER/'create_receipt.json').get('response')or{})
        import normalize_models_factory_gallery as current
        if pid and(current.BASE/'商品'/pid/'update_once.json').exists():
            if args.mode=='sync':
                import sync_models_factory_gallery as latest;latest.main();return
            row=next(z for z in load(current.BASE/'范围.json')['targets']if z['id']==pid);client,cfg=current.b.api_client();client.http_json=client.native_http_json
            print(json.dumps(current.operate(row,'verify',client,cfg),ensure_ascii=False));return
    family=None
    if args.style=='2569' and args.mode in ('verify','sync') and (FOLDER/'家族扩色/update_once.json').exists():
        family_spec=importlib.util.spec_from_file_location('current_2569_expansion',ROOT/'08_工具链/01_业务脚本/国际站扩品/expand_luqi_2569_colours.py');family=importlib.util.module_from_spec(family_spec);family_spec.loader.exec_module(family)
        if args.mode=='sync':family.sync();return
    if args.mode=='prepare':prepare();return
    if args.mode=='sync':sync();return
    spec=importlib.util.spec_from_file_location('alibaba_client',ROOT/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client);cfg=client.load_config(client.DEFAULT_CONFIG)
    original=client.native_http_json if args.http_transport=='native' else client.http_json;client.http_json=lambda request,timeout=25:original(request,timeout=timeout)
    if args.mode=='schema':
        result=read_only_call(client,cfg,'alibaba.icbu.product.schema.get',{'param_product_top_publish_request':{'cat_id':CATEGORY,'language':'en_US'}});assert result.get('data') and result.get('request_id');E.fromstring(result['data']);save(FOLDER/(SCHEMA_NAME+'.json'),result);(FOLDER/(SCHEMA_NAME+'.xml')).write_text(result['data'],encoding='utf8');print(STYLE,'CURRENT_SCHEMA_SAVED')
    elif args.mode=='bank':bank(client,cfg)
    elif args.mode=='create':create(client,cfg)
    else:(family.verify if family is not None else verify)(client,cfg)


if __name__=='__main__':main()
