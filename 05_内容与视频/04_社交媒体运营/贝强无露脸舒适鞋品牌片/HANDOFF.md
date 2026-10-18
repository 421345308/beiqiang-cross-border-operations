# 《柯基给主人买BQ028新鞋》接续入口

当前审核入口是 [PROJECT.md](PROJECT.md)。本页记录真实执行断点，2026-10-14更新。负责人已在画布自行生成1条28秒视频并反馈大致满意；代理没有新增付费生成授权。

## 已核实状态

- [同一LibTV画布](https://www.liblib.tv/canvas?projectId=428c67fed30b443f99611efb7d50e9ff)，UUID `428c67fed30b443f99611efb7d50e9ff`；整条草稿节点 `5cd0d215-f745-4974-a0fd-dbd453a5956d`。
- 官方CLI 1.1.3核当前20个节点、13条入边，13张参考的节点身份、URL与本地文件哈希一致。没有重新上传素材。
- 当前 `image2video`，Seedance 2.5、28秒、9:16、720P、声音开启、count1、autoCompliance1；完整提示保持Node身份绑定，已保存并正式回读。
- 旧S01 `7efef89d-8148-4f33-8387-f876e96194b6` 和旧S04 `9f40aef7-dd64-4397-a4ad-e098b7c9198b` 经核无连线、无任务、不在当前图片输入或提示中，已删除。删除回执及原正式上传证据仍保留。
- 本地 [最终提示稿](generation/workflow/seedance-prompt.md)、[镜头表](generation/shots/shots.json)与PROJECT已按实际图片顺序同步；故事仍按S01—S07展开。

实际图片编号：1 OWNER_BODY、2 OWNER_FACE、3 DOG_BODY、4 BQ028、5 OLD_SHOES、6 TABLET、7 S02、8 S03、9 S05、10 S06、11 S07、12修订S01、13修订S04。精确编号/nodeKey/文件/哈希以 [canvas-state.json](generation/platform/canvas-state.json) 为准，不从历史数组推断，不为排序反复拆边。

## 尚未完成，不伪称画布全部收尾

1. **已有节点位置**：修订S01 `8ff6aed1-5c08-4999-90e2-2a4089910237` 仍在(4300,120)，目标(1450,120)；修订S04 `4994dbf2-29e4-42df-a8e7-b2b635b2ac88` 仍在(4300,970)，目标(2830,120)。已核官方最新发布仍为1.1.3；help只支持新建节点坐标，没有已有节点移动命令。未以查询或`data.position`伪造移动，没有为布局重复上传/新建节点。
2. **非当前模式缓存**：`params.mixedList`仍带旧图ID，当前`imageList`、图片顺序、实时连线和完整Node提示均是选定13图。CLI拒绝直接`--set mixedList`，正常模式切换/连线重算也未刷新该缓存；已恢复并核实`image2video`。不能宣称缓存已修复，不盲目重跑同样脚本或改走原始HTTP；正式付费执行前须通过官方支持路径再次核定最终输入。

3. **素材节点标题**：官方CLI对资源节点执行`--name`也报`params.model不能为空`，未为改名伪设模型；七张图旧名称暂留，当前用途看已更新的剧情说明和完整Node提示。精确失败/目标名称在canvas-state。

状态区分`draft_content_verified=true`与`canvas_configured=false`。正式证据：[画布回读](generation/platform/428c67fed30b443f99611efb7d50e9ff/project-readback.json)、[草稿回读](generation/platform/428c67fed30b443f99611efb7d50e9ff/draft-readback.json)、[实际节点绑定提示](generation/platform/428c67fed30b443f99611efb7d50e9ff/submitted-prompt.txt)。

## 创作与授权基线

保留七场八句、13张参考和旧鞋→白袜→新鞋状态。负责人2026-10-14最新确认替代费用包袱与狗必须继续走的旧要求：开头先走到脚不舒服再坐，狗看旧鞋后想到换鞋，女生试穿后真正遛了一阵，结尾主人想继续、狗低头想歇。唯一末句是“走不动了……让我歇会儿。”狗仍只有自然动作、轻叫和内心独白；女生停下等狗。S06保留运动中鞋侧面及完整落地—承重—抬脚。

已同意的字标包装为米白纸盒、深绿“贝强 / BEIQIANG”、白色内衬纸概念；单独盒子图只备改图，不接成第14图。产品外观以真实BQ028图为准，不新增材料/性能/医疗承诺。不要恢复现场说话狗或14图中间稿。

当前28秒安排给先走再坐、试穿4秒、真实散步6秒和结尾位置交换留时间。S01/S05/S07静帧只作空间/身份/鞋状态参考，不锁新动作或狗的旧期待神态。新表演已有用户生成，当前对白预算仍未经独立正式声音核验；旧读稿失效。本批报价和付费范围仍未核，旧报价/其它项目授权不适用。

下一步：保留用户已大致满意的基线；脚痛表演、自然散步和鞋盒几何写为下次候选检视项，原因未核。电商视频agent方案另见工具入口。任何新增生成仍须当次付费范围确认；当前不重生成、不发布。

## 环境与同步

工作区 `C:/Users/spq/Desktop/贝强`。画布操作只用 `C:/Users/spq/.libtv/libtv.exe` 与当前help，不造HTTP、不换Provider。子进程代理 `http://127.0.0.1:7892`，不改系统代理或关闭TLS。Python `C:/ProgramData/anaconda3/python.exe -X utf8`。

本次CLI只读核验用户生成记录，没有代理视频生成；过时临时草稿和失败同步脚本不作为当前源。共享工作分支为`codex/workspace-consolidation`；本项目文本继续同步到受信origin的`codex/dog-shoe-character-assets`，用独立索引保护其他任务工作。公开同步仅提交创作文稿与非敏感结构检查；平台回执/资源元数据保留本地，不因权限配置变化绕过此前公开推送拒绝。素材原件及正式回执保留。
