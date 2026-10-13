from pathlib import Path
import json,hashlib,shutil,datetime,importlib.util,sys
sys.dont_write_bytecode=True
W=Path(__file__).resolve().parent;O=W/'H219_execution';P=Path.home()/'Desktop'/'贝强'
R=P/'02_Alibaba运营/05_扩品工程/执行记录';M=R/'9968_API完整新建_2026-10-02'
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=O/'evidence';e.mkdir(exist_ok=True)
ev=[]
for src in M.glob('live_catalog_*.flat.json'):
 dst=e/src.name;shutil.copyfile(src,dst);ev.append({'path':str(dst.relative_to(O)),'sha256':sha(dst),'kind':'catalog_snapshot'})
for name in ['candidate.json','public_index.json','page_text.txt']:
 dst=e/name;shutil.copyfile(W/'ls2017_1565538'/name,dst);ev.append({'path':str(dst.relative_to(O)),'sha256':sha(dst),'kind':'source_register'})
mapping=next((P/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21').glob('*一对一*.json'))
original=json.loads(mapping.read_text(encoding='utf-8'));row=next(x for x in original['rows'] if x.get('candidate')=='H219')
assert row['old_product_id']=='1601943767092' and row['protected'] is False and row['new_product_id'] is None
# Preserve the owner's original row; map its strategic-not-identical semantic
# into the mature contract's explicit enum in a task-local projection only.
shutil.copyfile(mapping,e/'owner_mapping_original.json')
normalized=dict(row,match_type='STRATEGIC_RETIRE_AND_REAL_SOURCE_REPLACEMENT_NOT_IDENTICAL_SHOE')
save('replacement_mapping_projection.json',{'rows':[normalized],'original_path':str(mapping),'original_sha256':sha(mapping),'normalization':'STRATEGIC_RETIRE_NOT_IDENTICAL_SHOE -> existing contract strategic real-source enum; no old-off authorization added'})
shutil.copyfile(M/'company_v3_manifest.json',O/'company_v3_manifest.json')
facts=json.loads((O/'facts_and_copy.json').read_text(encoding='utf-8'));facts.update(public_model='BQ-ABH219',category=201768405,ordinary_HR_target={'old_listing':row['old_listing'],'old_product_id':row['old_product_id'],'old_action':'NOT_SENT','retained_siblings':row['retained_siblings']})
save('facts_and_copy.json',facts)
candidate={'source':{'reference':facts['source_url'],'style':'H219 single-shoe Brown/Black size35-40','evidence':'evidence/candidate.json + public_index.json + actual original detail_03/05/10/11/14','critical_facts':{'profile':'women lace-up ankle boot','upper_structure':'PU round-toe ankle upper','outsole_structure':'rubber lug sole','closure':'front lacing and inner-side zipper','lining':'single-shoe composition not specified','functional_use':'casual ankle footwear'}},'search_intent':{'key':'women lace up ankle boots side zipper lug sole','evidence':'Existing H219 source facts and parent-delegated Target proxy; search volume unknown'},'hero_review':{'content_key':'H219-black-pair-handheld-original-detail03','label_status':'not_present','evidence':'Source detail_03 and individually viewed H219_M1 output; complete actual shoes, no third-party footwear mark; no price/Chinese'}}
save('differentiation_review.json',{'candidate':candidate,'source_records':{},'evidence_files':ev,'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'coverage_limit':'Existing saved three catalog pages only; unknown source associations do not establish global clearance. No global re-audit performed.'})
template=P/'02_Alibaba运营/05_扩品工程/工厂店外新款数据采集模板.md'
doc='''# H219 单款经营任务包

## A. 身份、来源与商业字段
task2唯一写入者；REPLACE，图文生产与首次发布；公开型号BQ-ABH219，类目201768405，productId未创建。搜鞋网https://ls2017.sooxie.com/detail/1565538；实际供货H219，棕/黑单鞋35–40共12SKU，不含加棉。PU鞋面、橡胶外底、前系带、内侧拉链、圆头；内里/中底/鞋垫/工艺未指定。Schema必填内里、中底使用其允许自定义“Not specified”，可选未知省略。拿货60元；50%/40%/30%加价，MOQ2、50/100阶梯，项目固定汇率6.6987、美分上取整。包装34×23×13cm/0.5kg为用户授权运营基线而非实测。库存可选省略，不为评分编999。

## B. 需求与款型匹配
复用源候选包的Target Dunes Kobe与Soda FIRM父线程代理观察：女性圆头系带短靴方向。不同品牌、材质或性能不迁移；无该款海外销量或舒适、防滑验证，不宣传这些性能。

## C. 词与标题
Women's Lace-Up Ankle Boots with Side Zipper and Lug Sole；核心词women lace up ankle boots，侧拉链/圆头/PU/实际底纹均源证。搜索量未知。发布后正式关键词若空值标待补，不以本地文案宣称持久化。

## D. 六主图、四详情、五公司图与SKU
asset_manifest.json逐张原图有效裁切像素、展示尺寸与SHA；M1实际黑色双鞋完整轮廓，M2两色，M3拉链，M4橡胶底纹，M5棕色上脚，M6PU鞋面；D1选项、D2闭合、D3外底、D4询价输入。照片裁切排除中文、加绒和背景品牌字，不重画鞋。SKU另用无文字单色实际白底原鞋图。公司复用已批准v3整套五图与原银行ID，泛公司能力不冒充本款自产。

## E. 执行与独立验收
既有schema publishing entry、当前叶子Schema与哈希；单次创建账本防重复。完成后正式get/render检查型号、12SKU、阶梯、MOQ、6/4/5图、FAQ，实际score>=5、独立公开买家页QA。当前全部发布/评分/公开QA未完成；不发供应商消息。

## F. 新旧映射与保护
owner既有映射指定HR048-B /1601943767092，今日普通且protected=false；HR048-A/C潜力保留。实际不同鞋型战略替换，无同鞋去重豁免；保留原映射并在本地投影规范既有contract枚举，不新增old-off授权。新建完成后绑定唯一新ID，旧下架交独立owner在新内容验收、score5、公开QA及旧状态/关联再次核实后处理。

## G. 观察与下一动作
内容小试，不声称转化或蓝海。下一动作：已核图后上传、当前Schema预检、一次新建与正式验收。UTC18:00硬停止，无自动续跑。
'''
(O/'经营任务包.md').write_text(doc,encoding='utf-8')
def evidence(p,kind):return {'path':str(p),'sha256':sha(p if p.is_absolute() else O/p),'kind':kind}
pack={'task_id':'H219_2026-10-02_task2','role':'REPLACE','phase':'PREPARING_CURRENT_SCHEMA_CREATE','writer':'task2','next_action':'Upload reviewed images, prepare and submit once, formal readback and public QA; no automatic old-off','public_model':'BQ-ABH219','category_id':201768405,'product_id':None,'source_identity':candidate['source'],'search_intent':candidate['search_intent'],'hero_review':candidate['hero_review'],'replacement_plan':{'candidate':'H219','old_product_ids':[row['old_product_id']]},'evidence_files':[evidence(template,'task_pack_template'),evidence(Path('经营任务包.md'),'task_pack_document'),evidence(Path('replacement_mapping_projection.json'),'replacement_mapping')]}
save('task_pack.json',pack);print('Staged H219 taskpack; exact HR048-B bound; original owner mapping preserved; no platform write.')
