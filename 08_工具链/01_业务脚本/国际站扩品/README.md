# 国际站扩品工具

用途：把搜鞋网贝强工厂店公开商品目录同步为本地清单，下载候选素材，并生成视觉审计联系表。

## 目录同步

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync_sooxie_catalog.ps1 -Mode Inventory
```

输出：

- `02_Alibaba运营/05_扩品工程/数据/搜鞋网贝强工厂店在线商品_2026-08-14.csv`
- `02_Alibaba运营/05_扩品工程/数据/搜鞋网待去重候选_2026-08-14.csv`

## 下载候选主图

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync_sooxie_catalog.ps1 -Mode CandidateCovers
```

候选主图用于视觉去重，不代表可上架。

## 下载选定数据包

```powershell
& .\sync_sooxie_catalog.ps1 -Mode SelectedPackages -SelectedArtno @('ZX2212','T5503')
```

特点：

- 图片最多 4 路并发。
- 已存在文件自动跳过，可中断续跑。
- CDN 返回 WebP 时按真实格式保存。
- 每款保留 `source.json` 和原图文件夹。

大批量续跑经验：一次下载 48 包可能超出单次命令时限，应按 5-8 款小批运行。脚本会跳过已存在文件，不会重新下载完成包。Xiecdn 图片 URL 必须去掉 `!` 后的转码后缀，并携带来源 Referer；当前脚本已内置主/备 URL 和 3 次重试。

搜鞋网官方“数据下载”按钮需要登录。当前脚本从公开详情页重建标题、颜色、尺码、上架时间和完整详情图，不读取账号凭证。

## 生成联系表

`make_candidate_contact_sheets.ps1` 读取 JPG/PNG 审计预览并生成每页 12 张联系表。WebP 原图先转为 JPG 预览，原图不改。

## 生成预上架包

先完成重复/IP/产品事实审计，然后编辑配置正本：

```text
sooxie_prelisting_profiles_2026-08-14.json
```

执行：

```powershell
python .\build_sooxie_prelisting_batch.py --workspace C:\Users\spq\Desktop\贝强
```

脚本会：

- 从每款 `source.json` 直接读取尺码。
- 按配置生成 6 张主图、6 张英文详情图和逐颜色 SKU 图。
- 校验公开标题/关键词禁用宣称、图片数量、像素尺寸和颜色映射。
- 写出总表、单品填写表和主图/详情/颜色总览，用于人工视觉验收。

生成程序不调用生成式 AI，不改变鞋型、配色和结构。源图存在中文或第三方标识时，必须通过选图/合规裁切或转入隔离，不使用 AI 抹除风险元素。

## 每次运行后

1. 更新 `国际站合规扩品工程总控.md`。
2. 更新 `扩品批次台账.csv` 的唯一下一动作。
3. 不把“货号缺口”直接当成“可建链接数量”。
4. 不自动发布；草稿创建、提交和上线都要分别记录。
