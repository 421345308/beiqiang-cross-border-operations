"""Audit independently saved get/render/score; no network or platform write."""
from pathlib import Path
from collections import defaultdict,Counter
from xml.etree import ElementTree as E
import json,sys,copy
from datetime import datetime,timezone
import replace_hr_real_sources as o
def check(pid,family,variant):
 if not(o.BASE/'商品'/pid/'after_get.json').exists():
  return {'id':pid,'state':'LOCAL_PREPARATION_NOT_FORMALLY_SUBMITTED'}
 f=o.BASE/'商品'/pid;got=o.b.load(f/'after_get.json');p=got['product'];report={'id':pid,'at':o.b.now(),'state':'REVIEWING','status':p['status'],'display':p['display']}
 if p['status']!='approved':o.b.save(f/'verification.json',report);return report
 missing=[name for name in ['prepared.json','after_render.json','score.json']if not(f/name).exists()]
 if missing:
  report.update(state='FORMAL_EVIDENCE_INCOMPLETE',missing_files=missing)
  o.b.save(f/'verification.json',report);print(pid,report['state'],missing);return report
 prep=o.b.load(f/('business_correction_prepared.json'if(f/'business_correction_once.json').exists()else'prepared.json'));schema=E.fromstring(o.b.load(f/'after_render.json')['data']);actual=o.contract.field_snapshot(schema);checks={}
 if(f/'gallery_repair_prepared.json').exists():prep['expected_schema']['scImages']=o.b.load(f/'gallery_repair_prepared.json')['expected_schema']['scImages']
 if(f/'hero_quality_prepared.json').exists():prep['expected_schema']['scImages']=o.b.load(f/'hero_quality_prepared.json')['expected_schema']['scImages']
 if(f/'title_quality_prepared.json').exists():prep['expected_schema']['productTitle']=o.b.load(f/'title_quality_prepared.json')['expected_schema']['productTitle']
 if(f/'group_quality_prepared.json').exists():prep['expected_schema']['productGroup']=o.b.load(f/'group_quality_prepared.json')['expected_schema']['productGroup']
 if(f/'company_quality_prepared.json').exists():
  correction=o.b.load(f/'company_quality_prepared.json');prep['expected_schema'].update(correction['expected_schema']);prep['fields']=list(set(prep['fields'])|set(correction['fields']))
 last=max((o.b.load(f/name).get('at','')for name in ['update_once.json','attribute_repair_once.json','gallery_repair_once.json','public_style_once.json','hero_quality_once.json','business_correction_once.json','optional_attribute_clear_once.json','title_repair_once.json','title_quality_once.json','group_quality_once.json','company_quality_once.json']if(f/name).exists()),default='')
 checks['formal_read_after_latest_write']=datetime.fromtimestamp((f/'after_get.json').stat().st_mtime,timezone.utc).isoformat()>last and datetime.fromtimestamp((f/'score.json').stat().st_mtime,timezone.utc).isoformat()>last
 for key,value in prep['expected_schema'].items():
  if key in ['sku','icbuCatProp','productKeywords']:continue
  checks[key]=o.contract.created_field_equivalent(key,value,actual.get(key))
 sku=o.contract.verify_create_skus(prep['expected_schema']['sku'],actual['sku']);checks['schema_sku_binding']=sku['status']=='verified'
 attrs=defaultdict(set)
 for a in p['attributes']:attrs[a['attribute_name']].add(a['value_name'])
 plan=o.PLANS[family]
 expected={'Place of Origin':{'CN'},'Midsole Material':set(o.attribute_values(plan.get('midsole','Other'))),'Outsole Material':set(o.attribute_values(plan.get('outsole','Rubber'))),'Lining Material':set(o.attribute_values(plan['lining'])),'Upper Material':set(o.attribute_values(plan['upper'])),'Closure Type':{plan['closure']},'Style':set(plan['style']),'Toe Style':{plan.get('toe_style','Round Toe')},'Model Number':{o.model_number(family,variant)},plan['custom'][0]:{plan['custom'][1]},'Season':set(plan['seasons']),'Feature':{plan.get('feature','Fashion Trend')}}
 checks['category_exact']=int(p['category_id'])==int(plan.get('category_id',o.b.load(f/'before_get.json')['product']['category_id']))
 expected.update({name:set(values)for name,values in plan.get('extra_category_attributes',{}).items()})
 for name in plan.get('category_attribute_omissions',[]):expected.pop(name,None)
 if(f/'public_style_prepared.json').exists():expected['Style']={'Platform Sneakers','Lace-up'}
 checks['formal_attributes_exact']=dict(attrs)==expected
 axes={str(a['attribute_id']):a['values']for a in p['product_sku']['sku_attributes']}
 color_axis=prep.get('color_axis_id','191288010')
 checks['formal_color_names']=set(v['system_value_name']for v in axes[color_axis])==set(prep['colors'])
 checks['formal_eu_names']=set(v['system_value_name']for v in axes['222038415'])==set(prep['sizes'])
 col={str(v['value_id']):v['system_value_name']for v in axes[color_axis]};sz={str(v['value_id']):v['system_value_name']for v in axes['222038415']}
 pairset=Counter();pricepass=True;bindings={}
 tiers=[(int(q),float(pr))for q,pr in prep['tiers']]
 inventory_observed=[]
 for row in p['product_sku']['skus']:
  prop=json.loads(row['attr2_value']);pairset[(col[str(prop[color_axis])],sz[str(prop['222038415'])])]+=1
  bindings[row['sku_code']]=row['sku_id'];prices=[(int(v['start_quantity']),float(v['price']))for v in row['bulk_discount_prices']];pricepass&=sorted(prices)==sorted(tiers)
  inventory_observed.extend(row.get('inventory_dto_list',[]))
 if(f/'attribute_repair_before_get.json').exists():
  prior=o.b.load(f/'attribute_repair_before_get.json')['product']['product_sku']['skus'];checks['attribute_only_sku_ids_preserved']=bindings=={r['sku_code']:r['sku_id']for r in prior}
 checks['formal_sku_cartesian_complete']=pairset==Counter((c,s)for c in prep['colors']for s in prep.get('sizes_by_color',{}).get(c,prep['sizes']))
 checks['formal_sku_tiers']=pricepass
 old=o.b.load(f/'before_get.json')['product'];oldpres=o.preserve(old,prep['fields']);newpres=o.preserve(p,prep['fields'])
 checks['non_target_get_fields_preserved']=oldpres==newpres
 tradeold=copy.deepcopy(old['sourcing_trade']);tradenew=copy.deepcopy(p['sourcing_trade'])
 for tr in [tradeold,tradenew]:
  for key in ['fob_min_price','fob_max_price']:tr.pop(key,None)
 checks['trade_unit_moq_currency_leadtime_preserved']=tradeold==tradenew
 checks['formal_price_range']=float(p['sourcing_trade']['fob_min_price'])==min(pr for _,pr in tiers)and float(p['sourcing_trade']['fob_max_price'])==max(pr for _,pr in tiers)
 if 'platform_group_id'in plan:checks['store_group_exact']=str(p.get('group_id'))==str(plan['platform_group_id'])
 checks['summary_exact']=p['struct_detail']['product_summary']==plan['highlights']
 checks['main_count_six']=len(p['main_image']['images'])==6
 checks['detail_count_four']=len(p['struct_detail']['detail_image']['images'])==4
 common=o.b.load(o.ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/通用FAQ与公司简介.json')
 bank=o.b.load(o.ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/bank.json')['items']
 roles=[('C1','400'),('C2','550'),('C3','600'),('C4','450'),('C5','700'),('C6','700')]
 checks['approved_company_six_exact']=Counter((str(x['image_set']['id']),o.contract._created_image_identity(x['image_url']))for x in p['struct_detail']['company_image']['images'])==Counter((role,o.contract._created_image_identity(bank[key]['url']))for key,role in roles)
 checks['approved_general_faq_exact']=p['struct_detail']['product_faq']==[{'question':x['question'],'answer':x['answers']}for x in common['companyFaqDesc']]
 checks['approved_company_intro_exact']=p['struct_detail']['company_summary']==common['companyDesc']
 if(f/'company_quality_before_get.json').exists():
  prior=o.b.load(f/'company_quality_before_get.json')['product']
  checks['company_only_other_fields_preserved']=o.preserve(prior,prep['fields'])==o.preserve(p,prep['fields']) and prior['subject']==p['subject'] and prior['product_sku']==p['product_sku'] and prior['main_image']==p['main_image'] and prior['attributes']==p['attributes'] and prior['sourcing_trade']==p['sourcing_trade']
 scores=o.b.load(f/'score.json');result=scores.get('result',{});score=float(result['final_score'])if result.get('final_score')is not None else None;problem=json.loads(result['problem_map'])if isinstance(result.get('problem_map'),str)else result.get('problem_map',{})
 checks['actual_score_at_least_5']=score is not None and score>=5
 checks['score_diagnostics_clear']=not any(problem.get('extendProblemMap',{}).values())and not problem.get('errorReasonList')
 checks['display_y']=p['display']=='Y'
 keywords=[v for v in p.get('keywords',[])if v]
 wanted_keywords=prep.get('keyword_submission_selection',[plan['keywords']]if isinstance(plan['keywords'],str)else plan['keywords'])
 keyword_state='PERSISTED'if keywords==wanted_keywords else'LEGACY_FIELD_EMPTY_API_HIGHLIGHTS_MATCH_UI_PER_ID_PENDING'if not keywords and checks['summary_exact']else'MISMATCH'
 checks['keyword_observation_recorded']=keyword_state!='MISMATCH'
 report.update(state='FORMAL_FIELDS_SCORE_PASS'if all(checks.values())else'FORMAL_MISMATCH',checks=checks,failed=[k for k,v in checks.items()if not v],actual_score=score,target_score=5.0,score_source={'method':'alibaba.icbu.product.score.get','request_id':scores.get('request_id')},get_observed_at=datetime.fromtimestamp((f/'after_get.json').stat().st_mtime,timezone.utc).isoformat(),score_observed_at=datetime.fromtimestamp((f/'score.json').stat().st_mtime,timezone.utc).isoformat(),diagnostics=problem,keyword_state=keyword_state,keyword_write_verified=keyword_state=='PERSISTED',public_qa='PENDING',sku_bindings=bindings,inventory={'write':'OMITTED','formal_rows':inventory_observed,'physical_stock':'NOT_CONFIRMED'},scope='Formal get/render and actual score only. Empty legacy keywords are not claimed written; per-ID UI/public migration not yet tested. Normalization is limited to known image URLs, schema ordering/custom IDs and numeric price formatting.')
 o.b.save(f/'verification.json',report);print(pid,report['state'],report.get('failed',[]));return report
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf8')
 for family,ts in o.TARGETS.items():
  for variant,pid in ts.items():check(pid,family,variant)
