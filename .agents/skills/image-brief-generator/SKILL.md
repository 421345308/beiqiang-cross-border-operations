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
- Use the current SKU's evidenced positioning. Factory supply, fit, comfort, weight, materials, sample support and OEM/ODM scope must each be supported; `Wide Toe Box` is not a store-wide default.
- Keep filenames for Alibaba upload short when proposing names.
- Start with a buyer question, not an image label. `OEM/ODM`, `FAQ` and `FACTORY` are useful only when the image contains specific, credible decision information.
- For factory briefs, specify the exact proof role: supplier identity, customization workflow, production organization, quality checkpoint, or packing/order handoff. Do not use generic clean interiors as a substitute for evidence.

## Alibaba B2B 主图组信息架构

M1 继续承担搜索点击与商品识别：真实产品优先、主体清楚、文字克制。M2-M6 不是同一鞋面、同一颜色或同一卖点的重复展示；整组必须帮助进口商、批发商和品牌买家完成不同采购判断。

先列出本款买家尚未解决的问题，再从以下角色中选择互不重复的内容。没有证据的角色不要硬凑：

- 商品结构、不同有效角度或本款真实差异点；
- 实际颜色、尺码范围与SKU选择；
- `WHOLESALE`、`OEM/ODM`、打样流程或买家需提供的定制输入；
- 真实工厂拼图、生产组织、质检节点或订单协作能力；
- 包装选择，例如袋装、盒装或外箱交接；包装方式是可讨论选项，不等于默认报价已包含；
- MOQ、混色混码、询价信息或其他能推动买家发询盘的下一步。

B2B 标识必须对应具体信息，不做装饰性徽章。可使用 `WHOLESALE`、`OEM/ODM`、`SAMPLE SUPPORT`、`PACKAGING OPTIONS` 等简短英文，但只有在公司或单款证据支持时才能出现。公司能力图允许复用经核实的模板；产品细节、颜色、尺码、材料与产品承诺必须逐款映射。

## 输出格式

Return:

```text
Image role:
Target buyer:
Buyer question answered:
Product evidence:
Core message:
Layout brief:
Text on image:
Style direction:
AI prompt:
Negative prompt:
Required source assets:
Risk/confirmation notes:
Buyer next step enabled:
Suggested filename:
```

For a full image set, return a table with one row per image.

## 禁止事项

- Do not change the shoe style, color, material, sole, or structure away from source evidence.
- Do not add fake logos, fake certificates, fake reviews, fake awards, or unsupported factory claims.
- Do not use Chinese text on international-facing images.
- Do not create dense Taobao/1688-style promotional layouts.
- Do not put uncertain facts such as unconfirmed material or weight on buyer-facing images.
- Do not present AI-outpainted buildings, equipment, production scale or factory processes as factual proof until the owner confirms the reconstruction. Mark such candidates `FACT_CHECK_REQUIRED`.
