from pathlib import Path
import json,shutil,datetime
W=Path(__file__).parent;O=W/'3522_execution';P=Path(r'C:\Users\spq\Desktop\贝强');dest=P/'02_Alibaba运营/05_扩品工程/执行记录/3522_API完整新建_2026-10-02'
receipt=json.loads((O/'publish_receipt.json').read_text(encoding='utf-8'));assert receipt['product_id']=='1601969920294'
checks=json.loads((O/'formal_checks.json').read_text(encoding='utf-8')) if (O/'formal_checks.json').exists() else {'status':'PENDING_READ','display':None,'actual_score':None,'public_acceptance':'PENDING','completion_status':'PENDING'}
claim=json.loads((O/'ownership.json').read_text(encoding='utf-8'));claim.update(product_id='1601969920294',status=checks.get('completion_status','PENDING'),platform_submit_status=receipt['status'],formal_status=checks['status'],actual_score=checks.get('actual_score'),updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat());(O/'ownership.json').write_text(json.dumps(claim,ensure_ascii=False,indent=2),encoding='utf-8')
dest.mkdir(parents=True,exist_ok=True);shutil.copytree(O,dest,dirs_exist_ok=True)
for name in ['prepare_3522.py','pipeline_3522.py','audit_3522.py','build_3522_images.py','archive_3522.py','bind_3522_differentiation.py','dedup_3522_images.py','verify_3522_cdn.py','schema_3522.py','watch_3522_readonly.py','watch_3522_score.py','research_title_3522.py','keyword_3522_probe.py','keyword_field_3522.py','cow_suede_3522.py']:shutil.copyfile(W/name,dest/name)
text=f'''# 3522 / BQ-L3522 执行回执

商品ID：1601969920294。单次schema.add于2026-10-02T15:19:04Z成功；request_id 0bbb3b2417909543537025346。未写其他商品，未删除或下架旧HR，未写库存，未重发新建。

真实来源：https://gediao.sooxie.com/detail/2541782。采购标价85元；牛反绒鞋面、PU内里。必填外底、中底和产地缺证据使用当前schema支持的真实自定义Not specified；未知鞋垫可选值省略。黑、绿、米三色，原始标签39–46，共24 SKU。6主图、4详情、3颜色原图通过独立像素与375px复核；5原v3公司图复用。13张新图均取得正式图片银行URL/ID。CDN有JPEG再压缩，保留原始与官图真实hash及像素复核，未宣称逐字节相同。

价格依据：85 CNY，项目报价汇率6.6987 CNY/USD，数量2/50/100双按50/40/30%加成、向上取分，19.04/17.77/16.50 USD/pair，MOQ2双。供货、议价、逐码可用量、样品、定制、实际包装及发货安排在客户询价时确认。

发布前13页完整目录365条、无本款同源/型号命中。实际近款30张当日主图加HR006C历史正式来源复核；HR003豆豆底金属端绳、HR044横带厚黑底、HR020C短全孔围片侧松紧等均与本款长素面围片/外围圆孔/无饰件/连续薄白底不同。当前发布器的目录、来源登记、型号及实际首图绑定PASS。

正式状态：{checks['status']}/{checks['display']}。actual_score={checks.get('actual_score')}，target_score=5.00。公开验收：{checks.get('public_acceptance')}。闭环：{checks.get('completion_status','PENDING')}。字段、SKU、颜色与图集实际结果以formal_checks.json及原回执为准。

运营层限定：本款为“差异化测试候选”，尚未取得本款海外畅销、搜索量或转化验证，不能称“畅销优款”。具体目标买家、测试理由、Clarks/Kohl's/Alibaba用词与结构在售证据、真实长尾词见operating_demand_review.json与operating_test_plan.json。父任务推荐标题与单个核心长尾词已准备2字段最小更新；实际回执/生效状态见research_title_update，不移植品牌图或性能。该限定不推翻实物来源、API状态或真实平台分数，也不以平台5.00证明实物品质/销量。

归档UTC：{datetime.datetime.now(datetime.timezone.utc).isoformat()}。
'''
(dest/'README.md').write_text(text,encoding='utf-8')
pending=P/'02_Alibaba运营/05_扩品工程/执行记录/3522_待发布包_2026-10-02/ownership.json';pending.write_text(json.dumps(claim,ensure_ascii=False,indent=2),encoding='utf-8')
queue=P/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR持续替换目标与货源队列_2026-10-02.md'
tag='3522平台新建：1601969920294'
if tag not in queue.read_text(encoding='utf-8'):
 with queue.open('a',encoding='utf-8') as f:f.write('\n\n'+tag+'；BQ-L3522；唯一写入者task-7；单次schema.add业务成功，当前正式/公开/5.00验收以执行记录/3522_API完整新建_2026-10-02为准；海外需求依据待父任务研究复审。\n')
print(dest)
