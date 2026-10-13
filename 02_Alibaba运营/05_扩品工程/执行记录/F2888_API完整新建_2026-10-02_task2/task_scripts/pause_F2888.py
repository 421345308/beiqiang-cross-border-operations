from pathlib import Path
import json,datetime,hashlib,shutil
W=Path(__file__).resolve().parent;O=W/'F2888_execution';P=Path.home()/'Desktop'/'贝强'
now=datetime.datetime.now(datetime.timezone.utc).isoformat();ledger=json.loads((O/'publish_once_ledger.json').read_text(encoding='utf-8'));pid=ledger['product_id'];assert pid=='1601970034464'
state={'paused':True,'paused_at_UTC':now,'authorization':'User Sentinel_6ecc1ce493f081919c00bc62f8883936: 先暂停咱们的上品任务，额度重置了','since_resume_new_product_count':1,'new_product_id':pid,'new_model':'BQ-WBF2888','last_formal_status':'new','last_display':'N','actual_score':None,'score_status':'PENDING: read request returned generic validation failure while product new/N; no valid score returned','score_error_request_id':'213f5a2117909807503223158','old_OFF_count':0,'old_action':'NOT_SENT','old_product_id':'1601943775160','create_result':'CONFIRMED submitted_needs_readback','create_request_id':ledger['refs']['request_id'],'unknown_or_inflight_writes':[],'automatic_resume':False,'next_action':'Require a new explicit user resume. Read same existing ID only; never recreate. Score and public QA pending. Parent knowledge owner binds shared mapping/new ID.'}
(O/'PAUSED_USER_2026-10-02.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
runtime=W/'api_F2888.py';s=runtime.read_text(encoding='utf-8');needle="O=W/'F2888_execution';O.mkdir(exist_ok=True)";s=s.replace(needle,needle+"\nassert not (O/'PAUSED_USER_2026-10-02.json').exists(),'Explicit user pause; no automatic resume'");runtime.write_text(s,encoding='utf-8')
trace=json.loads((O/'source_traceability.json').read_text(encoding='utf-8'));trace['international_product_id']=pid;trace['public_url']='https://www.alibaba.com/product-detail/Women-s-Quilted-Winter-Boots-with_1601970034464.html';trace['publication_state']='CONFIRMED_CREATE_PENDING_REVIEW_SCORE_PUBLIC_QA_USER_PAUSED';(O/'source_traceability.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'execution_outcome.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
h={'supplier_name':'联晟鞋业','supplier_original_model':'H219','supplier_original_direct_url':'https://ls2017.sooxie.com/detail/1565538','our_model':'BQ-ABH219','international_product_id':'1601969936536','actual_score':5.0,'score_observed_at':'2026-10-02T17:50:29.345077+00:00','old_OFF':'NOT_SENT','source_model_evidence':'Original ls2017_1565538/page_text.txt has 货号：H219; supplier 联晟鞋业','status':'Prior completed create, no recreation in resumed session; public QA/keyword persistence pending browser owner'}
(O/'source_traceability_delivery_all_owned.json').write_text(json.dumps({'rows':[trace,h],'master_table_writer':'Parent knowledge owner only; no shared master modification'},ensure_ascii=False,indent=2),encoding='utf-8')
doc=f'''# F2888 暂停断点

用户已明确暂停（Sentinel_6ecc1ce493f081919c00bc62f8883936）。没有自动恢复任务；运行脚本加了暂停守卫。

本次22:13恢复后新增1条，F2888 / BQ-WBF2888 / {pid}。创建UTC22:38:07，request {ledger['refs']['request_id']}。正式get已返回24SKU、真实阶梯11.87/11.08/10.29美元、6主图、正确型号和Not specified材料；最后审核new/展示N，render无data。评分接口通用验证失败，无有效评分，actual_score=null。未再发评分/修改请求。公开页及详情完整审核未完成，不能报改造完成。

来源：尚潮鞋业，供应商原货号F2888，[原始商品直达](https://shangchao.sooxie.com/detail/2357652)。货号证据evidence/page_text.txt。SKU三色35–42共24，原图及裁切/上传SHA保留。14次图片上传全部明确成功（13个在用素材+1个被新版主图替代的未使用素材），无未知写入。创建一次明确返回新ID，无重发。旧HR056-A /1601943775160未OFF；其它旧产品未操作。

唯一下一步：待用户再次明确恢复后，以此已有ID续做审核get、实际5分和父浏览器公开QA；禁止重新创建。现有manifest/taskpack属首次创建历史，不重新执行。共享映射仍待父知识线程绑定新ID，任务本地已保存确切原HR映射副本及规范投影，无共享表写入。

H219此前ID1601969936536/5.00保留，无重复创建。全款溯源交付文件source_traceability_delivery_all_owned.json包含联晟鞋业/H219/原直达URL/我方BQ-ABH219及国际站ID。
'''
(O/'README_暂停交接.md').write_text(doc,encoding='utf-8')
print(json.dumps(state,ensure_ascii=False))
