# 贝强电商经营 Agent：总入口

当前版本 **v0.2.1**。在原有本地任务后端上，加入平台/发布位置分类、品类视角、同品多种呈现、多平台任务与具体字段差异。它接收自然语言，由宿主完成专业创作和判断，MCP/CLI保存真实资料、策略、依赖和审核成果；没有另开付费模型API。

本文件是技术项目唯一总入口。商品、公司、客户与授权仍读原业务源，不建影子产品主库或CRM。当前源码位于 [beiqiang-commerce](beiqiang-commerce/)，Python 3.11+、标准库运行；插件21个工具，源版本与本地官方安装版本保持一致。

## 已实现的分类与协作

| 层 | 当前实现 | 它解决的问题 |
| --- | --- | --- |
| 平台与位置 | Alibaba商品页/视频；抖店商品、抖音短视频/直播切片；小红书商品/图文/视频笔记；Amazon商品页/视频；独立站商品/落地页/品牌视频；TikTok短视频 | 同平台的商品上传与内容发布分开，平台ID与账号能力不混用 |
| 商业模式与目标 | B2B、零售、内容；发现、考虑、购买、询盘、品牌、留存；每个目标单独指定市场、语言、受众 | 不把MOQ放进零售卖点，不用播放量代替有效商机 |
| 品类 | 鞋、服装、美妆、家居、电子、食品饮料、配饰、通用，共8种提问视角 | 品类只帮助提出问题，不自动生成材料、性能或实物事实；贝强真实资料仍主要是鞋类 |
| 呈现方式 | 生活故事、问题演示、身体/手部试用、选择指南、日常场景、搭配、细节、开箱、步骤、真实对比、测试证据、工厂过程，共12条路线 | 同款可有多个不同说服方式；用户选择优先，测试/对比/工厂方向缺证时排除 |
| 任务与产物 | 共享身份→定位→平台独立分支→实验→审核；窄任务仍独立执行 | 平台分支分别留语言、位置、素材、指标和待核项，不能换标签冒充完成 |
| 变更与数据 | staged字段差异；版本/证据失效检查；跨渠道JSON切片；本地可读审核稿 | 缺基线明示未知，缺数据为null，不混算B2B询盘和零售订单 |

推荐排序是编辑启发式，不是销售预测。8类/12条路线是可扩展配置，具体产品能否使用，要读其事实、素材、场景与当前目标。外部内容只作资料，不能改变工具规则。

[开源参考与实现依据](开源参考与实现依据.md)记录Anthropic commerce-agents、SuperCMO、Shopify的锁定版本、实际阅读范围、许可、采用设计及官方文档缺口。代码独立实现，没有移植整个Claude运行时。REA的[原仓库](https://github.com/morluto/rea)与[官网](https://rea.tools/)已核，属于研发分析工具；未指定调查目标，没有安装或执行逆向。

## 可以直接审核的真实商品示例

[BQ028跨平台审核示例](beiqiang-commerce/examples/BQ028跨平台审核示例.md)包含五个平台、六个位置：Alibaba商品页、抖音短视频、小红书图文笔记、Amazon商品页与详情视频、B2B独立站落地页。三个内容位置各写三个具体方向，共九个创意；包括实际台词/图页/镜头事件、产品参与、声音、素材职责和制作检查。

抖音保留已认可28秒七场八句柯基故事，另提供拿快递/先走两步方向；小红书回答看鞋型、后跟与选择问题；Amazon用英语试穿/细节/日常穿着；独立站承接采购需求。现有影片与画布没有因开发改动，也没有新生成。

[请求](beiqiang-commerce/examples/bq028-campaign.request.json)与[宿主创作内容](beiqiang-commerce/examples/bq028-campaign.content.json)是可复核示例。运行下方脚本会登记这份固定示例的本地任务，不是自动编剧模型；重复执行恢复同一对象。其它商品由宿主创作自己的内容后提交产物，不能把此鞋例硬套所有品类。

```powershell
python -X utf8 '08_工具链/07_电商Agent/beiqiang-commerce/scripts/run_campaign_example.py'
```

实际示例已完成11个步骤，状态package_ready；[本地审核包](.state/exports/a625bd4a-2d0c-4fac-a584-2db3a383b99a/review-11.md)保留逐步证据。它代表草稿范围准备完成，未发布、未付费生成、没有广告数据。原影片局部反馈仍以用户观看为源，尚无代理独立完整成片QA。

## 工作流与使用

单项工作流：title、listing、video、operations、customer；单平台有数据和客户上下文的组合准备用commerce；多平台/同品多呈现用campaign。自然语言需求由宿主整理为请求，不要求用户先填一大份表。

必填workflow/goal/channel/language，除纯数据分析外选SKU。targets指定platform/placement/business_model/market/audience/goal_type/language；creative可选数量、明确风格、声音形式、时长、是否露脸和复杂度。图文位置不会继承视频时长。视频现有项目优先沿用PROJECT，当前任务不自动换语言/模型/画幅。

[commerce Skill](beiqiang-commerce/skills/commerce/SKILL.md)按需路由到[平台方法](beiqiang-commerce/skills/commerce/references/platform-playbooks.md)、[视频导演](beiqiang-commerce/skills/commerce/references/video-director.md)、[运营方法](beiqiang-commerce/skills/commerce/references/operations-playbook.md)及[产物契约](beiqiang-commerce/skills/commerce/references/artifact-contracts.md)。21个工具可通过同一个[server.py](beiqiang-commerce/server.py)调用：

```powershell
python -X utf8 '08_工具链/07_电商Agent/beiqiang-commerce/server.py' --tools
python -X utf8 '08_工具链/07_电商Agent/beiqiang-commerce/server.py' --tool commerce_create --args-file '08_工具链/07_电商Agent/beiqiang-commerce/examples/bq028-campaign.request.json'
python -X utf8 -m unittest discover -s '08_工具链/07_电商Agent/beiqiang-commerce/tests' -v
```

新增工具：commerce_catalog、commerce_strategy、commerce_stage_change、commerce_change、commerce_export、commerce_business_snapshot。身份/策略/指标步骤由后端执行，实际文案与判断由宿主完成后submit_artifact登记。相同key恢复任务；revision防覆盖；来源、策略或已登记产物变动后显示needs_refresh，须明确刷新和重审。

任务、草稿、回执和导出留本地`.state/`，包与校验记录放`.local/`，均被Git忽略。正式业务成果继续回相应入口；运行库不是事实主库。commerce_stage_change只保存具体字段前后差异，不执行提交；缺目标对象、schema、基线或适用授权的情况逐项显示。

## 连接状态与验收

| 能力 | 实际状态 |
| --- | --- |
| Alibaba、LibTV官方读取 | 已接既有官方客户端；v0.1.1曾完成BQ028 product.get和现有节点实际读取，原回执只留本地 |
| 六个平台内容准备 | 已实现位置化策略、产物和审核契约；不表示六个账号已经连接 |
| 抖音/抖店、小红书、Amazon、TikTok账号 | 未连接；缺当前账号权限、对象映射与动态schema，不伪造发布成功 |
| 独立站 | 沿用现有B2B网站入口，源码/CMS执行走实际项目工作流；Shopify只作为可选Provider研究 |
| 平台写入、消息、广告、付费生成 | 插件没有这些执行接口；适用时走已有官方业务Skills和具体授权，再取正式回读/业务验收 |
| 验证 | 55项程序检查、BQ028六位置完整准备与可读导出；安装副本stdio启动、21工具发现和调用检查 |

程序检查覆盖身份/别名、平台错绑、位置/商业模式/静态图文、品类与不同方向、缺证排除、窄上下文、产物覆盖、变更基线/重复恢复/失效、数据归因与未知值，以及原v0.1任务兼容。结构和合成测试不能证明所有品类的创作质量或经营效果。

## 安装、扩展与业务源

工作区已有`.agents/plugins/marketplace.json`和启用配置，插件名继续是beiqiang-commerce@beiqiang-workspace。源包更新后用官方`codex plugin add beiqiang-commerce@beiqiang-workspace --json`重新安装新版本，不编辑缓存。校验/打包用[verify_package.py](beiqiang-commerce/scripts/verify_package.py)；--online-schema查官方格式，--zip写源目录外的本地ZIP。已有会话未刷新工具时，可直接用CLI。

新增平台要分别补当前业务规则、账号/对象/类目schema、精确准备请求、提交/异步状态、正式回读及本地回写。新增品类要补真实商品资料和主张证据。共用任务、素材版本和反馈协议；不重复上传已有素材、不盲重跑待终态任务。

商品模块读[商品SOP](../../02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md)和[唯一台账](../../02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json)；内容模块读[视频入口](../../05_内容与视频/AGENTS.md)和[视频子模块](../02_视频工具/电商视频Agent/README.md)；运营读[增长总控](../../00_总控台/全渠道增长总控.md)；客户读[客户入口](../../04_客户开发/README.md)。既有身份、来源、事实、授权和验收规则按这些源执行。

下一条真实接入需要一个具体平台账号与业务对象，按上述接口逐项验证；当前开发不会冒用其它平台账号权限。后续评估看减少纠正、重复操作、失败返工及有效采购商机，不以配置数量或内容产量作为成功。
