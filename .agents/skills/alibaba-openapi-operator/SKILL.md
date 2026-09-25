---
name: alibaba-openapi-operator
description: Execute Beiqiang Alibaba.com product, image-bank, video, quality, showcase, order and logistics operations through the authorized OpenAPI client. Use for API execution and readback; publishing rules remain in the workspace SOP.
---

# Alibaba OpenAPI Operator

Prefer the authorized Alibaba Open APIs over repetitive browser form work. Resolve scripts relative to this skill directory and business data relative to the workspace root; do not run the examples from an unrelated `scripts/` directory.

## Safety and evidence

负责人于2026-09-08确认：只有原始数据包中的商品属于贝强自有工厂货。阿里巴巴国际站扩品可能没有实际存在的商品；已上线、API回读、图片、生成素材、热榜或竞品记录均不能证明产品实物存在、自有工厂生产或可供货。必须逐款关联原始数据包；没有匹配证据的扩品标记为 HOLD_SOURCE（实物与货源待核验），不得称为自有工厂货、计入已确认供给或承诺样品/库存/交期。外部商品经后续核实可以记录真实来源，但不自动成为自有工厂货；归属变化须由负责人明确确认。

- Credentials default to `~/.config/beiqiang/alibaba-openapi.json` (`Path.home()` in the client). A different external file can be selected with `--config` before the command. Never print secrets, copy them into prompts, commit them, or place them in generated workbooks.
- Treat the current permission page and current official API documentation as authoritative. Read [references/permissions.md](references/permissions.md) to route an operation.
- Read-only discovery and validation may run directly. Product/media, inventory/display, order/shipping, address and other external mutations must remain within the user's authorized targets and scope. Prepare the exact change before any missing approval is requested; existing authorization in the conversation remains valid.
- For publishing or repair, read [the canonical lifecycle SOP](../../../02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md) and the SKU source evidence. Do not infer unsupported fields or copy historical defaults.
- For sourced HR replacement, supplier `0`/"not stocked" is not an API inventory target or automatic source failure. Once the specific order route and replacement SKU identity are evidenced, write `999` for valid SKUs in the rebuilt draft, submit together with consistent new-shoe assets, and read back formal inventory. Treat `999` as a seller-side inquiry marker, not literal on-hand quantity; never count a stock-only update on an old-shoe page as a completed replacement.
- Record request IDs, trace IDs, returned product IDs, and platform error objects. Do not call success unless the API returns a positive business result.

## Runtime

Use `scripts/alibaba_openapi.py` rather than reimplementing signing or token handling.

```powershell
python scripts/alibaba_openapi.py doctor
python scripts/alibaba_openapi.py self-test
python scripts/alibaba_openapi.py auth-url
python scripts/alibaba_openapi.py call alibaba.icbu.product.list --params-json params.json
python scripts/alibaba_openapi.py upload-image C:/absolute/image.jpg
python scripts/catalog_image_audit.py --output C:/absolute/audit-folder --reference C:/absolute/reference.png
```

The first authorization requires a user-approved OAuth grant in Alibaba. Authentication uses GOP while seller business APIs use the TOP-compatible protocol. The client saves returned tokens in the external configuration file. It does **not** automatically refresh an expired token: use `refresh-token` when needed, then verify the required read API before resuming.

## Product operations

For publishing or repair, read [references/product-publishing.md](references/product-publishing.md). The preferred sequence is:

1. Resolve a leaf category and fetch its current publish Schema.
2. Upload every local image through `alibaba.icbu.photobank.upload`; retain both returned image URL and file ID.
3. Fill the Schema XML from verified product data and current platform rules.
4. Create a draft for validation when practical, then publish with the new Schema endpoint.
5. Associate the correct product or factory video only after the product ID is known.
6. Read the product back, check quality score, and verify the public page when it becomes available.

For an existing product repair, prefer a minimal incremental Schema containing only the target fields and documented dependencies. Render the target's current Schema first; do not use another product's full Schema as a shortcut for a one-field edit. Inspect current video fields before writing, because an overlinked video can block otherwise unrelated edits. See the failure-handling rules in the publishing reference.

Use `alibaba.icbu.product.get` for review state and formal field readback. Do not make a status check depend on `schema.render`: while a product is under review, Alibaba can return a valid request/trace pair but omit rendered `data`. Treat that as an unavailable editable Schema, not as proof that `product.get` failed.

Use browser only when OAuth consent, CAPTCHA, a field absent from the API, or visible public-page verification requires it. Browser fallback does not replace API-side readback.

For a catalog-wide image audit, use `scripts/catalog_image_audit.py`. It is read-only: it retrieves every live product gallery, creates compact six-image contact sheets, checks image count/resolution/hero occupancy, and can match a user screenshot to the closest live image without storing hundreds of full-size CDN files.

Other helpers: `catalog_secondary_image_audit.py` performs a read-only follow-up audit; `batch_replace_hero.py` and `replace_full_gallery.py` write live products. Inspect each helper's `--help` and input manifest before use; their presence does not authorize a batch change.

## Documentation routing

- Authentication, signing, endpoints, and token handling: [references/auth-and-signing.md](references/auth-and-signing.md)
- All currently authorized APIs and their risk class: [references/permissions.md](references/permissions.md)
- Schema publishing, image-bank invariants, video binding, and verification: [references/product-publishing.md](references/product-publishing.md)
