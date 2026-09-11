# E-commerce Image Generation Lessons

Source reference: `https://github.com/liangdabiao/ecom-details-image`.

Use this only as image-generation method inspiration. Do not copy its Amazon/Shopify image count or template order directly into Alibaba International Station listings.

Keep generated upload filenames within 30 characters including the extension. Resolve dimensions, image counts and acceptance against the current workspace publishing SOP.

## Useful Ideas To Adopt

- Visual brief before prompts: define product, target buyer, selling point, image role, style, and evidence source before generating.
- Conversion driver diagnosis: decide whether the image should be visual-driven, pain-point-driven, functional proof-driven, or trust-driven.
- Campaign Style Lock: keep the whole product image set visually consistent with the same color palette, typography style, lighting, background, icon style, and layout rhythm.
- Prompt/Generate split: first write a clear image plan and prompt; generate only after the prompt matches the buyer role and product evidence.
- Negative constraints: every generation prompt should specify what to avoid, such as wrong shoe, changed color, unsupported claims, fake certificates, Chinese text, messy typography, cropped labels, excessive blank space, or domestic promotional style.
- Template inspiration: useful template types for Beiqiang shoes include hero image, lifestyle scene, detail macro, before/after comparison, packaging, infographic, size/spec chart, multi-angle grid, and sports/walking campaign.

## Alibaba Adaptation

- Alibaba main images should prioritize search click and B2B product understanding, not social-media novelty.
- Use fewer stronger images over a full set of weak images. The image count from other platforms is not a target.
- Main gallery images should be 1:1 and product-led. Detail-page modules can be vertical or square depending on Alibaba editor needs.
- Use the real product photo/cutout as the anchor. Generated scenes and diagrams can support the product, but must not change the actual shoe structure, material, color, outsole, or closure.
- Strong promotional language is allowed only when true and useful for B2B buyers. Avoid exaggerated consumer-ad claims, fake reviews, fake certificates, and unsupported performance data.

## Beiqiang AI Image Workflow

Default hierarchy:

1. Preserve truth first: use real source photos, SKU photos, and cutouts as the factual anchor.
2. Use deterministic local processing for routine cleanup: background removal, white canvas composition, size charts, color grids, and text layout.
3. Use AI generation/editing when local processing cannot create a buyer-grade asset: weak raw scenes, poor first-image click appeal, missing lifestyle/use scene, awkward domestic props, or a detail module that needs a cleaner product-led visual.
4. Do not use pure text-to-image generation for first main images unless the real product identity can still be preserved from a reference/cutout. For upload assets, AI should enhance or stage the real product, not invent a different shoe.

Use built-in `image_gen` when the user has no `OPENAI_API_KEY` or is using a subscription plan only. Treat it as the default AI path for product scene generation and image editing. Use CLI/API `gpt-image-2` only when the user explicitly chooses an API workflow and has configured `OPENAI_API_KEY`; a ChatGPT/Codex subscription is not the same as an API key.

AI asset intake rule:

- Put generated or edited AI images into the matching product folder as traceable candidate inputs before any formal replacement, preferably under `05_AI候选/`.
- Keep a short candidate note with the intended image role, prompt direction, pass/fail judgment, and reasons for rejection or next iteration.
- Do not place an AI image into `01_主图` or `02_详情图` until it passes SKU identity, edge/shadow, resolution, composition, and buyer-click quality checks.
- If an AI tool only shows a preview and does not expose a local file path or downloadable asset, record the candidate decision but do not claim the formal file has been created.

AI is appropriate for:

- Upgrading a weak first image into a cleaner product-led hero while preserving the real shoe.
- Creating a neutral walking/commuting/travel scene for image 4 or 6 when the source package lacks a useful lifestyle photo.
- Rebuilding domestic promotional graphics into clean English B2B modules.
- Creating product-detail supporting visuals such as breathable upper texture, cushion sole emphasis, flexible/walking comfort, winter fleece context, or simple packaging/order-support scenes when supported by evidence.

AI is not appropriate for:

- Changing outsole tread, sole thickness, toe shape, closure type, upper texture, colorway, lining, logo, or SKU identity.
- Inventing certificates, reviews, factory capacity, weight, anti-slip grade, waterproof/safety/orthopedic claims, or other unverified performance proof.
- Producing heavy text, fake badges, domestic e-commerce labels, or dramatic consumer-ad imagery for the first Alibaba main image.

Main image shadow rule:

- Avoid full-shoe halo/outline shadows created from the whole cutout alpha. They make the shoe look pasted onto the canvas.
- If grounding is needed, use no shadow or only a very light contact shadow under the sole. The shadow must not wrap around the upper, heel loop, or toe edge.
- Always inspect at full size after white-background reconstruction. Reject grey edge halos, scene remnants, missing sole texture, jagged cutout edges, or visible pasted rectangles.

## Prompt Checklist For Beiqiang Product Images

Before generating, include:

- Product anchor: which exact shoe photo/cutout to preserve.
- Image role: search hero, feature proof, material detail, size chart, color overview, use scene, or order support.
- Buyer-facing message: one short headline or 2-4 compact labels.
- Evidence: which source image or confirmed fact supports the claim.
- Style lock: light international B2B style, consistent colors, clean typography, high product occupancy.
- Negative constraints: no Chinese text, no fake logos/certificates/reviews, no wrong shoe/color/material, no internal notes, no clutter, no oversized blank space.
