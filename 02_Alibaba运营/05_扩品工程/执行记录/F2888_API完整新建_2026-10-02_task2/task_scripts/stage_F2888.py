from pathlib import Path
import json,hashlib,shutil,datetime
W=Path(__file__).resolve().parent;O=W/'F2888_execution';P=Path.home()/'Desktop'/'贝强';H=W/'H219_execution';S=W/'shangchao_2357652';e=O/'evidence';e.mkdir(exist_ok=True)
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ev=[]
for p in (H/'evidence').glob('live_catalog_*.flat.json'):
 shutil.copyfile(p,e/p.name);ev.append({'path':'evidence/'+p.name,'sha256':sha(e/p.name),'kind':'catalog_snapshot'})
for name in ['candidate.json','public_index.json','page_text.txt','source.html','attributes_text.txt','public_Stock.json']:
 shutil.copyfile(S/name,e/name);ev.append({'path':'evidence/'+name,'sha256':sha(e/name),'kind':'source_register'})
m=next((P/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21').glob('*一对一*.json'));raw=m.read_bytes();row=next(x for x in json.loads(raw)['rows'] if x.get('candidate')=='F2888');assert row['old_product_id']=='1601943775160' and row['new_product_id'] is None and row['protected'] is False and row['growth_tier']=='普通品'
(e/'owner_mapping_original.json').write_bytes(raw)
normalized=dict(row,match_type='STRATEGIC_RETIRE_AND_REAL_SOURCE_REPLACEMENT_NOT_IDENTICAL_SHOE')
save('replacement_mapping_projection.json',{'rows':[normalized],'original_path':str(m),'original_sha256':sha(m),'normalization':'Enum spelling only; strategic different-shoe semantics unchanged. Original preserved, shared owner table not modified. No old-off authorization.'})
shutil.copyfile(H/'company_v3_manifest.json',O/'company_v3_manifest.json')
f=json.loads((H/'facts_and_copy.json').read_text(encoding='utf-8'));f.update(source_model='F2888',supplier_name='尚潮鞋业',source_url='https://shangchao.sooxie.com/detail/2357652',public_model='BQ-WBF2888',category=201339011,source_cost_CNY=53,colors=['Khaki','Black','Cream'],sizes=list(range(35,43)),SKU_count=24,version='Winter version; size34 held because page/photo labels conflict',materials={'upper':'Not specified; original term 太空革, exact polymer unknown','shaft_upper':'Mixed materials','shaft_lining':'Artificial long plush','upper_lining':'Cotton (source field; no percentage specified)','insole':'Artificial short plush','outsole':'Not specified','midsole':'Not specified'},construction='Cemented',closure='Side zipper',title="Women's Quilted Winter Boots with Plush Lining and Side Zipper",keywords=['women quilted winter boots'],product_summary="Women's quilted winter boots with a round toe and side zipper. Artificial long-plush shaft lining and an artificial short-plush insole are specified. Khaki, Black and Cream are offered with size labels 35-42. Exact upper composition, outsole and midsole materials are not specified. Send quantities by color and size, destination and packing requirements for a quotation. Measurements, international size conversion, availability and requested dispatch dates are confirmed for your order.",ordinary_HR_target={'old_listing':'HR056-A','old_product_id':row['old_product_id'],'old_action':'NOT_SENT','retained_siblings':row['retained_siblings']},publication_status='NOT_SUBMITTED',resume_authorization= json.loads((O/'resume_authorization.json').read_text(encoding='utf-8')))
f.pop('hard_stop_UTC',None);f.pop('no_auto_resume',None);f['price_policy'].pop('tiers',None)
f['FAQ']=[{'question':'Which materials are specified?','answer':'The shaft lining is artificial long plush and the insole is artificial short plush. Exact upper composition, outsole and midsole materials are not specified. Include your material requirements when requesting a quotation.'},{'question':'Which colors and sizes are offered?','answer':'Khaki, Black and Cream with size labels 35-42. Send quantities for each color and size. Foot measurements and international size conversions are confirmed for the order.'},{'question':'How do the boots close?','answer':'These boots have a side zipper and quilted upper panels, as shown in the actual product photos.'},{'question':'Can I request samples or customization?','answer':'Send your sample quantity or customization requirements with your color-size mix. Feasibility, charges, packing or logo options and any applicable minimums are confirmed before quotation.'},{'question':'How is availability and dispatch confirmed?','answer':'Provide quantities by color and size, destination and requested dispatch date. Per-size availability, packing, payment and dispatch terms are assessed for your order before quotation.'}]
save('facts_and_copy.json',f)
trace={'supplier_name':'尚潮鞋业','supplier_original_model':'F2888','supplier_original_direct_url':f['source_url'],'our_model':'BQ-WBF2888','international_product_id':None,'original_model_evidence':'evidence/page_text.txt: 货号：F2888; supplier 尚潮鞋业','old_listing':'HR056-A','old_product_id':'1601943775160','old_action':'NOT_SENT','knowledge_master_write':'PARENT_KNOWLEDGE_OWNER_ONLY'};save('source_traceability.json',trace)
old=json.loads((O/'old_formal_get.flat.json').read_text(encoding='utf-8'));old['product']['id']='1601943775160';old['product']['red_model']='HR056-A';old['identity_provenance']={'binding':'Official encrypt maps exact public id to secret_id returned in formal get; exact Model Number HR056-A','files':{n:sha(O/n) for n in ['old_encrypt.params.json','old_encrypt.flat.json','old_formal_get.flat.json']}};save('old_catalog_projection.json',old)
assets=json.loads((O/'asset_manifest.json').read_text(encoding='utf-8'));save('visual_gate.json',{'verdict':'PASS','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'review':'All 13 individual output images viewed at actual dimensions; source crops checked; complete whole shoes for hero/colors, intentional cropped closeups; no Chinese/prices/background magazine text; no shoe repaint or generated facts. Native source resolution limits recorded.','image_hashes':{Path(x['path']).name:x['sha256'] for x in assets['assets']}})
candidate={'source':{'reference':f['source_url'],'style':'F2888 winter boot Khaki/Black/Cream size35-42','evidence':'evidence/page_text.txt + public_index.json + source originals04/07/08/15/17','critical_facts':{'profile':'women quilted winter boot','upper_structure':'quilted upper, exact chemical material not specified','outsole_structure':'visible sole profile; chemical composition not specified','closure':'side zipper','lining':'artificial long-plush shaft lining, artificial short-plush insole','functional_use':'casual winter footwear'}},'search_intent':{'key':'women quilted winter boots plush lining side zipper','evidence':'Walmart women snow boots bestseller category read2026-10-02: winter boot + plush lining + side zipper alternatives; quilted modifier comes from actual product photos. Proxy only; search/sales volumes unknown.'},'hero_review':{'content_key':'F2888-khaki-whole-real-boot-detail04','label_status':'not_present','evidence':'Original detail04 isolated actual complete Khaki boot; individually viewed M1 no footwear brand/Chinese/prices; actual native322x220 recorded, no detail generated.'}}
save('differentiation_review.json',{'candidate':candidate,'source_records':{},'evidence_files':ev,'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'coverage_limit':'Existing three catalog pages plus fresh first page and exact old HR056-A formal get only; unknown source associations do not prove full-store identity clearance.'})
doc='''# F2888 单款经营任务包

## A. 身份、来源与商业字段
任务task2，REPLACE，型号BQ-WBF2888，类目Snow Boots/201339011。供应商尚潮鞋业，原货号F2888，[原始商品直达](https://shangchao.sooxie.com/detail/2357652)，原货号证据page_text.txt。国际站ID待实际回执；source_traceability.json持续绑定。拿货价53元只有一个展示价，供应商MOQ/阶梯/实际库存未知；店铺MOQ2和2/50/100双的50%/40%/30%加价独立采用用户经营授权，固定报价汇率6.6987非实时市价，向上到美分。卡其/黑/米对应Khaki/Black/Cream，35–42交集24SKU，34暂不发。靴筒人造长毛绒、鞋垫人造短毛绒、鞋面内里棉无百分比、太空革不外推PU；外底/中底未知。当前Schema必填未知用合法自定义Not specified；可选筒高/性能/库存省略。胶粘、侧拉链、圆头由来源证明。授权包裹基线34×23×13cm/0.5kg/1pair非实测。

## B. 类目方向与对标
[Walmart女性冬靴畅销类目](https://www.walmart.com/c/best-sellers/women-s-snow-boots)本轮公开读取展示Ecetana侧拉链内衬冬靴和plush-lined冬靴、Hobibear冬靴。用于冬靴/内衬/开口选型和信息顺序，销量/性能不迁移；quilted来自本款实拍。review计数只属类目代理，不证明本款销量。

## C. 搜索及文案
Women's Quilted Winter Boots with Plush Lining and Side Zipper。关键词women quilted winter boots；购买问题围绕三色、色码组合、开口、绒衬、报价输入。无防水/防滑/低温/羊毛/宽楦承诺；来源和HR属于内部溯源，不写买家页面。

## D. 六主图、四详情、公司图与SKU
M1完整卡其真鞋白底，M2三色，M3开口绒衬，M4绗缝，M5上脚，M6黑色；D1色码，D2已知内衬部位，D3侧拉链结构，D4询价所需配比/目的地/包装/发运要求。3色SKU绑定实拍无字图。asset_manifest.json记录每一裁切有效像素、源SHA和目标SHA。原生SVG排版不生成鞋体；不以小图放大当测量证明。五公司图沿用已审核v3官方银行。

## E. 发布验收及边界
既有成熟API和当前Schema一次创建，正式get/render校验型号、24SKU、图片6/4/5、FAQ6、MOQ、真实阶梯；实际score至少5，公开页面交浏览器负责人QA。库存可选省略不承诺现货。停止18UTC历史断点已由22:13用户“可以恢复了，请继续进行任务”明确恢复，仅本款脚本读取恢复授权，不复跑H219。

## F. 旧新映射与保护
HR056-A/1601943775160今日普通且protected=false，正式Model Number回读吻合。真实冬靴是战略不同鞋替换，非同鞋重复豁免。保留HR056-B普通和HR056-C潜力以及PROTECT_SOURCE。原始映射复制存证，本地只规范枚举拼写，父知识线程维护共享总表。本任务不下架旧链接；新ID绑定由回执交父线程。

## G. 观察与下一步
冬季方向小批试验；当前无转化销量。实拍审核→官方银行上传→当前Schema验证→一次创建→正式5分回读→浏览器公开QA。供应商数量、MOQ阶梯、测量尺码/包装、图片商用授权待采购确认，不猜。
'''
(O/'经营任务包.md').write_text(doc,encoding='utf-8');template=P/'02_Alibaba运营/05_扩品工程/工厂店外新款数据采集模板.md'
def evidence(p,k):return {'path':str(p),'sha256':sha(p if p.is_absolute() else O/p),'kind':k}
pack={'task_id':'F2888_2026-10-02_task2','role':'REPLACE','phase':'PREPARING_CURRENT_SCHEMA_CREATE','writer':'task2','next_action':'One current-schema create then formal score and parent public QA; no old-off','public_model':'BQ-WBF2888','category_id':201339011,'product_id':None,'source_identity':candidate['source'],'search_intent':candidate['search_intent'],'hero_review':candidate['hero_review'],'replacement_plan':{'candidate':'F2888','old_product_ids':['1601943775160']},'source_traceability':trace,'evidence_files':[evidence(template,'task_pack_template'),evidence(Path('经营任务包.md'),'task_pack_document'),evidence(Path('replacement_mapping_projection.json'),'replacement_mapping'),evidence(Path('evidence/owner_mapping_original.json'),'source_register')]};save('task_pack.json',pack)
# Reuse mature 9968/H219 payload builder; substitute only this shoe's facts.
s=(W/'prepare_H219.py').read_text(encoding='utf-8')
for a,b in [('H219','F2888'),('BQ-ABF2888','BQ-WBF2888'),('HR048-B','HR056-A'),('201768405','201339011'),('Decimal(60)','Decimal(53)'),('len(bank)==12','len(bank)==13'),('range(35,41)','range(35,43)'),("['sku_count']==12","['sku_count']==24"),('12 SKU','24 SKU'),('USD 13.44','USD 11.87'),('USD 12.54','USD 11.08'),('USD 11.65','USD 10.29')]:s=s.replace(a,b)
s=s.replace("prop('p-1','China',100000458);prop('p-210194982','PU',3323086);prop('p-191290426','Rubber',3338114);prop('p-191290430','Not specified',-2);prop('p-20700','Not specified',-2)","prop('p-1','China',100000458);prop('p-191284187','Women',3374293);prop('p-191288212','Winter',3254739);prop('p-191290428','Not specified',-2);prop('p-191290426','Not specified',-2);prop('p-191290430','Plush',4141322);prop('p-20700','Not specified',-2)")
s=s.replace("prop('p-200000388','Lace-up and side zipper',-2);prop('p-200000486','Round toe',-2)","prop('p-200000486','Round Toe',556500746)")
s=s.replace("colors=[('Brown','3399503'),('Black','3327837')]","colors=[('Khaki','-2'),('Black','3327837'),('Cream','-3')]")
s=s.replace("assert vid in [x.get('value') for x in d.findall('./options/option')]","assert (int(vid)<-1 and any(x.get('value')=='inputValue' for x in d.findall('./rules/rule'))) or vid in [x.get('value') for x in d.findall('./options/option')]")
(W/'prepare_F2888.py').write_text(s,encoding='utf-8');print('Staged facts, source traceability, reviewed assets and scoped original HR056-A evidence; shared tables untouched.')
