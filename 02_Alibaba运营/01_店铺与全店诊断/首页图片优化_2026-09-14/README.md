# Alibaba 旺铺首页厂房图片优化记录

日期：2026-09-14

用途：当前未发布旺铺首页的厂房外观、生产现场与工序证明模块。

## 成品与来源

| 成品 | 来源图 | 建议角色 | 处理说明 |
| --- | --- | --- | --- |
| `01_factory_exterior_web_v1.png` | 独立站 `factory-video-stills/factory-exterior.webp` | 首页首屏 / 工厂介绍 | 保留真实建筑主体与规模，校正透视、曝光和色温，清理画面并移除原视频的平台角标。 |
| `02_workshop_active_web_v1.png` | 独立站 `factory-web/workshop-area.webp` | 生产能力主图 | 保留原车间结构、设备类型和产品场景，整理杂乱区域，并按负责人授权适度补充工作人员。该图只作视觉展示，不作为现场人数、设备数量或产能证据。 |
| `03_stitching_process_web_v1.png` | 独立站 `factory-video-stills/stitching-line.webp` | 工序近景 | 保留原人员、缝纫设备和动作，优化曝光、色温与清晰度，移除原视频的平台角标。 |

## 使用边界

- 三张图均为真实厂房素材的网页视觉优化版本，不得用于证明具体在岗人数、设备总量、自动化程度或固定产能。
- 不将优化后的车间整洁度解释为审厂结论、认证或现场实时状态。
- 对外文案中的厂房面积、年产量、成立年份及履约能力继续按负责人已确认事实使用，但图片本身不单独承担这些数字的证据。
- 发布到 Alibaba 图片银行后，页面只能引用本店正式 Alibaba CDN 地址；不得引用本地路径或 Accio 临时地址。

## 生成方式

使用 Codex 内置图像编辑模式。外观图与工序图采用受控修图；车间图采用受控修图并按负责人授权增加少量工作人员。所有成品单独保存，未覆盖独立站原图。

## Alibaba 图片银行与旺铺接入

| 图片 | fileId | 正式 CDN | API 回执 |
| --- | ---: | --- | --- |
| 厂房外观 | `33492780323` | `https://sc04.alicdn.com/kf/Ha5217d67c8e34e249665622b4ebd6d5fp/286385890/Ha5217d67c8e34e249665622b4ebd6d5fp.png` | requestId `213f5a2117893956464152991`；traceId `2103346a17893956432843030e0b3f` |
| 车间全景 | `33492852091` | `https://sc04.alicdn.com/kf/H0e89259ce96443359ca237ba009b9744b/286385890/H0e89259ce96443359ca237ba009b9744b.png` | requestId `0bbb3b2417893956615828094`；traceId `2103245817893956572538830e10ec` |
| 工序近景 | `33489516737` | `https://sc04.alicdn.com/kf/Hf74feec711c74932a3c6ca6388e80e92u/286385890/Hf74feec711c74932a3c6ca6388e80e92u.png` | requestId `21501be117893956749226710`；traceId `210334ab17893956717911996e0d5d` |

接入位置：厂房外观用于首屏右侧主图；车间全景用于 `Reliable Production Capacity` 主视觉；工序近景用于 `Advanced Production Lines`。首屏图框从 1:1 调整为 4:3 并左对齐裁切，保证 PC 与移动端均保留完整建筑主体。2026-09-14 已完成构建、PC/移动端加载与目视检查；页面仍为未发布副本，未触发线上发布。

## V2 重构（负责人复审后）

第一版页面中 `Strict Quality Control Process` 使用了一张与贝强实际场景不符的陌生工厂图，现明确排除，不再用于旺铺。V2 仅以负责人本次提供的四张贝强实拍为场景依据，保留真实绿色设备、建筑结构、物料形态及原有工作人员；主要处理画面杂乱、光线、构图和网页展示比例。新增人员不作为实际人数、产能或审厂证据。

| V2 图片 | 页面角色 | fileId | 正式 CDN | API 回执 |
| --- | --- | ---: | --- | --- |
| `bq_factory_v2_quality.png` | `Strict Quality Control Process`，替换错误陌生工厂图 | `33492972380` | `https://sc04.alicdn.com/kf/H97758b313a3e417bb69c643fb3a0ee0cG/286385890/H97758b313a3e417bb69c643fb3a0ee0cG.png` | requestId `212cbf3217893968517244953`；traceId `210334ab17893968483824177e0e86` |
| `bq_factory_v2_capacity.png` | `Reliable Production Capacity` 主视觉 | `33489636632` | `https://sc04.alicdn.com/kf/H6f102436c8a54c96a90a08dc7cdc0d20R/286385890/H6f102436c8a54c96a90a08dc7cdc0d20R.png` | requestId `0bab02fe17893968816015370`；traceId `2103346a17893968782827755e0d6d` |
| `bq_factory_v2_storage.png` | 物料与鞋面部件仓储场景 | `33492061930` | `https://sc04.alicdn.com/kf/H9d305621c7884a94ae57f30ddee481bfl/286385890/H9d305621c7884a94ae57f30ddee481bfl.png` | requestId `213f5a2117893968951975079`；traceId `210334ab17893968920145173e0d7e` |
| `bq_factory_v2_staging.png` | 订单备料与周转场景 | `33492025993` | `https://sc04.alicdn.com/kf/Hfca0c6eb1dde42f79b0d7b9b352cbadb9/286385890/Hfca0c6eb1dde42f79b0d7b9b352cbadb9.png` | requestId `210829b717893969087331800`；traceId `2103245817893969054578057e0e18` |

V2 四张图片单独保存，没有覆盖实拍原件或 V1 成品。厂房外观与工序近景不在本次错误图片范围内，继续沿用已有版本，避免页面出现重复场景。

## V3 模板占位图清理

负责人要求继续清理 OEM、合作伙伴与底部询盘模块中的模板占位图。本轮以已有真实厂房素材为基础：三个大面积背景分别复用已优化的产线、订单备料和厂房外观图；两个内容展示位使用独立站工厂视频中的真实装盒与成鞋检查帧重新修图，去除视频角标和桌面杂物，不改变鞋款、人员动作或现场身份。

| V3 图片 | 建议角色 | fileId | 正式 CDN | API 回执 |
| --- | --- | ---: | --- | --- |
| `bq_factory_v3_packing.png` | OEM/ODM 或供应链装盒近景 | `33493128348` | `https://sc04.alicdn.com/kf/H320e4a556fbb465c9f39b0dba4e25484e/286385890/H320e4a556fbb465c9f39b0dba4e25484e.png` | requestId `212cbf3217893978808498374`；traceId `2101d13c17893978776422574e0efb` |
| `bq_factory_v3_inspection.png` | 合作伙伴或底部询盘模块的成鞋检查近景 | `33493152314` | `https://sc04.alicdn.com/kf/H7670140696a24e3db4a8365e7d566891n/286385890/H7670140696a24e3db4a8365e7d566891n.png` | requestId `213d4e4917893978949142114`；traceId `2101d86517893978914554204e0c47` |

V3 使用边界与前述版本一致：画面只证明存在相应真实场景与动作，不单独证明固定工序、检验标准、包装规格、人员数量或交付能力。

负责人复审认为 V3 两张近景仍有明显视频截帧感、专业度不足，因此不接入最终预览；文件与上传回执仅保留追溯，不作为页面正式素材。

## V4 专业工位重构

根据负责人允许适度生成人员与工位的要求，以贝强真实绿色设备、红色消防管线、厂房采光、黑色针织鞋和青绿色鞋盒为视觉约束，重构为统一工作服的包装工位与人工终检工位。两图属于基于真实素材的网页场景重构，不作为真实人员数量、现场实时状态、检测项目或固定流程证据。

| V4 图片 | 页面角色 | fileId | 正式 CDN | API 回执 |
| --- | --- | ---: | --- | --- |
| `bq_factory_v4_packing_team.png` | 专业装盒与订单准备工位 | `33489865097` | `https://sc04.alicdn.com/kf/H22593e04fb6d450397fcfc8cda669dd8k/286385890/H22593e04fb6d450397fcfc8cda669dd8k.png` | requestId `213f5a2117893985124977484`；traceId `210329c717893985093238582e0dcb` |
| `bq_factory_v4_final_inspection.png` | 成鞋人工终检工位 | `33492229993` | `https://sc04.alicdn.com/kf/H20fa9c2152514aabb118c762ac0207bcp/286385890/H20fa9c2152514aabb118c762ac0207bcp.png` | requestId `0bbb637a17893985281697896`；traceId `2103135017893985249406863e0d87` |

负责人随后指出统一深蓝工服与其它实拍员工着装不一致、容易产生摆拍感，因此 V4 不作为最终页面版本。

## V5 自然着装修正版

仅调整 V4 前景员工服装：包装工位改为浅灰 T 恤与深灰黑 Polo，终检工位改为深灰普通 T 恤；背景员工继续保留白色日常工作服。人物、动作、鞋款、设备、建筑结构和构图保持不变，避免形成不存在的统一制服印象。

| V5 图片 | 页面角色 | fileId | 正式 CDN | API 回执 |
| --- | --- | ---: | --- | --- |
| `bq_factory_v5_packing_natural.png` | 自然着装的专业装盒工位 | `33493344199` | `https://sc04.alicdn.com/kf/H47a32d0cc7e7469eac86316515c02e0fd/286385890/H47a32d0cc7e7469eac86316515c02e0fd.png` | requestId `0bbb637a17893987870324243`；traceId `2103346a17893987839314076e0bff` |
| `bq_factory_v5_inspection_natural.png` | 自然着装的成鞋人工终检工位 | `33489816584` | `https://sc04.alicdn.com/kf/H4df7d8df833444b0889a4e21a1d14660C/286385890/H4df7d8df833444b0889a4e21a1d14660C.png` | requestId `213d4e4917893988018554907`；traceId `210325bb17893987976233101e7c85` |

## V6 全页漏项修复

全页场景图审计确认，除已清理的模板图外，仍有四张原始竖图被固定比例容器重度裁切，并存在倾斜、杂乱、过曝或场景体量丢失问题。V6 以负责人提供的贝强实拍为环境依据，统一校正为 16:9 网页构图；保留绿色设备、红色消防管线、实际建筑尺度与鞋类生产场景，人员使用白、灰、黑等不同日常工作服，不形成不存在的统一制服印象。

| V6 图片 | 页面角色 | fileId | 正式 CDN | API 回执 |
| --- | --- | ---: | --- | --- |
| `11_workshop_overview_web_v6.png` | OEM/ODM 模块右侧厂房/车间展示图 | `33489960763` | `https://sc04.alicdn.com/kf/H30daef88e74f405785923e6110ff045at/286385890/H30daef88e74f405785923e6110ff045at.png` | requestId `21501b8d17894002980313866`；traceId `210334ab17894002947715256e0b2a` |
| `12_manual_quality_station_web_v6.png` | Factory Overview 人工质量检查场景 | `33493512372` | `https://sc04.alicdn.com/kf/Hb88e4e21abf547a4906128a7021307a1q/286385890/Hb88e4e21abf547a4906128a7021307a1q.png` | requestId `21546a1d17894003095747863`；traceId `2103135017894003065066766e0f35` |
| `13_material_storage_web_v6.png` | Factory Overview OEM/ODM 材料仓储场景 | `33493500330` | `https://sc04.alicdn.com/kf/H59ffefffdf404de78f910a9219ae69e4S/286385890/H59ffefffdf404de78f910a9219ae69e4S.png` | requestId `212c6fc617894003489404024`；traceId `210334ab17894003453723992e0d9f` |
| `14_order_staging_web_v6.png` | 独立的订单备料/履约背景 | `33489984709` | `https://sc04.alicdn.com/kf/Heaed1f313c5b46b8b3b103bd4aa2c46eY/286385890/Heaed1f313c5b46b8b3b103bd4aa2c46eY.png` | requestId `212c41d317894003608356390`；traceId `2103346417894003572412861eb283` |
| `15_craftsmanship_station_web_v6.png` | Factory Overview 第一张质量与舒适工艺场景 | `33492553575` | `https://sc04.alicdn.com/kf/H15f1c6d4227e49b7a4deba6fd82a204an/286385890/H15f1c6d4227e49b7a4deba6fd82a204an.png` | requestId `210829b717894004607544411`；traceId `210334ab17894004576582046e0ee9` |

V6 图片是基于真实环境的网页视觉重构，不单独证明实时人数、设备数量、库存、固定工序或履约能力。原始实拍文件继续保留作来源追溯，页面不得再直接引用被审计为 C 级的竖图。

## 发布记录

- 负责人于 2026-09-15 明确同意发布。
- 已将 `AI页面-upgrade` 同步发布至 PC 端和无线端。
- 国际站返回发布成功；当前线上版本：`v20260915.000303`，发布时间 2026-09-15 00:03（Asia/Shanghai）。
- 发布后公开店铺首页已回读到新模块，真实厂房首图、六个真实产品分组链接及新图片资源均已加载。
- 上一历史版本 `v20260721.132216` 仍保留在国际站历史版本列表，可用于平台侧回溯。
