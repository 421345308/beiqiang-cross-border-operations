---
name: image-conversion-review
description: Review Beiqiang Alibaba.com main images and first gallery images for search click-through and inquiry conversion. Use when checking product image roles, first-image quality, first 5 image sequence, duplicate image risk, B2B visual style, wide toe box/comfort proof, OEM image placement, and image remake priorities.
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

Default first 6 image roles:

1. Search hero: clean light/white background, complete product, high product occupancy, minimal text.
2. Core differentiator: wide toe box, breathable upper, slip-on opening, seasonal lining, or other real difference.
3. Comfort or fit proof: walking/standing scenario, closure, insole, flexibility, or wear structure.
4. Structure proof: sole, upper, outsole texture, cushioning, material details.
5. Color/SKU overview: real available colors with correct labels.
6. Buyer decision support: OEM/ODM, packing, sample, size, or order support when confirmed.

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

## 禁止事项

- Do not use Chinese domestic images directly if they look like Taobao/1688 pages.
- Do not add fake badges, certificates, reviews, waterproof/medical claims, or unconfirmed materials.
- Do not repeat near-identical images just to fill 6 slots.
- Do not make a lifestyle image where the shoe is unclear or different from the real product.
