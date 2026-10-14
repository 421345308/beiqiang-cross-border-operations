# 审核产物契约

所有产物是JSON对象，有 `kind`、`summary`。工具提交会绑定 `task_id` 和真源 `sku`；引用已有文件时这两项必须已匹配。结构通过不等于内容正确。

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
