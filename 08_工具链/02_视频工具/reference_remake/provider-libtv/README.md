# Hypit 原生 LibTV Provider

版本0.1.0，针对本机已验证的 Hypit0.1.8 / LibTV CLI1.1.3。使用 Hypit 公共 Endpoint/Runtime SDK，不修改上游、重建私有HTTP接口或添加后台调度器。普通JavaScript包通过 `hypit.activation` 加载；Profile将 `@hypit/seedance@1#seedance-2.5` 绑定到本包。

## 已打通的责任链

Source声明完整视频、1–2张商品图片、提示词与明确4–30秒参数 → Run要求一次整片输出 → Runtime选择LibTV Endpoint → 校验实际素材bytes/hash与已审适配包 → 核对草稿输入/顺序/提示词/参数 → 官方CLI同步提交一次 → 官方CLI下载 → 核视频流、时长、画幅、分辨率及要求的音轨 → `context.resources.put` → 模型声明的 `GeneratedVideoSet` → Hypit的主视频输出。

仅支持本路线实际准备的全能参考 `mixed2video`。文本生成、首尾帧、额外音频引用、人物分类、联网搜索、自动时长和多输出批量未实现，明确拒绝，不暗中换模型或入口。平台限制收紧时需重核当前schema；支持函数不保证模型成功率。

## 项目初始化与检查

先使用上级 `prepare.py` 与 `Stage-LibTV.ps1` 准备/绑定真实输入，上传回执按hash复用。再执行：

```powershell
./Initialize-NativeProvider.ps1 -Prepared <prepared.json> -Workspace <本项目Hypit目录> -EvidenceDirectory <同一LibTV证据目录> -FFprobe <已安装ffprobe>
./Check-NativeProvider.ps1 -Workspace <本项目Hypit目录>
```

脚本位于本目录的上一级。初始化创建普通项目包、Source/Run/Profile与指向已知原件目录的Junction，不复制原视频、不下载依赖、不更改全局账号。相对素材路径必须以 `./` 开头，检查只准入实际引用的原件目录；不以全盘作为素材根。当前Windows运输要求LibTV原生可执行文件，拒绝需要shell展开的cmd/bat/ps1包装。

Profile中的prepared/evidence/executable/ffprobe使用本机绝对路径，**项目初始化时不配置authorization**。Hypit的 `plan: Preflight ready` 只证明图与端点可选，不意味着付费提交就绪、最新价格已核或审美验收通过。现有CLI准备路径仍保留，供非Hypit项目与故障定位使用。

## 费用、一次提交与恢复

CLI 1.1.3的新草稿可能按图片→视频推导mixedListOrder，而不是调用方添加入边的顺序。准备时记录实际顺序，要求每个预期素材恰好出现一次；Provider冻结这一顺序，并分别检查imageList/videoList顺序与提示词的节点身份。不得用不可写的mixedListOrder/mixedList字段强改排序。新稿若未持久化派生mixedList，只能依据完整的类型列表与已冻结顺序检查；如果该字段存在，空缓存、旧素材或顺序不符都拒绝。页面正常打开可能重算缓存，完成后需CLI回读，不能只为通过测试标记就绪。

联网搜索必须显式关闭，Provider检查advancedSettings.search_enabled=0，避免Hypit no-webSearch声明与平台默认开启冲突。参考编码也须实测可播放：遇到HEVC兼容问题，另保留全帧、同时间线、原音轨的H264输入及原件关系/hash，不把转码当裁片。CLI与网页富文本引用周围的空格须在审核原文中对齐，不放宽正文校验。

CLI没有数值报价，Provider只公开价格来源页面，不推算积分或人民币。真正执行前需要当前平台报价、实际可见素材确认及负责人当次付费范围。准备工具的 `stage-state.json` 默认保持generation_ready=false；完成真实核验后才能更新为true，不能仅为跑通代码改状态。

配置中的authorization指向本项目私有确认文件，格式为 `libtv-paid-authorization-v1`：confirmed_by_user=true、原文confirmation、prepared_sha256、stage_sha256、draft_sha256、project_uuid、draft_node_id、count=1、max_submissions=1、expires_at；quote需source=libtv_current_page、实际credits与checked_at，报价距执行不超过24小时。输入/草稿指纹不同、缺授权、过期、缓存不同、旧结果已存在均拒绝执行。授权记录不能由模型自行猜测或补写。

同步CLI的 `--run` 没有外部timeout、后台运行、自建轮询或自动重试。提交前写入持久operation记录并用独占文件锁避免重复；故障、异常退出或状态不明均阻止第二次付费提交。崩溃遗留锁/未知状态必须先核平台实际任务，不能删除记录来重试。CLI终止后只回读一次节点，结果不完整就停止。

确认远端完成后，下载失败可以继续收集同一输出；收集完成后只复用相同请求记录下、hash未改变的素材，不重新生成。这里是同一次已确认提交的恢复，不是“重复Build就获得新的生成授权”。编辑版复用在Run中显式选已接受文件/Build Output；接受与否另由完整观看、听审决定。

CLI的download当前返回本地路径而非JSON。已实测它可能在水印服务504后仍返回exit0与文件，必须核实际文件与音视频流，不能凭退出码宣称输出成功。下载路径只准入自己的输出目录，不添加会员、去水印或其他计费选项。凭证继续由LibTV管理，Provider配置不保存token。

## 验证状态

2026-10-12：真实28.467秒完整AV参考＋两张BQ029原图的Source检查通过；Run实际加载本包，恰好一个28秒、720P、9:16、带声请求，Provider指向libtv.reference。没有Build、收费提交或后台Worker。

`test.mjs`使用真实Hypit SDK、模拟LibTV运输验证：接口不支持的请求/素材hash错、独占锁、缺授权/授权指纹错/过期、旧商品缓存、提交失败不重试、下载失败续收、结果类型与已收集文件篡改。它不是模型生成测试，模拟MP4内容不能作为成片展示。公开参考经官方CLI下载后实测28.466667秒、960×720、有音轨，4,098,491bytes且SHA与同源上传视频一致；临时下载副本已删除。这验证下载运输，不是新片生成成功。

2026-10-13：另一17秒整片包经Source/plan与实时Provider草稿检查通过；实际图片→视频派生顺序及缓存一致，联网搜索关闭，网页兼容参考已加载、数值报价已核，仍无授权配置或生成提交。测试新增派生排序、顺序变化、空缓存、重复素材及联网参数检查。上述检查是准备与调度证据，不能证明模型生成效果或完整声画理解。

**尚未验证：** 真正付费一次后的平台终态/成片下载与Hypit Build完整闭环。旧28秒草稿的缓存/报价待核状态与新17秒草稿分开保存。因此这是已接入并通过不付费验证的原生Provider，不是已经验收的新视频，也不是完整音视频理解或审美模型。

账号ID、上传URL、确认文件、operation记录、Profile、本机路径和媒体留项目本地；公共工具仓库只放通用代码与说明。只启动短时CLI进程，不加载本地模型，不安装剪辑器或新建预览网站。
