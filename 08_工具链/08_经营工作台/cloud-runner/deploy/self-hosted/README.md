# 原生执行器

配合网站 `self-hosted/deploy/`，独立 `beiqiang-runner` 非root账号。
2026-10-31已在已有VPS安装固定Codex CLI 0.166.0，非root可执行且真实私有挂载/0700写入验证通过。本机Chrome设备授权页返回`unsupported_country_region_territory`（服务器已取得设备码，服务器侧不可用的结论尚未成立），临时登录服务已停，runner保持inactive/OFF、后端manual_cloud；不绕过地域限制，不宣称真实登录或自动领取通过。以下保留安装命令供重建参考。安装固定 `@openai/codex@0.166.0` 到
`/opt/beiqiang-codex`（将`/opt/beiqiang/runtime/node/bin`加入本次安装PATH后运行
`npm install --prefix /opt/beiqiang-codex @openai/codex@0.166.0`，
CLI在 `node_modules/.bin`；创建 `/opt/beiqiang-codex/bin` 指向此目录的软链接）。
root安装时的umask077可能阻止服务账号遍历。安装后仅对专用
`/opt/beiqiang-codex`内真实目录设0755，对真实文件执行`chmod a+r`并保留原执行位；
不得递归修改其他`/opt`路径，也不要跟随包中的软链接到外部。
Node专用runtime祖先由prepare-host.sh明确设0755，并以两个服务账号实际执行`node --version`。
最后以`beiqiang-runner`及service相同PATH运行`codex --version`确认目录和可执行入口均可达。
不要复制桌面凭证；服务器正常ChatGPT设备登录。

将runner.py和preflight.py及其本地模块作为同一只读release置于
`/opt/beiqiang-runner/releases/<version>/`，`current`指向该release。
runner.env放`/etc/beiqiang/runner.env` root:root 0600。
安装本service，但先不enable/start。

`bash verify-mount.sh`在目标机实际创建独立systemd挂载空间，验证
通过同一preflight函数读取`/proc/self/mountinfo`精确挂载点、非root、0700归属及写入。此结果必须留部署证据；
同文件系统bind会被`os.path.ismount`漏判，因此不再只靠设备号检查。本机配置检查不算远端通过。宿主原有`/var/data`不改变；实际持久原件位于
`/var/lib/beiqiang/runner/{codex,state}`，不是软链接，不需要修改既有预检。

登录用相同namespace：

```sh
systemd-run --wait --pty --collect --unit=beiqiang-login \
  -p User=beiqiang-runner -p Group=beiqiang-runner \
  -p BindPaths=/var/lib/beiqiang/runner:/var/data \
  -p Environment=CODEX_HOME=/var/data/codex \
  -p Environment=PATH=/opt/beiqiang/runtime/node/bin:/usr/local/bin:/usr/bin:/bin \
  /opt/beiqiang-codex/bin/codex -c 'forced_login_method="chatgpt"' login --device-auth
```

固定官网HTTPS队列路径仍由EdgeOne转发至统一API，不能改成HTTP绕过预检。
先验证官网转发与API共享secret，再启动；服务启动先真实preflight。
停用只用`systemctl stop beiqiang-runner`；失败不自动重试、不清blocked.json。
凭证和state私有目录分别备份到受控加密介质，不能放业务附件备份或公开包。
