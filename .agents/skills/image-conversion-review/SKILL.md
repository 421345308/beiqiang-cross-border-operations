---
name: image-conversion-review
description: Review Beiqiang Alibaba.com main images and first gallery images for search click-through and inquiry conversion. Use when checking product image roles, first-image quality, gallery sequence, duplicate image risk, B2B visual style, SKU-supported product proof, OEM image placement, and image remake priorities.
---

# Image Conversion Review

Use this skill to judge whether Alibaba product images can win clicks and help buyers understand the product quickly.

## 适用场景

- Review first main image before publishing or P4P testing.
- Audit first 5-6 gallery images for role clarity and duplicate risk.
- Decide whether to remake a main image, detail proof image, color overview, OEM image, or order-support image.
- Compare Beiqiang images against public competitor galleries.

## 输入要求

Use any of:

- Local product folder with `01_主图`, `02_详情页`, `03_颜色图`.
- Product screenshots or Alibaba live URL.
- Product code/model, buyer intent, target keyword, source photos, confirmed material/size/color facts.
- Previous image audit notes.

## 图组标准

M1 is normally a clean, complete, product-first search hero with a light/white background, strong product occupancy and minimal text. Do not force M2-M6 into a permanent sequence. First list the buyer's unresolved questions, then select distinct roles from this library:

- additional angle or construction proof;
- real color/SKU choice and supported size information;
- a genuine differentiator such as closure, upper structure, lining or outsole;
- use/fit evidence that can be shown without inventing performance;
- confirmed OEM/ODM scope and the inputs required from the buyer;
- quote FAQ, sample/packing/order support or another concrete next step;
- supplier/factory proof when it answers a procurement-risk question.

Every image must answer one primary buyer question. If removing an image does not reduce search recognition, product understanding, supplier trust or inquiry readiness, treat it as redundant. Two white-background views, repeated black shoes or a generic factory photo are not justified merely because the six slots exist.

For a normal six-image Alibaba B2B gallery, require portfolio-level coverage rather than six cosmetic variations. M1 should win the click and identify the exact shoe. Across M2-M6, cover distinct procurement questions such as actual SKU choice, construction or differentiator, confirmed OEM/ODM and sampling support, real factory/order capability, and available bag/box packing or inquiry inputs. Sequence these roles for the product and evidence at hand; do not repeat the same surface, color, angle, headline or capability merely to fill slots.

Treat `WHOLESALE`, `OEM/ODM`, `SAMPLE SUPPORT`, `MIXED SIZES/COLORS` and `PACKAGING OPTIONS` as information labels, not decorative badges. Each label must be backed by visible evidence or a confirmed company/SKU capability. Packaging visuals should distinguish an available option from standard included packing and should never imply a price inclusion that has not been quoted.

## 输出格式

Return:

```text
Image review scope:
Evidence used:
Image role table:
CTR risk:
Conversion risk:
Duplicate image risk:
Remake priorities:
Recommended image prompts or briefs:
Pending confirmations:
ChatGPT handoff:
```

Image role table fields:

```text
Product | Image | Current role | Pass/Weak/Fail | Problem | Rewrite/remake action
```

## 贝强业务规则

- Keep images international B2B-facing, clean, product-first, and suitable for US/EU buyers.
- Use real product photos as the anchor; image enhancement must not change the shoe identity.
- Product images should explain the shoe before factory/company proof.
- OEM/ODM visuals are useful, but should not replace product proof in the first image.
- A reusable company-capability template may appear after the product has been identified, but product detail, color, size, material and construction panels must be regenerated or rebuilt from the exact SKU evidence. Never reuse another shoe's detail panel merely because the layout fits.
- For an existing link, a verified high-recognition color may become M1 and the whole six-image sequence may be rebuilt around it. Judge whether the new gallery improves the search card and buyer understanding; do not reject the change merely because the product structure is unchanged.
- For a proposed sibling link, compare it with every link sharing the same factory article number. Different M1 colors or reordered images are presentation changes, not proof of an independent listing.
- Before approving the set, identify the target buyer, the decision blocked without each image, the evidence shown, and the next action enabled. Visual polish alone is not conversion proof.

## 同货号家族审查

For every same-model family, report:

- Shared source model and SKU matrix.
- M1 difference.
- Exact or near-duplicate count across M2-M6.
- Product-detail image overlap.
- Real structural or procurement-intent difference.
- Decision: `OPTIMIZE_CANONICAL`, `KEEP_DISTINCT`, `MERGE_REVIEW`, or `PAUSE_REVIEW`.

Classify `5/6 shared main images + all product-detail images shared` as high-confidence duplicate-presentation risk. A unique title, color-first M1, OEM/wholesale prefix, or generic use-scene wording does not by itself change that result.

## AI适度优化与验收

真实原图是商品身份的证据，不代表必须原封不动上传。原图如果主体小、背景杂、构图弱、光线差或不适合国际站搜索缩略图，应评估AI受控编辑；不要因为“是真图”就保留低竞争力首图，也不要因为“是AI图”就自动淘汰。

可接受的AI优化包括：

- 清理或替换为干净白色/浅色背景，移除无关道具和场景干扰。
- 放大、居中和重新构图，提高鞋体占比并保持完整边缘。
- 调整曝光、白平衡、对比度、清晰度和自然接触阴影。
- 以真实鞋图为锚创建克制的通勤、步行或采购展示场景，以及不改变SKU事实的颜色总览或结构版式。
- 修复抠图毛边和低清晰度，但不能借“修复”重画商品结构。

必须保持不变：鞋头比例、鞋楦与整体轮廓、鞋底高度/曲线/纹路、鞋面分区与针织纹理、闭合方式、鞋口、后跟拉环、材料外观、Logo及真实SKU颜色。AI不得补造不存在的配色、部件、标签、功能、认证、评价或工厂事实。

AI候选进入正式图片银行前，至少完成：真实参考图可追溯、原图与候选同屏对照、原尺寸逐项检查、六图整组检查、颜色/SKU/标题一致性检查。结构无法确认或出现漂移即淘汰；通过上述门禁的AI图可以作为M1正式候选，不要求退回较弱原图。

需要生成或编辑时，读取[电商图片生成经验](../alibaba-international-operations/references/ecom-image-generation-lessons.md)，先形成图片角色与负面约束，再生成和验收。

## 禁止事项

- Do not use Chinese domestic images directly if they look like Taobao/1688 pages.
- Do not add fake badges, certificates, reviews, waterproof/medical claims, or unconfirmed materials.
- Do not repeat near-identical images just to fill 6 slots.
- Do not make a lifestyle image where the shoe is unclear or different from the real product.
- Do not approve a factory visual that cannot state what credible buyer concern it resolves. AI-expanded architecture remains `FACT_CHECK_REQUIRED` until the owner confirms it matches the real site.
