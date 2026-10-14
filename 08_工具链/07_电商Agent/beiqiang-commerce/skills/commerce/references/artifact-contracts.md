# 审核产物契约

所有产物是JSON对象，有 `kind`、`summary`。工具提交会绑定 `task_id` 和真源 `sku`；引用已有文件时这两项必须已匹配。结构通过不等于内容正确。

## v0.2请求

保留v0.1字段并增加platform/placement/business_model/market/audience/goal_type/category/affordances/creative/supporting_evidence/targets。platform为alibaba/douyin/xiaohongshu/amazon/storefront/tiktok；位置通过commerce_catalog查询，不把笔记与商品、视频与listing合并。category为footwear/apparel/beauty/home_living/electronics/food_beverage/accessories/general。目标为discovery/consideration/purchase/inquiry/retention/brand。

creative示例：`{"count":3,"styles":["body_tryon","selection_guide","detail_hero"],"no_face":true,"duration_seconds":20}`。时长来自当次选择，非平台或模型限制。证据示例：`{"kind":"test","path":"工作区相对文件","basis":"记录与该款对应的确认依据"}`；程序核文件存在，宿主核真实性和适用性。

campaign的targets每项有platform，可指定placement/business_model/market/audience/goal_type/language；每个位置形成独立target_id和步骤。顶层channel可写multi，目标语言在各target分别指定。只有已有数字/客户时才附相应路径，不要求campaign为了创建而编造这些输入。

## v0.2多平台产物

- positioning：audiences/use_cases/claim_evidence/unconfirmed数组、product_role、按exact target_id覆盖的channel_differences对象。
- channel_listing：target_id/platform/placement/language、fields、claim_evidence/image_roles/unconfirmed数组、schema_status（当前动态Schema已核还是仍待核）。市场/商品ID/供给字段未确认则明示，不生成虚假可提交载荷。
- channel_content：同上目标身份及claim_evidence/unconfirmed；variants必须覆盖策略选择的variant_id。每版写hook/product_role/ending/sound/cta、具体beats数组、asset_plan数组、production_checks对象。
- landing_page：目标身份与claim_evidence/unconfirmed、sections数组、cta、message_match（入口承诺如何由页面承接）。
- experiment_plan：experiments按target_id完整覆盖；每项hypothesis/variable/primary_metric/data_needed/stop_rule、hold_constant数组、baseline（未知null）。
- campaign_review：reviewer:agent、decision:ready_for_user_review；target_checks覆盖exact targets，每项检查audience/platform_fit/claims/creative_difference/asset_feasibility/measurement/handoff，结构同下方review。

## 原v0.1产物继续兼容

| kind | 必填字段 |
| --- | --- |
| title_draft | title、rationale、claim_evidence数组；依据写出真实文件与适用范围 |
| listing_draft | 非空fields对象、claim_evidence/image_roles/unconfirmed数组 |
| video_brief | objective、audience、channel、language、product_role、duration_seconds、scenes、production_checks |
| operations_plan | observations、hypotheses、actions、missing_data数组；未知信息留在缺口 |
| customer_draft | context_path（必须与任务匹配）、channel、message、next_action、unconfirmed_terms数组、sent:false |
| review | reviewer:agent、decision:ready_for_user_review、checks对象；未解决的问题不能填pass |

video_brief的每场有 `start/end/action/cause_and_effect/product_visibility/dialogue`；时间从0开始连续，最后end等于总时长。dialogue数组可为空，各对白建议写speaker/text/mode（现场或内心）及生活处境；产品不出现的场次说明其叙事作用，不强行加鞋特写。production_checks有acting/motion/props/audio/continuity五项具体检查。模型/Provider未由用户选择时留待确认，不自行付费试跑。

review.checks每项结构是 `{"status":"pass或not_applicable","evidence":"判断依据或不适用理由"}`。各工作流所需项目：

- title：identity、claims、buyer_language、scope。
- listing：identity、claims、fields、images、inquiry_hook。
- video：story、dialogue、acting、product、motion、props、audio、continuity。
- operations：comparable_data、attribution、business_outcome、next_action。
- customer：buyer_context、terms、product_evidence、stop_contact、next_action。
- commerce：以上五组的合并项目。

这些是首版产物接口。平台发布、用户审核、付费生成、完整成片验收及真实发送有各自证据，不能由此JSON冒充。
