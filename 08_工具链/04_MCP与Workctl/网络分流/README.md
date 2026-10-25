# 国内服务直连

2026-10-25：Clash Verge Rev 2.5.8 / Mihomo 1.19.32 已启用全局国内分流，源文件为 [china-direct.js](china-direct.js)。它安装在 Clash Verge 配置目录的 `profiles/Script.js`，不依赖当前订阅的名称或编号。切换订阅时由 Clash Verge 全局扩展重新应用；若另行编写订阅扩展覆盖 `rules` 或 DNS，需要重新核对最终配置。

路由采用三层：抖音、抖店、剪映、即梦、LibTV、阿里国际站与相关接口/素材明确直连；[MetaCubeX 国内域名规则库](https://github.com/MetaCubeX/meta-rules-dat) 每 86400 秒更新；`.cn`、`.中国`、`.中國` 及 `GEOIP,CN,DIRECT` 兜底。国内域名及直连出口使用阿里/腾讯加密 DNS。保留原有拒绝规则及海外路由。

相较逐个枚举网站，规则库能持续覆盖新增国内域名；它仍是维护中的分类数据，不能保证识别所有新域名、海外部署或跨国共享资源。不能用 `MATCH,DIRECT` 代替国内分流，否则未单独列出的海外服务也会直接连接。

验收：规则库已加载 110448 条；抖音、剪映、LibTV 页面及接口、阿里国际站均观察到 `DIRECT`；百度命中 `CN-Domains-Direct` 规则集；Google 仍走原代理。关闭 26 条上述国内服务遗留的代理连接后重新建立连接。页面 HEAD 返回 404/421 只作为网络连通探测，不作为产品功能验收。未修改账号语言或浏览器语言偏好；直连不会自动清除已保存的英文设置。

本机备份位于 Clash Verge 配置目录 `repair-backups/china-direct-20261025-212013/`；规则库缓存为 `RuleSet/cn-direct.mrs`。当次验证原件在 `99_临时区/国内网络直连_20261025/verification.json`。节点配置、凭证及运行时完整文件仅留本机，不提交公开仓库。

参考：[Mihomo 路由规则](https://wiki.metacubex.one/config/rules/)、[DNS 策略](https://wiki.metacubex.one/config/dns/)、[Clash Verge 全局扩展与优先级](https://www.clashverge.dev/guide/extend.html)。
