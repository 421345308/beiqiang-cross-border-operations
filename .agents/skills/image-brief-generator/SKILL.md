---
name: image-brief-generator
description: Image brief and AI prompt generator for Beiqiang Alibaba.com operations. Use when creating design briefs or AI image prompts for Alibaba main images, detail images, shipping images, OEM/ODM images, factory images, quality inspection images, size charts, color charts, wide toe box comparison graphics, and product proof visuals for B2B shoe buyers.
---

# Image Brief Generator

Use this skill to create image briefs before selecting, designing, or generating Alibaba International Station images.

## 适用场景

- Alibaba first main image, gallery image, detail page image, and SKU color image planning.
- Wide toe box comparison image.
- Comfort, flexibility, lightweight, knit upper, EVA sole, size chart, and color chart visuals.
- OEM/ODM, packing, shipping, factory, warehouse, and quality-check images.
- AI image generation prompt writing when raw product assets are weak.

## 贝强业务规则

- Product must stay visually consistent with the real shoe photo and confirmed facts.
- First main image should be clean, product-first, international B2B style, with minimal or no text.
- Detail images should explain product before factory.
- Use English only on buyer-facing images.
- Use Beiqiang positioning: factory supply, wide toe box comfort, lightweight walking shoes, sample and order support.
- Keep filenames for Alibaba upload short when proposing names.

## 输出格式

Return:

```text
Image role:
Target buyer:
Product evidence:
Core message:
Layout brief:
Text on image:
Style direction:
AI prompt:
Negative prompt:
Required source assets:
Risk/confirmation notes:
Suggested filename:
```

For a full image set, return a table with one row per image.

## 禁止事项

- Do not change the shoe style, color, material, sole, or structure away from source evidence.
- Do not add fake logos, fake certificates, fake reviews, fake awards, or unsupported factory claims.
- Do not use Chinese text on international-facing images.
- Do not create dense Taobao/1688-style promotional layouts.
- Do not put uncertain facts such as unconfirmed material or weight on buyer-facing images.
