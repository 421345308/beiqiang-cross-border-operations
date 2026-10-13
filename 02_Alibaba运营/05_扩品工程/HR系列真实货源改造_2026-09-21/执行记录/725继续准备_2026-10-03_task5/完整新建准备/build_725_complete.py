"""725 complete local plan and canonical create manifest; never calls an API."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys,csv,copy,xml.etree.ElementTree as E
from PIL import Image
W=Path(__file__).parent; O=W/'725_next_preparation_20261003'; S=Path(r'C:\Users\spq\Documents\Codex\2026-10-02\task-4\hr_control\basketball_casual_candidate_2026-10-02'); R=Path(r'C:\Users\spq\Desktop\贝强')
sys.path.insert(0,str(R/'08_工具链/01_业务脚本/国际站扩品'))
import publish_hot_rank_hr_a_batch as pub
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
model='BQ-CS063C'; category=201334413
buyer=json.loads((S/'725_buyer_copy_CURRENT_NOT_SENT.json').read_text(encoding='utf-8'));buyer['public_model']=model
buyer['title']='Basketball-Inspired Mesh Lace-Up Casual Sneakers with Rear Pull Tab Model '+model
buyer['faqs'][0]['answers']='The upper is mesh textile and the outsole is rubber. The source specifies a rubber + MD sole assembly; separate midsole and lining compositions are not specified.'
buyer['faqs'][2]['answers']='Listed size labels are 36–45. The sizing system is not specified; please confirm measurements and your quantities by size before ordering.'
buyer['faqs'][4]['answers']='2–49 pairs: USD 13.43/pair; 50–99 pairs: USD 12.54/pair; 100+ pairs: USD 11.65/pair. Freight, packing and dispatch timing are confirmed for your order.'
save('buyer_copy_complete_NOT_SENT.json',buyer)
colors=[('晴空','White / Lime',O/'source_extra/source_48.jpg'),('活字印刷术','White / Red',O/'COLOR_White_Red.png'),('冰刀','White / Blue / Purple',O/'source_extra/source_58.jpg'),('巾帼','Pink / Blue',O/'source_extra/source_55.jpg'),('绵绵冰','Blue / Purple',O/'source_extra/source_52.jpg'),('三潭印月','White / Green',S/'725_detail_60.jpg')]
selected=[('M1',S/'725_M1.jpg','Search hero: actual white/lime shoe'),('M2',S/'725_M2.png','Actual side-panel construction'),('M3',S/'725_M3.png','Mesh tongue and lace detail'),('M4',S/'725_M4.png','Rear pull tab construction'),('M5',O/'M5_color_card.png','Six actual color selections; replaces rejected sole redraw'),('M6',S/'725_M6_company_v3.jpg','Company order planning; no claim that this model is made here'),('D1',O/'source_extra/source_49.jpg','Pair and collar view in white/lime'),('D2',O/'source_extra/source_35.jpg','Actual outsole pattern in pink/blue; no grip claim'),('D3',O/'source_extra/source_21.jpg','Actual on-foot blue/purple profile; no fit guarantee'),('D4',O/'source_extra/source_59.jpg','Rear/side pair in white/green')]
for i,(_,alias,p) in enumerate(colors):selected.append(('COLOR_'+str(i+1),p,alias))
assert all(p.exists() for _,p,_ in selected),'Finish generated asset review before build'
assets=[]
for role,p,meaning in selected:
 with Image.open(p) as im: size=list(im.size);im.verify()
 assert p.stat().st_size<4*1024*1024
 assets.append({'role':role,'path':str(p.resolve()),'sha256':h(p),'dimensions':size,'meaning':meaning,'review':'PASS_ACTUAL_STRUCTURE_AND_MARKS_VISUALLY_REVIEWED','provenance':'AI-assisted surrounding layout or crop' if role in ['M2','M3','M4','M5','COLOR_2'] else 'Original source bytes / original company-v3 bytes'})
save('selected_assets_complete.json',assets)
bindings=[{'source_label':label,'buyer_color':alias,'source_chart':'source_extra/source_05.jpg','image_role':'COLOR_'+str(i+1),'image_path':str(p),'image_sha256':h(p),'stock':'NOT_ASSERTED','size_labels':[str(n) for n in range(36,46)]} for i,(label,alias,p) in enumerate(colors)]
save('color_binding_complete.json',bindings)
company=json.loads((S/'725_company_v3_exact_reuse_manifest.json').read_text(encoding='utf-8'))['rows']
assert all(h(S/c['local'])==c['sha256'] for c in company)
schema=E.parse(S/'current_schema.xml').getroot();meta=json.loads((S/'current_schema.meta.json').read_text())
save('materials_complete.json',{'upper':'Mesh','outsole':'Rubber','outsole_evidence':{'file':str(S/'725_detail_11.jpg'),'sha256':h(S/'725_detail_11.jpg'),'observed_text':'橡胶大底'},'whole_sole':'Rubber + MD','whole_sole_evidence':{'file':str(S/'725_detail_04.jpg'),'sha256':h(S/'725_detail_04.jpg')},'midsole':'Not specified','lining':'Not specified','no_inference':['MD is not mapped to EVA','TPU reinforcement is not an entire sole material'],'brand':'Actual SPORT marking retained; no unbranded claim'})
root=E.Element('itemSchema')
def fld(p,fid,typ):return E.SubElement(p,'field',id=fid,type=typ)
def val(p,fid,typ,text,attrs=None):f=fld(p,fid,typ);E.SubElement(f,'value',attrs or {}).text=str(text);return f
val(root,'catId','input',category);val(root,'productTitle','input',buyer['title'])
attrcv=E.SubElement(fld(root,'icbuCatProp','complex'),'complex-value');attrcv.append(pub.serialize_product_model(schema,model))
def attr(fid,label):
 d=schema.find("./field[@id='icbuCatProp']/fields/field[@id='"+fid+"']");assert d is not None
 opts=d.findall('./options/option');opt=next((a for a in opts if a.get('displayName','').casefold()==label.casefold()),None)
 node=fld(attrcv,fid,d.get('type'));container=E.SubElement(node,'values') if d.get('type')=='multiCheck' else node
 if opt is not None:E.SubElement(container,'value',{'displayName':opt.get('displayName')}).text=opt.get('value')
 else:
  assert any(a.get('value')=='-1' for a in opts) and any(a.get('value')=='inputValue' for a in d.findall('./rules/rule'))
  E.SubElement(container,'value',inputValue=label).text='-1'
attr('p-1','China');attr('p-20700','Not specified');attr('p-191290426','Rubber');attr('p-191290430','Not specified');attr('p-210194982','Mesh');attr('p-191288243','Lace-up')
ledger=O/'upload_once_ledger.json';uploaded=json.loads(ledger.read_text())['uploads'] if ledger.exists() else []
actual={a['role']:a for a in uploaded if a['status']=='UPLOADED_BUSINESS_VERIFIED'}
ready=all(a['role'] in actual for a in assets)
bank={a['role']:{'url':actual[a['role']]['official_url'],'file_id':actual[a['role']]['file_id']} if a['role'] in actual else {'url':'https://sc04.alicdn.com/kf/LOCAL_NOT_UPLOADED_'+a['role']+'.jpg','file_id':'LOCAL_NOT_UPLOADED'} for a in assets}
fld(root,'scImages','complex');pub.set_main_images(root,[bank['M'+str(i)] for i in range(1,7)])
fld(root,'productKeywords','complex');pub.set_keywords(root,'mesh lace up casual sneakers')
sale=E.SubElement(fld(root,'saleProp','complex'),'complex-value')
colorid='p-191288010';sizeid='p-222038415'
for fid in [colorid,sizeid]:
 d=schema.find("./field[@id='saleProp']/fields/field[@id='"+fid+"']");assert d is not None and any(x.get('value')=='inputValue' for x in d.findall('./rules/rule'))
cv=E.SubElement(fld(sale,colorid,'multiCheck'),'values');sv=E.SubElement(fld(sale,sizeid,'multiCheck'),'values')
for i,(_,alias,_) in enumerate(colors):E.SubElement(cv,'value',inputValue=alias,img=bank['COLOR_'+str(i+1)]['url'],remark=alias).text=str(-201-i)
for i,n in enumerate(range(36,46)):E.SubElement(sv,'value',inputValue='Label '+str(n)+' (system unspecified)').text=str(-101-i)
sku=fld(root,'sku','multiComplex')
for i,(_,alias,_) in enumerate(colors):
 for j,n in enumerate(range(36,46)):
  row=E.SubElement(sku,'complex-values');val(row,'skuOuterId','input',model+'-C'+str(i+1)+'-'+str(n))
  props=E.SubElement(fld(row,'props','multiInput'),'values')
  for fid,vid,label in [(colorid,str(-201-i),alias),(sizeid,str(-101-j),'Label '+str(n)+' (system unspecified)')]:E.SubElement(props,'value',propId=fid.removeprefix('p-'),propName=fid,propValueId=vid,propValueName=label).text=fid.removeprefix('p-')+':'+vid
for fid,typ,v in [('priceUnit','singleCheck','5'),('saleType','singleCheck','normal'),('scPrice','singleCheck','1'),('minOrderQuantity','input','2'),('productDescType','singleCheck','4')]:val(root,fid,typ,v)
prices=E.SubElement(fld(root,'ladderPrice','complex'),'complex-value')
for i,t in enumerate(buyer['price_plan']['tiers']):
 row=E.SubElement(fld(prices,'ladderPrice_'+str(i),'complex'),'complex-value');val(row,'quantity','input',t['min_qty_pairs']);val(row,'price','input',format(t['usd_per_pair'],'.2f'))
fld(root,'detailImage','multiComplex');pub.set_gallery(root,'detailImage',[bank['D'+str(i)] for i in range(1,5)],[(350,'Other product images')]*4)
fld(root,'companyImage','multiComplex');pub.set_gallery(root,'companyImage',[{'url':c['url']} for c in company],[(int(c['gallery_id']),c['role']) for c in company])
val(root,'companyDesc','input','Quanzhou Beiqiang Footwear & Apparel Co., Ltd. is based in Quanzhou, Fujian, China. The company images introduce our general footwear development and order coordination capabilities. Model-specific samples, customization, packing and dispatch arrangements are reviewed against your requirements before quotation.')
val(root,'textDesc','input','Basketball-inspired casual sneaker styling with a mesh textile upper, lace-up closure, rear pull tab and rubber outsole. The source specifies a rubber + MD sole assembly; separate midsole and lining compositions are not specified. Choose six color combinations shown in the actual photos and listed size labels 36–45; confirm size measurements before ordering. Minimum order: 2 pairs. Send your quantities by color and size, destination and packing requirements for a quotation. Performance, availability and customization are confirmed for your selected order; no tested sporting or medical performance is claimed.')
root.append(E.parse(O/'faq_values_NOT_SENT.xml').getroot())
faq=root.find("./field[@id='companyFaqDesc']")
for row,item in zip(faq.findall('./complex-values'),buyer['faqs']):
 for k,v in item.items():row.find("./field[@id='"+k+"']/value").text=v
# Store commercial packaging baseline only; not a measured model package.
old=E.parse(W/'single_agent_resume_2310/929_publish/intended_payload.xml').getroot()
for fid in ['pkgMeasure','pkgWeight']:
 node=old.find("./field[@id='"+fid+"']")
 if node is not None:root.append(copy.deepcopy(node))
if root.find("./field[@id='pkgMeasure']") is None:
 package=E.SubElement(fld(root,'pkgMeasure','complex'),'complex-value')
 for fid,number in [('length',34),('width',23),('height',13)]:val(package,fid,'input',number)
if root.find("./field[@id='pkgWeight']") is None:val(root,'pkgWeight','input','0.5')
assert len(sku)==60 and not root.findall(".//field[@id='skuStock']")
payload=O/'intended_payload_complete.xml';payload.write_text(E.tostring(root,encoding='unicode'),encoding='utf-8')
mapping=R/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR普通品一对一待替换映射_2026-10-02.json'
m=json.loads(mapping.read_text(encoding='utf-8'));mr=next(x for x in m['rows'] if x['candidate']=='725');assert mr['new_product_id'] is None
approved=S/'PARENT_HANDOFF_CURRENT/725_HR063_C_APPROVED_SOURCE_MAPPING.json'
authorization=json.loads(approved.read_text(encoding='utf-8'))
assert str(authorization['ordinary_HR_product_id'])==str(mr['old_product_id']) and authorization['source_url']==mr['source_url'] and authorization.get('backend_authorization')
projected=dict(mr,match_type='STRATEGIC_RETIRE_AND_REAL_SOURCE_REPLACEMENT_NOT_IDENTICAL_SHOE',authorization_scope=authorization['backend_authorization'])
# Read-only projection of two existing originals: no business row changes and
# no same-shoe duplicate waiver. The strategic old-off remains separate.
save('replacement_mapping_contract_projection.json',{'rows':[projected],'limits':'Local schema-contract projection, not a live classification or business state update','originals':[{'path':str(mapping),'sha256':h(mapping)},{'path':str(approved),'sha256':h(approved)}]})
contract_mapping=O/'replacement_mapping_contract_projection.json'
catalog=W/'quality_audit_resume_20261002_2227/catalog.json'
allrows=json.loads(catalog.read_text(encoding='utf-8'))['products']+json.loads((O/'latest_page1.json').read_text())['response']['products']
assert not any(x.get('red_model')==model for x in allrows),'New model collision; retain records and select another legal model'
source={'reference':'https://tuyuan.sooxie.com/detail/2541696','style':'725','evidence':[str(O/'materials_complete.json'),str(O/'color_binding_complete.json')],'critical_facts':{'upper_structure':'mesh textile upper with angular side overlay','outsole_structure':'rubber outsole with patterned tread','closure':'lace-up','profile':'basketball-inspired casual sneaker'}}
intent={'key':'mesh lace up casual sneakers with angular side panels and color choices','evidence':[str(O/'buyer_copy_complete_NOT_SENT.json')],'limits':'Factual positioning, not proof of demand or traffic'}
hero={'url':bank['M1']['url'],'aliases':[bank['M1']['url'].replace('https:','')],'sha256':assets[0]['sha256'],'content_key':'725_actual_white_lime_angular_side_hero','label_status':'not_present','evidence':[assets[0]['path']],'limits':'SPORT marking retained; no model overlay; unknown catalog sources remain unknown'}
sources={str(x['new_product_id']):{'source':{'reference':x['source_url'],'style':x['candidate'],'evidence':str(mapping)}} for x in m['rows'] if x.get('new_product_id')}
latestfile=O/'latest_page1_catalog_projection.json';latestfile.write_text(json.dumps(json.loads((O/'latest_page1.json').read_text())['response'],ensure_ascii=False),encoding='utf-8')
context={'candidate':{'source':source,'search_intent':intent,'hero_review':hero},'source_records':sources,'evidence_files':[{'path':str(catalog),'sha256':h(catalog),'kind':'catalog_snapshot'},{'path':str(latestfile),'sha256':h(latestfile),'kind':'catalog_snapshot'},{'path':str(mapping),'sha256':h(mapping),'kind':'source_register'}],'coverage_limit':'Existing catalog snapshot and current first page; exact source/model/mapping checks, not a global same-shoe clearance'}
save('differentiation_review_complete.json',context)
doc=O/'A-G完整准备稿.md';doc.write_text('\n'.join(['# 725 A–G 完整准备稿','## A 角色与目标','REPLACE；单写入者task-5；旧HR063-C / 1601943764325不同鞋战略替换，不自动下架。新型号BQ-CS063C避免旧型号冲突。','## B 原始货源','途远鞋业，货号725，https://tuyuan.sooxie.com/detail/2541696；外采实鞋，不宣称本款自产。成本60 CNY观察2026-10-02 22:24 UTC。','## C 买家内容',json.dumps(buyer,ensure_ascii=False,indent=2),'## D SKU与报价','真实6色 × 源标签36–45共60；不猜EUR、不写库存；2/50/100三档13.43/12.54/11.65 USD；6.7为运营换算依据，成本加价不是净利润。平台包装为既有店铺商业基线，不是单款实测。','## E 资产',json.dumps(assets,ensure_ascii=False,indent=2),'六主、四详、五公司；失真旧M5及旧生成详情不用。新M5仅六色选择卡；实际颜色逐项按原图绑定。通用公司图不证明725自产。','## F 去重与提交','保留原HR及所有历史目录证据；新型号BQ-CS063C；直接复用canonical create/type4。缺图片银行回执时只可离线预演，禁止把占位URL提交。','## G 验收','单次正式新增、未知写入禁止重试；按新ID回读型号/60SKU/价格/材料/FAQ/六四五图片和5.0，再进行公开页验收。旧品只有新款完成且当前普通品及关联核对通过后按原授权处理。']),encoding='utf-8')
template=R/'02_Alibaba运营/05_扩品工程/工厂店外新款数据采集模板.md'
pack={'task_id':'725_resume_complete_20261003','role':'REPLACE','phase':'ASSET_REVIEW_COMPLETE_BANK_BINDING_PENDING' if not ready else 'REVIEWED_ONCE_CREATE','writer':'task-5','next_action':'Bind actual photobank receipts, canonical once-create, then exact new-ID readback','public_model':model,'category_id':category,'product_id':None,'source_identity':source,'search_intent':intent,'hero_review':hero,'replacement_plan':{'candidate':'725','old_product_ids':['1601943764325']},'source_traceability':{'supplier_name':'途远鞋业','supplier_original_model':'725','supplier_original_direct_url':source['reference'],'our_model':model,'international_product_id':None},'evidence_files':[{'path':str(template),'sha256':h(template),'kind':'task_pack_template'},{'path':str(doc),'sha256':h(doc),'kind':'task_pack_document'},{'path':str(contract_mapping),'sha256':h(contract_mapping),'kind':'replacement_mapping'},{'path':str(mapping),'sha256':h(mapping),'kind':'original_business_mapping'},{'path':str(approved),'sha256':h(approved),'kind':'original_authorization_evidence'}]}
save('task_pack_complete.json',pack)
manifest={'operation':'create','category_id':category,'facts_reviewed':True,'source_evidence':['materials_complete.json','color_binding_complete.json','buyer_copy_complete_NOT_SENT.json'],'current_schema':str(S/'current_schema.xml'),'current_schema_sha256':h(S/'current_schema.xml'),'schema_request_id':meta['schema_request_id'],'schema_acquired_at':meta['schema_acquired_at'],'payload_xml':payload.name,'field_ids':[f.get('id') for f in root],'dependency_ids':[],'expected_model':model,'differentiation_review':'differentiation_review_complete.json','differentiation_review_sha256':h(O/'differentiation_review_complete.json'),'task_pack':'task_pack_complete.json','task_pack_sha256':h(O/'task_pack_complete.json'),'ready_for_submission':ready,'placeholder_urls_present':not ready}
save('publish_manifest_complete.json',manifest)
listing=pub.load_submission_manifest(O/'publish_manifest_complete.json','create',None)
assert listing['differentiation_review']['status']=='PASS',listing['differentiation_review']
save('prepared_contract_complete.json',listing)
save('completion_checks.json',{'offline':'PASS','model':model,'colors':6,'SKU':60,'inventory_fields':0,'FAQ':6,'main':6,'details':4,'company':5,'canonical_differentiation':'PASS','actual_photobank_bound':ready,'safe_to_submit':ready,'no_old_off':True,'new_product_id':None,'materials':'Mesh/Rubber; custom Not specified midsole/lining; whole sole Rubber+MD','source_name_correction':'活体印刷术 -> 活字印刷术 per original color chart; original records preserved'})
print(json.dumps({'offline':'PASS','new_model':model,'counts':'60 SKU / 6 FAQ / 6 main / 4 detail / 5 company','photobank_bound':ready},ensure_ascii=False))
