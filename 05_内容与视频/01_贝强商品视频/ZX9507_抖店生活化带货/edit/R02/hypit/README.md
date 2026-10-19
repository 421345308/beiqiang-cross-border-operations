# ZX9507 R02 · 免费准备工程

唯一创意入口是[项目PROJECT](../../../PROJECT.md)与[分镜预览](../参考改编预览.html)。本目录不代表已生成视频。

`whole.svml`声明同一条参考、两张真实商品图、完整改编方向；`whole.svrun`只要求一次15秒720p竖版带声输出。2026-10-19 Source实际检查通过；plan读出1个生成请求、0个输入问题，但因本次Endpoint未绑定，1项unresolved，退出码1。不能报成生成路线已就绪。检查摘要见[verification.json](../verification.json)。

素材通过assets目录的本地Junction复用原件，不复制另一套商品图片。assets、运行缓存、Profile与prepared绝对路径证据只留本地，不推送公共仓库。恢复检查时，在本机启动器后使用`check whole.svml --workspace <本目录> --asset-root <商品原件目录> --asset-root <参考原件目录>`；选项在命令后。不能据此执行Build。

## API与执行状态

Hypit的本地媒体分析、Source检查和Run计划本身不要求API Key。视频生成一定需要实际服务账户：本项目拟继续使用已选LibTV，由现有LibTV登录管理授权，不等于Hypit免费提供Seedance。若以后改选HypiHub或其它Provider，才另配对应账户/Key与报价。当前没有向任何新Provider登录或上传。

R02尚未建立实际LibTV素材节点、草稿、当前报价或付费授权；空Runtime仅用于显示真实未就绪项，不虚构平台对象或绑定旧R01。后续可在当前方案核定后，经现有正式准备工具接入实际LibTVProvider。源视频有人的腿部与手，但无独立人物身份参考；本轮未要求人物分类参数，既有LibTVProvider也未实现该分类接口。

本轮实际新增视频、图片、声音生成均为0；仅复用现有Whisper权重完成一段本地ASR。没有执行Build。输入检查与plan不能证明最终保真；生成后仍需逐段看鞋型、针织与底纹，并听实际声音。
