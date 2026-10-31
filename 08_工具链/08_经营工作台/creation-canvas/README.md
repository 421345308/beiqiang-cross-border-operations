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
