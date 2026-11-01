# 创作画布

React Flow (`@xyflow/react`, MIT) 独立前端，绑定已有 `creation:` 对象。原项目记录与素材仍是唯一来源；本模块保存布局、节点文字和连线，不生成媒体。

- `npm ci` / `npm run build`，服务将本地 `dist/` 映射至 `/creation-canvas/`。
- 打开 `/creation-canvas/index.html?object_id=creation%3A...`。
- `/api/desk/bootstrap` 提供 `csrf_token`，写请求沿用 `X-Workbench-Token`。
- GET `/api/desk/creation-canvas?object_id=...` 返回 `{canvas:{object_id,title,nodes,edges,version}}`。
- POST 同路径发送 `{object_id,nodes,edges,version}`。返回新版本；409保留当前修改，不自动覆盖。
- 节点采用 `{id,type:'creation',position:{x,y},data:{title,content,media_path}}`；text、asset类型亦可。
- 媒体只加载 `/api/media/resolve` 核准的本机URL。

测试：`npm test`。生产构建与主工作台项目页面集成已完成；实际文字节点编辑、保存及重新打开已验证。连线与拖动依靠React Flow及本地测试，尚需更多实际项目体验。

官方文档：https://reactflow.dev/learn/concepts/adding-interactivity

镜头组织：点击‘添加镜头’，填写用途、时长、画面动作、文案/声音、制作状态及本机素材路径；通过连线关联参考素材和镜头。新增镜头不替换已有节点。保存后随项目画布接续。‘导出分镜简报’下载当前画布快照（含未保存编辑），供人工审阅或交给Agent；这不是新的知识库，也不触发生成或付费调用。Agent既有项目读取能力仍以原项目资料为准。导出顺序采用画布节点顺序，连线单列，不推断时序。
验证：npm test（3项通过），npm run build。新增分镜交互尚待浏览器实际验收。
