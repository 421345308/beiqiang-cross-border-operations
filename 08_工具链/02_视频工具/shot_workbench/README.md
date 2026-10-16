# 本地镜头拆解台

用于参考片与制作版的完整视频拆分、时间线对照、慢放循环和创作笔记。无云端推理、无模型权重、无媒体上传。媒体和笔记落在具体项目的`edit/shot-workbench/`，这里只保存可复用程序。

## 当前能力与实测

- 两片完整H264预览代理，保留原帧率与音轨，保存原件/代理SHA256；不改原片和成片。
- PySceneDetect 0.7.2自动画面切换候选，与已有工程剧情段落分开显示。候选既可能漏掉渐变，也可能把闪光识别为切镜，不能自动当作分镜真值。
- 双片同步播放、0.25/0.5/1倍速、逐帧定位、区间循环、单独选择音轨、局部时间偏移和声音幅度波形。
- 按段记录剧情目的、人物动机、行为回应、节奏留白、证据和修改假设；本机浏览器保存，JSON导出/导入且校验视频版本。
- 按自动切镜、已有剧情段落或自定义片段导出真正的带声MP4片段及时间映射。片段取自预览代理，非原片无损副本；导出边界按帧取整，声音边缘加最多30ms淡化。

2026-10-16：已用两部56秒24fps视频验证准备链路，原片检测到8段、制作版7段候选，工程17个剧情段落独立保留。浏览器已实测定位、24fps步进、半速双片循环、笔记刷新留存及JSON导出；HTTP Range返回206。已导出水中完整参考片段，ffprobe核得3.875011秒且含音轨。网页播放能力不代表助手获得了连续音画感知，工具验收不代表艺术验收。

## 安装与运行

依赖FFmpeg/ffprobe在PATH。隔离环境不放入Git，不修改全局Python：

```powershell
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -r requirements.lock.txt
& .venv/Scripts/python.exe build.py --reference '<原片.mp4>' --candidate '<制作版.mp4>' --shots '<工程镜头表.json>' --output '<项目/edit/shot-workbench>' --title '<作品名 · 镜头拆解台>'
python serve.py --directory '<项目/edit/shot-workbench>' --port 8796
```

打开`http://127.0.0.1:8796/`。服务只绑定本机；窗口或进程关闭后再次运行serve即可恢复，媒体不需重建。`--shots`可省略；镜头表结构为`{"shots":[{"start":0,"end":3,"meaning":"段落名"}]}`。准备器拒绝覆盖已有输出目录，新版本使用新目录。每段的“当前版偏移”以参考片时钟为基准；正数表示当前版向后取时。

```powershell
python export_clips.py --workbench '<项目/edit/shot-workbench>' --kind reference --mode auto --output '<项目/edit/参考切镜>'
python export_clips.py --workbench '<项目/edit/shot-workbench>' --kind candidate --mode chapters --index 13 --output '<项目/edit/片段样片>'
python export_clips.py --workbench '<项目/edit/shot-workbench>' --kind candidate --mode custom --notes '<导出的笔记.json>' --output '<项目/edit/自定义片段>'
```

`--index`从1开始，不传则导出全部。自定义模式使用笔记中的区间与对应偏移，校验两片SHA256。浏览器逐帧定位受解码/时间舍入影响；导出以帧取整的时间映射为准。浏览器存储可能被清理，重要笔记应导出到项目。

## 如何进入制作迭代

1. 先校正剧情段落和对应时间，再写每段希望观众感受到的变化。自动分割只提供导航。
2. 区分画面事实、用户反馈与解释；记录动作之前的动机、之后的回应，而不是只列物体和动作名称。
3. 每轮只选一两项有依据的修改假设，在既有Remotion/Blender工程中做短样片，回到同一段比较。
4. 若局部节奏/姿势能解决，沿用工程迭代；若剧情关系或角色表演结构需要改变，先做粗分镜/关键姿势样片再考虑重建。漂亮场景、更多动作和技术无错都不单独等于好作品。
5. 原片、旧版和新样片都保留明确版本；新素材重新运行准备器，不把旧笔记误套到不同视频上。

这不是完整的剪辑/骨骼动画软件，也不能从MP4还原原作者图层。本入口负责拆分、对照与片段导出；Remotion/Hypit仍负责合成，Blender等负责需要的角色动画。实际采用哪种制作方式，由短样片结果决定。
