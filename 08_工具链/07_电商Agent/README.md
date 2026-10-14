# 贝强电商经营 Agent：总入口

当前版本 **v0.3.0**。按负责人当前范围，将国外采购链、国内客户链、开始状态和未来模板分开；任务先选具体客户，再按发布位置组织内容。它接收自然语言，由宿主完成专业创作和判断，MCP/CLI保存真实资料、策略、依赖和审核成果；没有另开付费模型API。

本文件是技术项目唯一总入口。商品、公司、客户与授权仍读原业务源，不建影子产品主库或CRM。当前源码位于 [beiqiang-commerce](beiqiang-commerce/)，Python 3.11+、标准库运行；插件21个工具，源版本与本地官方安装版本保持一致。

## 当前业务范围与客户

实际范围只读[渠道经营范围](../../00_总控台/数据/渠道经营范围.json)，由[全渠道增长总控](../../00_总控台/全渠道增长总控.md)关联，不从插件支持列表反推经营事实。

| 经营链 | 当前范围 | 客户与下一步 |
| --- | --- | --- |
| 国外 | 国际站、B2B独立站、海外社媒（具体账号/发布状态仍查原入口） | 海外进口/批发/电商采购、品牌客户；选款→规格/数量→询盘→样品/报价讨论 |
| 国内 | 抖音已经开始；小红书、微信尚未开始，可准备内容和方法 | 消费者看场景、上脚、尺码；国内经销或品牌客户改用对应采购/开发问题 |
| 未来可选 | Amazon目前未开展 | 只保留扩展模板，默认清单和当前示例不把它列成经营渠道 |

当前经营、开始状态与工具连接是不同事实。抖音内容已开始不证明抖店开通、挂载或订单成交；小红书/微信的准备稿不记为已运营。国外/国内、客户类型、语言也分开：中文可以服务海外采购，微信也可以承接国内经销客户。

## 已实现的分类与协作

| 层 | 当前实现 | 它解决的问题 |
| --- | --- | --- |
| 平台与位置模板 | 国际站/独立站商品及内容、LinkedIn/Facebook图文与视频、TikTok短视频、抖音内容与可选抖店准备、小红书笔记/商品准备、微信朋友圈/公众号/视频号准备 | 当前/未开始/未来从业务源读取；模板不证明账号或电商执行能力 |
| 客户分流 | 个人消费者、国内经销/商家、海外采购、品牌开发；各有需求、语气、CTA及编辑排序偏好 | 同一渠道可切客户，消费者不套批发信息，采购不只讲生活情绪 |
| 商业模式与目标 | B2B、零售、内容；发现、考虑、购买、询盘、品牌、留存；每个目标单独指定市场、语言、受众 | 不把MOQ放进零售卖点，不用播放量代替有效商机 |
| 品类 | 鞋、服装、美妆、家居、电子、食品饮料、配饰、通用，共8种提问视角 | 品类只帮助提出问题，不自动生成材料、性能或实物事实；贝强真实资料仍主要是鞋类 |
| 呈现方式 | 生活故事、问题演示、身体/手部试用、选择指南、日常场景、搭配、细节、开箱、步骤、真实对比、测试证据、工厂过程，共12条路线 | 同款可有多个不同说服方式；用户选择优先，测试/对比/工厂方向缺证时排除 |
| 任务与产物 | 共享身份→定位→平台独立分支→实验→审核；窄任务仍独立执行 | 平台分支分别留语言、位置、素材、指标和待核项，不能换标签冒充完成 |
| 变更与数据 | staged字段差异；版本/证据失效检查；跨渠道JSON切片；本地可读审核稿 | 缺基线明示未知，缺数据为null，不混算B2B询盘和零售订单 |

推荐排序是编辑启发式，不是销售预测。8类/12条路线是可扩展配置，具体产品能否使用，要读其事实、素材、场景与当前目标。外部内容只作资料，不能改变工具规则。

[开源参考与实现依据](开源参考与实现依据.md)记录Anthropic commerce-agents、SuperCMO、Shopify的锁定版本、实际阅读范围、许可、采用设计及官方文档缺口。代码独立实现，没有移植整个Claude运行时。REA的[原仓库](https://github.com/morluto/rea)与[官网](https://rea.tools/)已核，属于研发分析工具；未指定调查目标，没有安装或执行逆向。

## 可以直接审核的真实商品示例

[BQ028当前渠道与客户审核示例](beiqiang-commerce/examples/BQ028跨平台审核示例.md)按国外和国内分组：国际站商品页、B2B网站承接、海外TikTok采购内容；抖音消费者短片；未开始的小红书图文和微信朋友圈准备稿。Amazon输出已移除。

海外内容询问真实型号、市场、规格配比、数量与样品目的；国内内容帮助看上脚、选择尺码与场景。微信另给消费者与经销客户的不同回应。抖音保留已认可28秒七场八句柯基故事，其它方向不覆盖原片；原画布和生成未改动。

[请求](beiqiang-commerce/examples/bq028-campaign.request.json)与[宿主创作内容](beiqiang-commerce/examples/bq028-campaign.content.json)是可复核示例。运行下方脚本会登记这份固定示例的本地任务，不是自动编剧模型；重复执行恢复同一对象。其它商品由宿主创作自己的内容后提交产物，不能把此鞋例硬套所有品类。

```powershell
python -X utf8 '08_工具链/07_电商Agent/beiqiang-commerce/scripts/run_campaign_example.py'
```

实际示例已完成11个步骤，状态package_ready；[本地审核包](.state/exports/68817a78-801e-4bac-9854-c94ee74e4931/review-11.md)保留逐步证据。它代表草稿范围准备完成，未发布、未付费生成、没有广告数据。原影片局部反馈仍以用户观看为源，尚无代理独立完整成片QA。

## 工作流与使用

单项工作流：title、listing、video、operations、customer；单平台有数据和客户上下文的组合准备用commerce；多平台/同品多呈现用campaign。自然语言需求由宿主整理为请求，不要求用户先填一大份表。

必填workflow/goal/channel/language，除纯数据分析外选SKU。targets指定platform/placement/business_model/market/audience/goal_type/language，以及market_scope、customer_segment；creative可选数量、明确风格、声音形式、时长、是否露脸和复杂度。图文位置不会继承视频时长。视频现有项目优先沿用PROJECT，当前任务不自动换语言/模型/画幅。

[commerce Skill](beiqiang-commerce/skills/commerce/SKILL.md)按需路由到[平台方法](beiqiang-commerce/skills/commerce/references/platform-playbooks.md)、[视频导演](beiqiang-commerce/skills/commerce/references/video-director.md)、[运营方法](beiqiang-commerce/skills/commerce/references/operations-playbook.md)及[产物契约](beiqiang-commerce/skills/commerce/references/artifact-contracts.md)。21个工具可通过同一个[server.py](beiqiang-commerce/server.py)调用：

```powershell
python -X utf8 '08_工具链/07_电商Agent/beiqiang-commerce/server.py' --tools
python -X utf8 '08_工具链/07_电商Agent/beiqiang-commerce/server.py' --tool commerce_create --args-file '08_工具链/07_电商Agent/beiqiang-commerce/examples/bq028-campaign.request.json'
python -X utf8 -m unittest discover -s '08_工具链/07_电商Agent/beiqiang-commerce/tests' -v
```

commerce_catalog默认将future_option单列；include_future:true可查看未来模板。strategy返回每个目标的经营状态与客户路线；范围改变会使旧审核失效，不能自动沿旧清单重跑。

新增工具：commerce_catalog、commerce_strategy、commerce_stage_change、commerce_change、commerce_export、commerce_business_snapshot。身份/策略/指标步骤由后端执行，实际文案与判断由宿主完成后submit_artifact登记。相同key恢复任务；revision防覆盖；来源、策略或已登记产物变动后显示needs_refresh，须明确刷新和重审。

任务、草稿、回执和导出留本地`.state/`，包与校验记录放`.local/`，均被Git忽略。正式业务成果继续回相应入口；运行库不是事实主库。commerce_stage_change只保存具体字段前后差异，不执行提交；缺目标对象、schema、基线或适用授权的情况逐项显示。

## 连接状态与验收

| 能力 | 实际状态 |
| --- | --- |
| Alibaba、LibTV官方读取 | 已接既有官方客户端；v0.1.1曾完成BQ028 product.get和现有节点实际读取，原回执只留本地 |
| 当前与准备渠道的内容 | 已实现位置/客户策略、产物与审核契约，按业务范围显示当前、开始或未开始 |
| 社媒及国内渠道的插件执行 | 尚未接写入接口；各实际账号身份与历史发布仍读业务证据，不能把插件未连接写成账号不存在 |
| Amazon | 当前未经营；只保留未来准备模板，不主动接入 |
| 独立站 | 沿用现有B2B网站入口，源码/CMS执行走实际项目工作流；Shopify只作为可选Provider研究 |
| 平台写入、消息、广告、付费生成 | 插件没有这些执行接口；适用时走已有官方业务Skills和具体授权，再取正式回读/业务验收 |
| 验证 | 60项程序检查、BQ028按当前/准备渠道完整准备与可读导出；安装副本stdio启动、21工具发现和调用检查 |

新增检查覆盖当前/未来清单、真实范围读取、同渠道不同客户、语言与地域独立、微信位置和范围变更失效；原检查覆盖身份/别名、平台错绑、位置/商业模式/静态图文、品类与不同方向、缺证排除、窄上下文、产物覆盖、变更基线/重复恢复/失效、数据归因与未知值，以及原v0.1任务兼容。结构和合成测试不能证明所有品类的创作质量或经营效果。

## 安装、扩展与业务源

工作区已有`.agents/plugins/marketplace.json`和启用配置，插件名继续是beiqiang-commerce@beiqiang-workspace。源包更新后用官方`codex plugin add beiqiang-commerce@beiqiang-workspace --json`重新安装新版本，不编辑缓存。校验/打包用[verify_package.py](beiqiang-commerce/scripts/verify_package.py)；--online-schema查官方格式，--zip写源目录外的本地ZIP。已有会话未刷新工具时，可直接用CLI。

新增平台要分别补当前业务规则、账号/对象/类目schema、精确准备请求、提交/异步状态、正式回读及本地回写。新增品类要补真实商品资料和主张证据。共用任务、素材版本和反馈协议；不重复上传已有素材、不盲重跑待终态任务。

商品模块读[商品SOP](../../02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md)和[唯一台账](../../02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json)；内容模块读[视频入口](../../05_内容与视频/AGENTS.md)和[视频子模块](../02_视频工具/电商视频Agent/README.md)；运营读[增长总控](../../00_总控台/全渠道增长总控.md)；客户读[客户入口](../../04_客户开发/README.md)。既有身份、来源、事实、授权和验收规则按这些源执行。

下一条真实接入需要一个具体平台账号与业务对象，按上述接口逐项验证；当前开发不会冒用其它平台账号权限。后续评估看减少纠正、重复操作、失败返工及有效采购商机，不以配置数量或内容产量作为成功。
