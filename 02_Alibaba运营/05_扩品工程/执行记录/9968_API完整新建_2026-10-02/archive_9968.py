from pathlib import Path
import json,shutil,datetime
W=Path(__file__).parent;O=W/'9968_execution';P=Path(r'C:\Users\spq\Desktop\贝强');dest=P/'02_Alibaba运营/05_扩品工程/执行记录/9968_API完整新建_2026-10-02'
receipt=json.loads((O/'publish_receipt.json').read_text(encoding='utf-8'));assert receipt['product_id']=='1601969788941'
dest.mkdir(parents=True,exist_ok=True)
shutil.copytree(O,dest,dirs_exist_ok=True)
shutil.copytree(W/'MaryJane_selection/9968',dest/'source_evidence',dirs_exist_ok=True)
for name in ['prepare_9968.py','pipeline_9968.py','audit_9968.py','build_9968_images.py','archive_9968.py']:shutil.copyfile(W/name,dest/name)
checks=json.loads((O/'formal_checks.json').read_text(encoding='utf-8'))
text=f"""# 9968 / BQ-MJ9968 API执行记录

真实商品ID：1601969788941。仅单次schema.add，无旧品删除/下架，无库存写入。业务成功request_id：2105584317909502611455670。

来源：https://qdnx.sooxie.com/detail/2532759，采购标价60元；合成革鞋面/内里、橡胶外底、PU鞋垫、胶粘。真实单宽魔术贴结构；未知中底填写schema合法自定义Not specified。灰/绿/蓝，原标尺码35–40，18个SKU。无专业性能、真皮或本款自产声明。

HR021-C已通过独立真实主图及当日正式回读精确去重；既有源26CZYA22-113为双扣款，不与本款同源。363条当日历史+新近期身份未找到9968；覆盖和读超时限度详dedup_gate.json。

6主图+4详情+5原v3公司图；13新图官方图片银行URL/ID及账本完整。D4初次socket连接失败在发出前停止，经官方bank读核证明无对应文件，保留D4_failed_transport_reconciliation.json后完成实际上传。价格图禁用。375px10图独验PASS，最终载荷独验PASS。

60元按项目报价汇率6.6987及50/40/30%加成向上取分：2/50/100双起13.44/12.54/11.65美元。供货、逐码库存、样品、定制、包装和发货逐单询价确认。

正式字段按18个稳定SKU编码核验所有平台SKU ID、色码组合及三档价。平台返回的skuId、图库顺序以及空库存不是新建失败，不重复创建。库存输入omitted_all，首次及后续库存API均空data_list，没有999写入。

最新状态：{checks['status']}/{checks['display']}；非空product.get字段核验PASS；render可用：{checks['render_nonempty']}。评分actual_score={checks['actual_score']}，target_score=5.00，状态{checks['score_status']}。审核approved/Y后评分API仍15，原始回执已保存；参数与official encrypt.secret_id及最新product.get加密ID一致，原因未确定。公开验收：{checks['public_acceptance']}；闭环状态：{checks.get('completion_status','PENDING')}。

买家页：https://www.alibaba.com/product-detail/Women-s-Colorblock-Mary-Jane-Flats_1601969788941.html

归档时间UTC：{datetime.datetime.now(datetime.timezone.utc).isoformat()}。{('本款已完成正式及公开5.00分闭环；供货、逐码数量、议价和进一步材料规格由客户询价时逐单核实。未改其它商品、未下架旧HR。' if checks.get('completion_status')=='COMPLETE' else '仅回读审核/评分，按真实扣分项修复；禁止重复schema.add或自动999。达到5.00且完成公开验收方可计完成。')}
"""
(dest/'README.md').write_text(text,encoding='utf-8');print(dest)
