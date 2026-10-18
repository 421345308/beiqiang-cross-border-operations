# 已核低分商品 FAQ 补缺实际结果

记录时间：2026-10-03T08:12:03.244765+00:00。仅处理既有 39 条核查中的 15 个 FAQ 同类项，未重扫全店。

已提交 14 条，FAQ 精确回读 14 条，未涉及字段完整保留 14 条，共 605 个 SKU。当前正式 5.0 通过 14 条；提交成功不等于提分成功。

| 商品 | ID | FAQ | SKU | 状态 | 实际分 | 验收 |
|---|---|---:|---:|---|---:|---|
| BQ042 / 206 | 10000047166193 | 8 | 33 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ043 / 8008 | 10000047175212 | 8 | 44 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ046 / A155 | 10000047187673 | 8 | 33 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ050 / A828 | 10000047196608 | 8 | 61 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ048 / A212 | 10000047198577 | 8 | 88 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ052 / 9212 | 10000047201716 | 8 | 40 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ047 / A189 | 10000047208726 | 8 | 14 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ051 / K6689 | 10000047216427 | 8 | 33 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ049 / A230 | 10000047220568 | 8 | 50 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ044 / 811 | 10000047221334 | 8 | 66 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ053 / 1888 | 10000047307924 | 8 | 44 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ061 / AA811 | 10000047356491 | 8 | 44 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ059 / A1888 | 10000047392343 | 8 | 22 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |
| BQ060 / A350 | 10000047396313 | 8 | 33 | approved/Y | 5.0 | PASS5_FORMAL_FIELDS_VERIFIED |

每款只有一次写入，字段限 companyFaqDesc，依赖 productDescType；FAQ 数量按该商品当前 Schema maxItemsRule 决定，本轮为 8。MOQ/阶梯价格逐款从当前正式字段读取，未机械套默认值。定制答复仅询问需求和订单级评审，不新增 OEM、现货、材料、认证或固定交期承诺。公司简介已有内容，未为凑分重写。

复用唯一工具入口：`08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py::api_submit` 和 `schema_publish_contract.py::prepare_scoped_listing`，操作为既有商品 `update`，仅处理原有 type4 结构化 FAQ。这批成功不扩展为任意类目、任意详情形式永久支持。下次检索 BQ042/BQ043/BQ046 的成功方案可直接读取本目录逐款 `reviewed_payload.xml`、`fact_basis.json`、`update_once_receipt.json` 和最终 `review*/score.json`；必须重新获取目标当前 Schema 和资料，不复制原型号、价格、MOQ 或数量限制。

标题、关键词、主图、SKU 全体 ID/编码/价格/库存、材料属性、交易字段、商品类目、产品/公司图集及原简介全部比较。网络失败只能记未知，不能写字段丢失；BQ060 首次只读回验超时已保留，第二次读取成功。

首批已审核上架，官方分仍 4.9 时，公开诊断没有明确扣分项，不猜测补其他字段、不重复提交同一 FAQ。后续分数须以带时间与 request_id 的正式回执确认；modified/N 不计通过。

DZ14546082-A：来源尚未在既有证据中定位，HOLD_SOURCE，未发送。

M001：当前首图是来源 05.jpg 中提取的 630×455 上脚图，提取坐标 (145,690,775,1145)；后续 455×455 方形裁切未执行。官方最新实际分 4.5，image_scale 扣 0.5。已通过图像生成工具制作两张优化背景/构图的候选，第一张改写孔纹/侧纹，第二张仍无法确认孔纹与模压边界的保真性；均未上传或更新商品，不能为 5.0 使用失真图。证据在 hero_review_current/visual_qa_rejection.json。

929 SKU 重建及 A6607 经营设置均未改动。此前两次自动审批拒绝记录保留；本执行线程收到直接 role=user 授权后才执行本轮写入。
