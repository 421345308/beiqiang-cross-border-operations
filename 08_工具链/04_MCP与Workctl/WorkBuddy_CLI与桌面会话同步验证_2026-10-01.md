# WorkBuddy CLI 与桌面会话同步验证

2026-10-01。负责人要求通过CLI指挥、在WorkBuddy原生桌面看到会话。此记录区分已跑通执行与未跑通显示；不代表HR试单或整款验收完成。

## 当次实测

- 安装内置CLI版本2.147.0。当前help支持`--resume`、`--session-id`、`--input-format stream-json`及ACP；`ps --json`未发现可连接的桌面活动会话。
- 用现有桌面WBIPC认证代理进行两次无工具短文本测试，模型均明确`deepseek-v4.1-flash`，每次仅一次模型调用。业务返回success、is_error=false、回复`CLI_VISIBLE_PROBE_OK`。没有商品变更，也没有复制上游凭证。
- 第一测试仅设`WORKBUDDY_CONFIG_DIR`，CLI把记录保存在`.codebuddy/projects/c-Users-spq-Desktop-贝强/`。这解释了以往命令行输出不出现在桌面的一个实际原因。
- 第二测试同时设`CODEBUDDY_CONFIG_DIR=C:/Users/spq/.workbuddy`，CLI原生记录确实保存在`.workbuddy/projects/c-Users-spq-Desktop-贝强/`；但当次原生桌面任务列表快照没有登记该测试ID。**共用记录目录不等于已验证桌面显示。**
- 两次`/v2/chat/completions`均200；`/v3/config`仍400，不能说配置接口全正常。整个短文本测试成功，配置400未阻止本次模型回复。
- 现有HR桌面任务ID是`6bfc01b4-ffcc-4dfd-9d4a-cd5f740152bd`，标题“接手HR020-A试单环境取证与图文准备”。另一个`96ff64c4-...`是旧视频会话，不能误续。尚未对运行中的HR会话启动第二个CLI写入者。

## 结论与下一步

已验证可以通过CLI和DeepSeek Flash实际执行小任务；**CLI发消息后原生桌面自动显示的通路尚未验证通过**。继续只核当前公开/宿主提供的会话关联能力。不要修改任务数据库、拼造聊天记录或把另开CLI/WebUI称为原桌面会话。桌面不可观察时，保留这一未完成范围。

临时可复核证据：`99_临时区/WorkBuddy_CLI桌面会话验证_2026-10-01/`，首次`finished.json`与第二次`shared-config/finished.json`、各自原生CLI stream。模型执行与GUI显示须分开验收。

参考：本机内置CLI `--help` 为本次参数依据；[官方CLI参考](https://www.codebuddy.ai/docs/cli/cli-reference)描述会话恢复和ACP，但没有据此证明WorkBuddy原生任务自动登记。

## 原生 HR 会话恢复的第三次实测
在目标 idle 时，以正确 CODEBUDDY_CONFIG_DIR 和 --resume 恢复原生 HR 会话。一次 DeepSeek Flash 模型调用成功，原生 jsonl 出现 CLI_VISIBLE_PROBE_OK，桌面任务时间更新为刚刚。但切换其他任务再返回 HR 后，界面仍显示 10:24 的旧回复，未显示测试消息。因此只能确认命令行执行与记录恢复，不能声称桌面自动显示或实时流式同步。未修改任务数据库或伪造消息。证据位于临时目录 resume-native/。
为避免通信调查拖住业务，下一批 HR020 纠正指令已通过原有桌面 HR 会话实际发送，模型为 Deepseek-V4.1-Flash。桌面可见通路仍需另行解决，不以隐藏 CLI 替代用户要求。
