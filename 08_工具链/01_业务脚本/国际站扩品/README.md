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

搜鞋网官方“数据下载”按钮需要登录。当前脚本从公开详情页重建标题、颜色、尺码、上架时间和完整详情图，不读取账号凭证。

## 生成联系表

`make_candidate_contact_sheets.ps1` 读取 JPG/PNG 审计预览并生成每页 12 张联系表。WebP 原图先转为 JPG 预览，原图不改。

## 每次运行后

1. 更新 `国际站合规扩品工程总控.md`。
2. 更新 `扩品批次台账.csv` 的唯一下一动作。
3. 不把“货号缺口”直接当成“可建链接数量”。
4. 不自动发布；草稿创建、提交和上线都要分别记录。
