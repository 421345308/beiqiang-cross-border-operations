from pathlib import Path
import json,datetime,shutil,sys
W=Path(__file__).parent;P=Path(r'C:\Users\spq\Desktop\贝强');O=W/'805_execution';O.mkdir(exist_ok=True)
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime(2026,10,2,18,tzinfo=datetime.timezone.utc)
shutil.copytree(W/'driver_selection/805',O/'source/published',dirs_exist_ok=True)
for n in ['source.html','source_text.txt','source_attributes.json','image_manifest.json']:shutil.copyfile(W/'driver_selection/805'/n,O/'source'/n)
ownership={'style':'805','model':'BQ-D805','owner':'task-7','source_url':'https://yut.sooxie.com/detail/559264','status':'PREPARING_NOT_PUBLISHED','old_product_ids':[],'new_product_id':None,'stop_at_utc':'2026-10-02T18:00:00Z'}
claim=P/'02_Alibaba运营/05_扩品工程/执行记录/805_待发布包_2026-10-02';claim.mkdir(exist_ok=True)
if (claim/'ownership.json').exists():assert json.loads((claim/'ownership.json').read_text(encoding='utf-8'))['owner']=='task-7'
else:
 with (claim/'ownership.json').open('x',encoding='utf-8') as h:json.dump(ownership,h,ensure_ascii=False,indent=2)
(O/'ownership.json').write_text(json.dumps(ownership,indent=2),encoding='utf-8')
q=P/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR持续替换目标与货源队列_2026-10-02.md';tag='## task-7 豆豆鞋唯一占用：805 / BQ-D805'
if tag not in q.read_text(encoding='utf-8'):
 with q.open('a',encoding='utf-8') as h:h.write('\n\n'+tag+'\n\n来源 https://yut.sooxie.com/detail/559264；task-7唯一文件和平台写入owner。CNY75，红/浅棕/蓝38–44，橡胶底/PU内里/胶粘，鞋面字段未知不填牛皮。独立实际原图复核5块分区接地片及后跟上翻小块、moc-toe围缝双流苏及压纹，区别HR010/006/003；Duluth仅需求方向代理，本款TEST，不称圆豆/手工/防滑/驾驶安全/自产。6M4D、官方上传、全量当前去重、单次Schema及验收待完成。旧HR父知识owner映射，本任务不下架。18UTC停止。\n')
for src,dst in [('schema_3522.py','schema_805.py'),('pipeline_3522.py','pipeline_805.py'),('bind_3522_differentiation.py','bind_805_differentiation.py')]:
 t=(W/src).read_text(encoding='utf-8').replace('3522','805').replace('BQ-L805','BQ-D805').replace('2541782','559264').replace('gediao','yut')
 if dst=='pipeline_805.py':t=t.replace("[('Green','00'),('Black','01'),('Beige','03')]","[('Red','03'),('Brown','01'),('Blue','05')]").replace("['BQ-D805','559264','yut','805']","['BQ-D805','559264']")
 if dst=='schema_805.py':t=t.replace("for method,params,name in", "sys.path.insert(0,str(W if False else Path(r'C:\\Users\\spq\\Documents\\Codex\\2026-10-02\\task-8')));from sdk_runtime_5998 import load;sdk.http_json=load().http_json\nfor method,params,name in")
 (W/dst).write_text(t,encoding='utf-8')
print('805 sole owner and source registered; platform writes none',flush=True)
