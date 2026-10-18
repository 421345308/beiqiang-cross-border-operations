"""Read-only exact-ID performance triage; different periods/channels stay separate."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter,defaultdict
from decimal import Decimal
import json,re,sys
ROOT=Path(__file__).resolve().parents[3]
AREA=ROOT/'02_Alibaba运营/01_店铺与全店诊断'
BASE=AREA/'经营诊断证据/商品表现处置'
ADS=AREA/'经营诊断证据/推广计划_20260914123458/20261015'
REG=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
PROTECTED={'1601825074604'}
def load(p):return json.loads(p.read_text(encoding='utf8'))
def rel(p):return p.relative_to(ROOT).as_posix()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def image_key(url):return re.search(r'/kf/([^/]+)',url).group(1).split('?')[0]if '/kf/'in url else url
def sku_matrix(p):
 axes={str(a['attribute_id']):{str(v['value_id']):str(v.get('custom_value_name')or v.get('system_value_name')or'').strip().casefold()for v in a['values']}for a in p.get('product_sku',{}).get('sku_attributes',[])}
 result={}
 for row in p.get('product_sku',{}).get('skus',[]):
  binding=json.loads(row['attr2_value']);key=tuple(sorted((a,axes.get(a,{}).get(str(v),'UNRESOLVED:'+str(v)))for a,v in binding.items()))
  if any(v.startswith('UNRESOLVED:')for a,v in key):return {}
  result[key]=sorted((int(x['start_quantity']),str(Decimal(x['price'])))for x in row.get('bulk_discount_prices',[]))
 return result
def source_change(l):
 v=l.get('optimization',{}).get('source_replacement',{})
 return v.get('at','')[:10]or None
def compatible(l,window_start):
 # A change anywhere inside the reporting window mixes two physical shoes.
 # Require it strictly before the first day; a same-day change is ambiguous.
 return not source_change(l)or source_change(l)<window_start
def main():
 sys.stdout.reconfigure(encoding='utf8');r=load(REG);products={p['id']:p for p in r['products']};links={l['id']:l for l in r['listings']};current=BASE/'处置后目录/catalog.json';catalog=load(current if current.exists()else BASE/'当前目录/catalog.json');live={str(p['id']):p for p in catalog['products']}
 monthfile=ROOT/'99_临时区/HR实源替换/商品经营数据/month09_effective.json';rawmonth=load(monthfile);month={}
 for row in rawmonth['rows']:
  pid=re.search(r'_(\d+)\.html',row['links'][0]).group(1);v=row['values'];month[pid]=dict(zip(['search_impressions','search_clicks','ctr_display','visitors','inquiries','tm_buyers'],[int(v[0]),int(v[1]),v[2],int(v[3]),int(v[4]),int(v[5])]))
 week={str(x['id']):x for x in load(ADS/'product_analytics_week40_all.json')['rows']};day13={str(x['id']):x for x in load(ADS/'product_analytics_20261013_all.json')['rows']};rawday=load(BASE/'产品参谋_最新完整日.json');day={x[0]:dict(zip(['search_impressions','search_clicks','visitors','inquiries','tm_buyers','marketing_clicks'],x[1:]))for x in rawday['rows']};ads={str(x['id']):x for x in load(ADS/'products_30d.json')['rows']};ad7={str(x['id']):x for x in load(ADS/'current_products_7d.json')['rows']}
 assert len(month)==357 and sum(x['search_impressions']for x in month.values())==155218 and sum(x['inquiries']for x in month.values())==63
 assert len(week)==382 and sum(x['search_impressions']for x in week.values())==81960 and sum(x['search_clicks']for x in week.values())==1151
 assert len(day)==249 and sum(x['search_impressions']for x in day.values())==11316 and sum(x['search_clicks']for x in day.values())==134 and sum(x['inquiries']for x in day.values())==7
 rows=[];formals={};families=defaultdict(list)
 for pid,cat in live.items():
  l=links[pid];product=products[l['product_id']];m=month.get(pid);w=week.get(pid);d=day.get(pid);a=ads.get(pid);signals=[];cp=l.get('formal_fields',{}).get('file');formal=load(ROOT/cp).get('response',{}).get('product')if cp and(ROOT/cp).exists()else None
  if formal:formals[pid]=formal
  if cat['status']=='tbd':signals.append('AUDIT_REJECTED_VISIBILITY')
  elif cat['status']!='approved':signals.append('REVIEW_PENDING_NOT_REJECTED')
  elif cat['display']!='Y':signals.append('ALREADY_OFFLINE_KEEP_STATE')
  if product.get('publication_disposition',{}).get('state')=='PLATFORM_IP_REJECTED_NO_RESUBMIT':signals.append('PLATFORM_IP_REJECTION_OWNER_CONFIRMED_NO_RESUBMIT')
  if not compatible(l,'2026-10-04'):signals.append('RECENT_PHYSICAL_REPLACEMENT_OLD_METRICS_NOT_NEW_PRODUCT')
  if cat['gmt_create'][:10]>'2026-10-10':signals.append('NEW_LISTING_AFTER_LATEST_COMPLETE_WEEK')
  if m and compatible(l,'2026-09-01')and m['search_impressions']>=1000 and m['search_clicks']/m['search_impressions']<.008:signals.append('MONTH_HIGH_EXPOSURE_LOW_CTR')
  if w and compatible(l,'2026-10-04')and w['search_impressions']>=250 and w['search_clicks']/w['search_impressions']<.008:signals.append('WEEK_LOW_CTR')
  if w and compatible(l,'2026-10-04')and w['visitors']>=25 and w['inquiries']==w['tm_buyers']==0:signals.append('WEEK_VISITS_WITHOUT_INQUIRY_OR_TM_CHECK_TRAFFIC_AND_OFFER')
  if a and compatible(l,'2026-09-15')and a['clicks']>=50 and a['l1_opportunities']==0 and a['opportunities']<=2:signals.append('AD_CLICKS_WEAK_QUALIFIED_OPPORTUNITY')
  if m is None:signals.append('MONTH_ROW_MISSING_NOT_ZERO')
  if w is None:signals.append('WEEK_ROW_MISSING_NOT_ZERO')
  row={'id':pid,'model':cat['red_model'],'family':l['product_id'],'source_state':product['source_state'],'source_id':l.get('bound_source_id'),'status':cat['status'],'display':cat['display'],'title':cat['subject'],'created_on':cat['gmt_create'][:10],'physical_source_changed_on':source_change(l),'periods':{'september':m,'week40':w,'oct13':day13.get(pid),'oct14':d,'ad_30d':a,'ad_7d_snapshot':ad7.get(pid)},'signals':signals,'protected':pid in PROTECTED,'primary_action':'SOURCE_AND_FIELD_REVIEW'if product['source_state']not in('ADOPTED','MAPPED','RAW_PACKAGE')else'CONTENT_OR_SIBLING_REVIEW'if any(x in signals for x in('MONTH_HIGH_EXPOSURE_LOW_CTR','WEEK_LOW_CTR','WEEK_VISITS_WITHOUT_INQUIRY_OR_TM_CHECK_TRAFFIC_AND_OFFER','AD_CLICKS_WEAK_QUALIFIED_OPPORTUNITY'))else'OBSERVE_CURRENT_STYLE'if any(x.startswith(('RECENT_PHYSICAL','NEW_LISTING'))for x in signals)else'KEEP_OR_LOW_SAMPLE','current_formal_reference':cp};rows.append(row);families[l['product_id']].append(row)
 duplicate_pairs=[]
 for family,group in families.items():
  for weak in group:
   pid=weak['id'];l=links[pid];m=weak['periods']['september'];w=weak['periods']['week40'];p=formals.get(pid)
   if weak['protected']or weak['display']!='Y'or weak['status']!='approved'or not p or not m or not w or not compatible(l,'2026-09-01')or any(m[k]or w[k]for k in ('inquiries','tm_buyers')):continue
   if m['search_impressions']<200:continue
   for strong in group:
    sid=strong['id'];s=formals.get(sid);sm=strong['periods']['september'];sw=strong['periods']['week40']
    if sid==pid or not s or strong['display']!='Y'or strong['status']!='approved'or not sm or not sw or not compatible(links[sid],'2026-09-01')or not any(sm[k]or sw[k]for k in('inquiries','tm_buyers')):continue
    main={image_key(u)for u in p['main_image']['images']};main2={image_key(u)for u in s['main_image']['images']};detail={image_key(x['image_url'])for x in p.get('struct_detail',{}).get('detail_image',{}).get('images',[])};detail2={image_key(x['image_url'])for x in s.get('struct_detail',{}).get('detail_image',{}).get('images',[])};wm=sku_matrix(p);ss=sku_matrix(s)
    duplicate_pairs.append({'family':family,'weak_id':pid,'strong_id':sid,'weak_model':weak['model'],'strong_model':strong['model'],'shared_main_images':len(main&main2),'same_detail_images':bool(detail)and detail==detail2,'weak_SKU_combos':len(wm),'strong_SKU_combos':len(ss),'all_weak_combos_retained_in_strong':bool(wm)and wm.keys()<=ss.keys(),'same_prices_on_weak_combos':bool(wm)and all(k in ss and wm[k]==ss[k]for k in wm),'same_category':p['category_id']==s['category_id'],'same_physical_family':True,'weak_month':m,'weak_week':w,'strong_month':sm,'strong_week':sw,'disposition':'REVIEW_EXACT_PRODUCT_DIFFERENCES_AND_RECENT_SIGNAL_BEFORE_PAUSE'})
 for x in rows:
  if 'PLATFORM_IP_REJECTION_OWNER_CONFIRMED_NO_RESUBMIT'in x['signals']:x['primary_action']='HOLD_ORIGINAL_SHOE_AND_IMAGES_NO_RESUBMIT_REVIEW_IP_NOTICE'
 summary={'catalog_ids':len(live),'catalog_states':dict(Counter(p['status']+'/'+p['display']for p in live.values())),'signal_counts':dict(Counter(s for x in rows for s in x['signals'])),'month':{'rows':len(month),'search_impressions':155218,'search_clicks':1986,'inquiries':63},'week40':{'rows':len(week),'search_impressions':81960,'search_clicks':1151,'inquiries':31},'oct14':{'rows':249,'search_impressions':11316,'search_clicks':134,'visitors':225,'inquiries':7,'tm_product_rows':8,'marketing_clicks':244},'duplicate_review_pairs':len(duplicate_pairs)}
 result={'schema_version':2,'observed_at':datetime.now(timezone.utc).isoformat(),'scope_notes':['完整488条当前目录；缺报表行保持null，不填零。','9月、10月4–10日、10月13/14日与推广9月15–10月14日分别解释，不叠加。','搜索指标不是已剔除广告的纯自然流，营销点击不与搜索点击相减。','访客、询盘和TM跨商品未去重，指标不能视为真实采购机会或成交。','来源整鞋替换日期与款式身份独立于货号/通用工厂图修改日期。','信号只触发复核，不自动证明原因、生成图合格或授权外操作已完成。'],'periods':{'september':rel(monthfile),'week40':rel(ADS/'product_analytics_week40_all.json'),'oct13':rel(ADS/'product_analytics_20261013_all.json'),'oct14':rel(BASE/'产品参谋_最新完整日.json'),'ad30':rel(ADS/'products_30d.json')},'summary':summary,'products':rows,'duplicate_pairs':duplicate_pairs};save(AREA/'商品诊断数据.json',result)
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
