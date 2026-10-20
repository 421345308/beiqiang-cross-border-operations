# 商品表现诊断与处置

业务唯一入口：[店铺经营诊断](../../../../02_Alibaba运营/01_店铺与全店诊断/店铺经营诊断.md)。本目录不维护第二份商品规范。

`diagnose_product_performance.py`只读当前完整目录、台账和带日期的表现原件，缺失保持空，换实鞋后的新款不套用旧鞋数据。诊断信号只触发复核，不自动证明原因或下架。

`apply_product_performance_actions.py prepare|submit|verify --ids ...`执行业务入口已明确的范围：重复弱链接可恢复下架、只改标题、明确校验错误的自定义属性清除。按当前Schema生成最小字段载荷；写入前再查当前值，每ID只提交一次，结果未知或审核中只回读。不得在此扩展类目、规格、报价或广告写入。空字段清除能否生效必须等正式回读证明，不能靠提交成功推断。

`sync_product_performance_actions.py`将当前实际回读写入台账、单款入口与来源的当前链接状态，不把下架误记为缺来源；当前值、拟稿与审核结果分开记录。旧货号/工厂图库同步工具遇到较新的本任务状态不会回写旧快照。

BQ1030-A/B已由负责人明确为平台侵权退回，计划与来源当前档案均标记停止原鞋原图重提，执行工具在调用API前拒绝这两项的准备/提交。Shoe Profile校验是独立编辑错误，不能当作侵权退回原因；历史5分和短暂approved不代替当前发布状态。具体平台权利通知尚未读取，不猜权利类型或靠抹图/改题重新投放。

后台原始统计、账号、登录和客户资料只保留本地；公开Git只同步派生经营结论、非敏感工具、公开商品字段与核验。运行安全测试：`python -m unittest discover -s 08_工具链/01_业务脚本/国际站经营诊断 -p test_*.py`。

## 当前内容质量复核

业务入口为[内容质量复核](../../../../02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/内容质量复核/README.md)，不从旧批次脚本继承商品事实。

- `read_content_quality_catalog.py`：只读完整当前目录、逐 ID 正式字段与对应公开来源。
- `audit_current_gallery_visuals.py`：去重下载当前图库，生成家族联系表作人工筛查；生成成功不代表视觉通过。
- `collect_exact_source_photos.py --families ...`：按台账对应精确来源采集原图，不搜索替代鞋冒充同款。
- `revise_catalog_content.py prepare|submit|verify|sync [--ids ...]`：只改已审核的标题/功能亮点，保护通用 FAQ、图片、SKU 和商业字段。`--correction` 使用单独纠正证据，`--followup-phase 正式差异收尾` 仅供已回读的具体后续差异；账本存在时不重放写入。
- `repair_m001_catalog.py bank|prepare|submit|verify|sync`：M001 原 ID 的三色18并码、原SKU保留和整组图文专项；当前已正式通过，不再提交。
- `repair_source_assortment.py bank|prepare|submit|verify|sync --family ...`：读取逐款已审计划，补实图颜色或移除有来源依据的误扩尺码，保留其余 SKU ID/编码/价格与页面。移除须声明精确旧SKU ID、理由和来源；合同校验仍拒绝静默删SKU、保留行换绑和同时新增无绑定行。新颜色图须原图对照和图审通过后才上传。每色范围分别填写，不把来源全店范围扩到受限颜色。

API 核验只证明正式字段、审核和评分，不代表原尺寸图审、实物库存或公开页面视觉通过。所有写入先准备当前 Schema、提交前检查当前值、每 ID 留一次账本，未知结果独立回读后决定具体修正。

`repair_added_sku_marker.py prepare|submit|verify|sync`仅执行负责人已明确确认的R1811三条新增33SKU/条的999可询货标记。先对原33与新33的身份、逐色EU范围和当前独立库存值；增量API每ID只提交一次，未知结果不得重放。`reconcile_r1811_content.py`对后续图库正式回读与前序库存、颜色、文案证据作综合验收，保留旧评分报告。`audit_colour_bindings.py`输出全目录SKU颜色图片联系表，筛查成功不代表修复通过；`sync_content_media_index.py`只按图片银行身份和SHA绑定当前本地素材，不复制媒体。

`repair_reviewed_gallery.py`只执行已审图片计划，支持完整图组、只换主图库、按精确图片身份纠正详情图。不同链接工厂图位置与get/render的详情排列可以不同，不能按第六槽/第一张猜；单图纠错逐原图ID核图集归属与多重集合，图库重做核有序首图。CDN原图/缩略形式只按已核身份等价，未知格式保持失败。`render_content_quality_preview.py`生成唯一图片复核页，出图/提交/正式生效分别展示。
