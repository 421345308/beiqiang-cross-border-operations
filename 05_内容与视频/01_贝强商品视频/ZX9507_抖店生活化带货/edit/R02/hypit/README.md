# ZX9507 R02 · 免费准备工程

唯一创意入口是[项目PROJECT](../../../PROJECT.md)与[分镜预览](../参考改编预览.html)。本目录不代表已生成视频。

`whole.svml`声明同一条参考、两张真实商品图、完整改编方向；`whole.svrun`只要求一次15秒720p竖版带声输出。2026-10-19 Source实际检查通过；plan读出1个生成请求、0个输入问题，但因本次Endpoint未绑定，1项unresolved，退出码1。不能报成生成路线已就绪。检查摘要见[verification.json](../verification.json)。

素材通过assets目录的本地Junction复用原件，不复制另一套商品图片。assets、运行缓存、Profile与prepared绝对路径证据只留本地，不推送公共仓库。恢复检查时，在本机启动器后使用`check whole.svml --workspace <本目录> --asset-root <商品原件目录> --asset-root <参考原件目录>`；选项在命令后。不能据此执行Build。

## API与执行状态

Hypit的本地媒体分析、Source检查和Run计划本身不要求API Key。视频生成一定需要实际服务账户：本项目拟继续使用已选LibTV，由现有LibTV登录管理授权，不等于Hypit免费提供Seedance。若以后改选HypiHub或其它Provider，才另配对应账户/Key与报价。当前没有向任何新Provider登录或上传。

上方记录的是免费review工程当时的未绑定状态；本轮已在.local建立本条实际LibTV素材、草稿及782积分报价，仍无付费授权。公共空Runtime保留作review输入，不绑定旧R01。后续可在当前方案核定后，经现有正式准备工具接入实际LibTVProvider。源视频有人的腿部与手，但无独立人物身份参考；本轮未要求人物分类参数，既有LibTVProvider也未实现该分类接口。

本轮实际新增视频、图片、声音生成均为0；仅复用现有Whisper权重完成一段本地ASR。没有执行Build。输入检查与plan不能证明最终保真；生成后仍需逐段看鞋型、针织与底纹，并听实际声音。

## 当前实际接线与报价

负责人已认可R02方案并要求先报积分。10-19已使用本项目`.local/hypit`的私有执行工程接实际LibTV Endpoint，Source/plan真实通过，1个Provider请求、preflight ready；公共review Source/Run保留原件与相对素材表达，未写入账户节点。当前草稿为15秒720p竖版带声1条，1视频＋2实图；页面当前782积分、划线1564。素材、prompt与参数经页面后再次CLI回读一致，未提交生成，无本次授权文件。该更新取代上方“本次尚未建立绑定/报价”的当时状态；完整执行证据仅留.local。
