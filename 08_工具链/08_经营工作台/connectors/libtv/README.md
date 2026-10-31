# LibTV本机官方CLI适配

仅调用本机官方`libtv`可执行文件，Python标准库、shell=False、45秒超时，禁用LIBTV_DEBUG。
不提供任意命令、模型、--run、删除、绑定或账户切换。每次使用无绑定临时cwd，
画布/节点操作显式UUID及-p，创建画布必须明确workspace_id（0=根目录）。
正常登录沿官方CLI；不读取、打印或复制凭证。account使用只读account list，
避开会校准账户scope的account info；所有操作先确认可读取当前active账户，
避免CLI未登录时project list返回null/0造成假空。

## Python合同

`execute(operation, **kwargs)`，亦可注入`Adapter(runner=callable, executable=..., receipt_dir=...)`。
runner按subprocess.run签名注入，离线测试不调用真实CLI。

| operation | 参数 | data |
| --- | --- | --- |
| account | 无 | `{account:{name,account_type,status,credits}}` |
| workspaces | page=1,page_size=20 | `{workspaces:{items,total,page,page_size}}` |
| projects | workspace_id可省略,page=1,page_size=20 | `{projects:{items,total,page,page_size}}` |
| project | project_id UUID | `{project:{id,name,workspace_id,updated_at,official_url,nodes,edges}}` |
| nodes | project_id UUID | `{nodes:{project_id,items,total}}` |
| create-project / create_project | name,workspace_id必须明确 | `{project:同上}` |
| create-text-node / create_text_node | project_id,title,content,x=0,y=0 | `{project_id,node}` |

全部返回`{ok,operation,data,error,source}`；operation保留调用方字符串。
source为`{provider:'libtv-cli',request_id,receipt,read_only}`，request_id为本地追踪UUID。
失败error为`{code,message,retryable:false}`，data=null，不向网页暴露原始stderr。
AUTH_REQUIRED需官方正常登录；创建超时/缺ID必须回读，不自动重复写入。

列表item：workspace为`{id,name,updated_at,official_url}`；project另有workspace_id。
node为`{id,title,type,x,y,content}`；edge为`{id,source,target}`。ID统一字符串，
未知字段为null/空名。project CLI摘要本身没有画布名称；node list本身通常无位置或内容，
不能从摘要推断未返回的正文。credits未从官方account list取得则null，绝不显示假0。
updated_at保留CLI返回时间值（项目当前毫秒数，工作区当前时间字符串）。
CLI没有返回可核的官方画布URL，因此official_url当前为null，不拼造网址。
nodes额外以官方`libtv node NODE_ID -p PROJECT_UUID`只读查询最多10个文本节点正文，
补全content数组，返回text_content_complete说明文本正文是否全部覆盖；不运行节点。

创建动作必须由网页用户逐次确认后才调用；适配器不会自行触发确认或批量创建。
实际project create返回`{projectMeta:{uuid,name,...}}`，适配器解包projectMeta，
项目列表条目/摘要的顶层UUID同样支持；未知结构仍保留回执并拒绝虚报成功。
文本写`-u content=[JSON字符串]`，不是模型prompt；x/y放在父node命令上；没有--run。
创建成功原JSON回执去除凭证/邮箱等字段后保存在本目录受忽略的`.local/receipts/`，
网页仅返回相对receipt及ID，不返回原私密回执。原始错误stderr不落网页/回执。

## 验收范围（2026-10-31）

已读个人libtv-cli技能和现场CLI help。主会话官方正常网页登录后重新只读实测：
account当前账户正常、workspace 15条、project 17条；指定已有画布摘要37节点/28边，
node list同37节点。适配器五类只读操作重新通过；不代表所有列表已拉全（按分页返回）。
主办已从UI明确确认创建一张专属“贝强工作台连接验收（无生成）”画布。
首次返回嵌套projectMeta导致适配器报缺ID；已停止重试，按私有回执和根目录列表只读
确认实际仅一张、补真实schema回归并修复规范化。没有重复创建、付费生成或默认绑定变更。
随后主办从同一画布确认创建一个内部验收文本节点，实际API及页面回读1节点、正文一致；未使用--run，既有画布未修改。11项离线测试通过，涵盖真实projectMeta响应结构。

运行测试：`python -m unittest discover -s connectors/libtv -p test_adapter.py`（工作台目录）。
