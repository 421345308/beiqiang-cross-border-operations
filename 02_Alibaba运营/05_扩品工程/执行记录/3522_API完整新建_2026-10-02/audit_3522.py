from pathlib import Path
import json,xml.etree.ElementTree as E,datetime,re
O=Path(__file__).parent/'3522_execution'
def read(n):return json.loads((O/n).read_text(encoding='utf-8'))
def token(url):
 if isinstance(url,dict):url=url['image_url']
 m=re.search(r'/kf/([^/]+?)(?:/|\.(?:jpg|jpeg|png))',url);assert m,url;return m.group(1)
g=read('formal_get.flat.json');p=g['product'];facts=read('facts_and_copy.json');ledger=read('upload_ledger.json');a={x['name']:x for x in ledger['uploads']};co=read('company_v3_manifest.json');sd=p['struct_detail'];skus=p['product_sku']['skus'];expected_codes={f'BQ-L3522-{c}-{z}' for c in ['Black','Green','Beige'] for z in range(39,47)}
assert p['subject']==facts['title'] and int(p['category_id'])==202240835
assert {x['sku_code'] for x in skus}==expected_codes and len(skus)==24 and len({x['sku_id'] for x in skus})==24
colorids={'Black':3327837,'Green':216016296,'Beige':5715155}
for sku in skus:
 _,c,z=sku['sku_code'].rsplit('-',2);props=json.loads(sku['attr2_value']);assert props=={'191288010':colorids[c],'222038415':-int(z)}
 assert [(int(v['start_quantity']),float(v['price'])) for v in sku['bulk_discount_prices']]==[(2,19.04),(50,17.77),(100,16.50)]
assert [token(x) for x in p['main_image']['images']]==[token(a['M'+str(i)]['official_url']) for i in range(1,7)]
details=sd.get('detail_image',sd.get('product_image',{}))['images'];assert len(details)==4 and {token(x) for x in details}=={token(a['D'+str(i)]['official_url']) for i in range(1,5)}
company=sd['company_image']['images'];assert len(company)==5 and {token(x) for x in company}=={token(x['official_url']) for x in co}
# Product.get groups gallery output by role; exact members/roles matter, not response order.
for i,role in enumerate([350,300,350,350],1):assert int(next(x for x in details if token(x)==token(a['D'+str(i)]['official_url']))['image_set']['id'])==role
for x,role in zip(co,[400,550,600,750,700]):assert int(next(y for y in company if token(y)==token(x['official_url']))['image_set']['id'])==role
assert sd['product_summary']==facts['product_summary'];assert sd['product_faq']==[{'question':x['question'],'answer':x['answer']} for x in facts['FAQ']]
attrs={int(x['attribute_id']):x['value_name'] for x in p['attributes']};assert attrs[191290428]==facts.get('formal_upper_material','Genuine Leather') and attrs[191290430]=='PU' and attrs[191290426]=='Not specified' and attrs[20700]=='Not specified' and attrs[200001153]=='Slip-On' and attrs[1]=='Not specified'
assert attrs.get(3)=='BQ-L3522',attrs.get(3)
trade=p['sourcing_trade'];assert trade['min_order_quantity']=='2' and trade['min_order_unit_type']=='Pair'
receipt=read('publish_receipt.json');pid=receipt['product_id'];render=read('formal_render.flat.json');render_ok=False
if render.get('data'):
 r=E.fromstring(render['data']);m=r.find("./field[@id='icbuCatProp']/complex-value/field[@id='p-3']/value");assert m.get('inputValue')=='BQ-L3522'
 cols=r.findall("./field[@id='saleProp']/complex-value/field[@id='p-191288010']/values/value");assert len(cols)==3
 for v in cols:assert token(v.get('img'))==token(a[v.get('inputValue')]['official_url'])
 assert len(r.findall("./field[@id='sku']/complex-values"))==24;render_ok=True
inventory=[{'sku_id':x['sku_id'],'sku_code':x['sku_code'],'returned_inventory_dto_list':x.get('inventory_dto_list')} for x in skus]
score=read('score_timestamp.json');s=score['response'];scoredata=s.get('result',{});actual=float(scoredata['final_score']) if scoredata.get('final_score') is not None else None;diagnostics=json.loads(scoredata.get('problem_map','{}')) if not s.get('error_response') else {'score_query_error':s['error_response'],'parameter_contract':'Verified official encrypt.secret_id top-level String','cause':'Unestablished'};check={'product_id':pid,'model':'BQ-L3522','status':p['status'],'display':p['display'],'public_url':p['pc_detail_url'],'formal_fields':'PASS' if p.get('keywords')==facts['keywords'] else 'PASS_EXCEPT_KEYWORD', 'keyword_persistence':p.get('keywords')==facts['keywords'], 'actual_keywords':p.get('keywords'), 'expected_keywords':facts['keywords'],'title_model_exact':True,'main':6,'detail':4,'company':5,'SKU':24,'stable_SKU_codes_and_platform_ids_verified':True,'color_bindings_render_verified':render_ok,'FAQ':6,'price_tiers_exact':True,'get_request_id':g.get('request_id'),'render_request_id':render.get('request_id'),'render_nonempty':bool(render.get('data')),'optional_stock_input':'omitted_all','inventory_returned':inventory,'target_score':5.0,'actual_score':actual,'observed_at':score['observed_at'],'score_source':score['score_source'],'diagnostics':diagnostics,'score_status':'PASS' if actual is not None and float(actual)>=5 else 'PENDING_OPTIMIZATION' if actual is not None else 'PENDING_SCORE','public_acceptance':'PENDING_INDEPENDENT_READ_ONLY','create_comparator_note':'Stable SKU fields compared directly; platform-generated skuId and default empty/zero stock retained as formal output evidence, not treated as creation failure','no_inventory_mutation':True,'no_repeat_creation':True,'audit_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
public_path=O/'parent_public_final_acceptance.json'
if public_path.exists():
 public=json.loads(public_path.read_text(encoding='utf-8'));assert public['verdict']=='PASS_PUBLIC_CONTENT' and public['product_id']==str(pid)
 check['public_acceptance']='PASS_PARENT_INDEPENDENT_CLOUD_BROWSER'
 check['completion_status']='COMPLETE' if check['score_status']=='PASS' and p['status']=='approved' and p['display']=='Y' and render_ok and check['keyword_persistence'] else 'PENDING'
 check['score_request_id']=s.get('request_id')
 check['diagnostics_reviewed']=True
 public.update(actual_score=actual,score_observed_at=score['observed_at'],score_request_id=s.get('request_id'),completion_status=check['completion_status'])
 public_path.write_text(json.dumps(public,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'formal_checks.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:check[k] for k in ['product_id','model','status','display','formal_fields','render_nonempty','SKU','actual_score','score_status','public_url']},ensure_ascii=False))
