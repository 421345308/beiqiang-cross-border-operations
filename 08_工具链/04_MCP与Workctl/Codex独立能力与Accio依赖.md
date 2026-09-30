# Codex独立能力与Accio依赖

日期：2026-09-29。负责人授权：整理可复用能力、注意模型及额度；HR全量替换继续优先推进。

## 已能独立调用

Codex现有授权OpenAPI客户端：`.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py`。它自行调用Alibaba官方接口，使用外置授权配置，不调用Accio、不调用WorkBuddy、也不消耗它们的模型轮次。

| 能力 | 独立实现 | 本轮证据 |
| --- | --- | --- |
| 商品正式读取、审核状态与SKU | `alibaba.icbu.product.get` | HR015三条完整正式回读及42个实际SKU；HR016写前正式对象 |
| 当前商品Schema及原生字段 | `alibaba.icbu.product.schema.render` | HR015真实替换计划；HR016当前Schema材料/尺码规则 |
| 标题、型号、图库、色码、材料等原生更新 | `alibaba.icbu.product.schema.update` | HR015冻结native执行与正式身份回读；更新前须逐款当前Schema |
| 正式图片银行上传、CDN验证 | `alibaba.icbu.photobank.upload`＋本地字节核对 | HR016五张批准图已入库，五张CDN原字节核对通过 |
| 质量分诊断 | `alibaba.icbu.product.score.get` | 已有全店及分款调用证据；具体分数以当次回执为准 |

这些能力已在Codex实际使用；无需在Accio里再次让模型执行同一工作。凭证留在既有外置配置，不复制到指南、Git或代理上下文。

## 当前仍依赖Accio网关

Workctl的结构化草稿读取/编辑、详情与公司模块编辑、正式草稿提交等当前走Accio Desktop后端。现有适配器不是脱离Accio的证明。`remote-registry`是另一后端，但当前测试缺可用RegistryURL；不能伪造地址或宣称已迁移。

需要逐项确认官方独立入口、当前授权、请求格式及回读一致性，才能替换这一层。目前保留已验证的网关流程推进HR，不为迁移反复启动浏览器或模型。

## 沉淀方式与验收

1. 把选品证据路由、标题判断、图库角色、公司图复用、三档价及失败处理写成简短指南；单款事实留在单款台账。
2. 把机械调用封装成可重跑的本地工具：读操作独立；写操作有明确对象、载荷SHA、启动标记和正向业务回执。不要把模型推理或提示词当作可验证接口。
3. 每迁移一个能力，以实际商品对照输入、正式对象、库存、素材与受保护字段；必要时验买家页。独立运行成功才标记可脱离Accio。
4. Accio仅用于独立入口尚不可用的能力或必要补充；简单机械执行不启动模型。需要推理/视觉时只给相关证据，核对当前可用模型和消耗后选择，不猜价格。

独立只读入口：`08_工具链/01_业务脚本/国际站审计/alibaba_direct_product_audit.py`。它只导入既有OpenAPI客户端，输出商品与质量分证据，代码不调用Accio进程或网关。
