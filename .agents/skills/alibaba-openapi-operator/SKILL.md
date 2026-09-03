---
name: alibaba-openapi-operator
description: Use Beiqiang's Alibaba.com Open Platform application for API-first product, image-bank, video, quality-score, showcase, order, and logistics operations. Use when an Alibaba International Station task can be done through the authorized Open APIs; keep browser work only for authorization, unsupported UI-only fields, and final public-page verification.
---

# Alibaba OpenAPI Operator

Prefer the authorized Alibaba Open APIs over repetitive browser form work. The application currently exposes 72 APIs across product/media, order, logistics, and system authorization.

## Safety and evidence

- Credentials live only at `C:/Users/spq/.config/beiqiang/alibaba-openapi.json`. Never print the secret, copy it into prompts, commit it, or place it in generated workbooks.
- Treat the current permission page and current official API documentation as authoritative. Read [references/permissions.md](references/permissions.md) to route an operation.
- Read-only discovery and validation may run directly. A product publish/update, inventory/display change, order creation/shipping, address change, or other external mutation requires explicit authorization in the current task and an exact target summary before the call.
- Do not infer unsupported Alibaba fields. Product facts and quality gates still come from the workspace Alibaba SOP and SKU evidence.
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

The first authorization requires a user-approved OAuth grant in Alibaba. Authentication uses GOP while seller business APIs use the TOP-compatible protocol on Alibaba.com's current API server. After authorization, the script stores access and refresh tokens beside the credentials and refreshes them without exposing them.

## Product operations

For publishing or repair, read [references/product-publishing.md](references/product-publishing.md). The preferred sequence is:

1. Resolve a leaf category and fetch its current publish Schema.
2. Upload every local image through `alibaba.icbu.photobank.upload`; retain both returned image URL and file ID.
3. Fill the Schema XML from verified product data and current platform rules.
4. Create a draft for validation when practical, then publish with the new Schema endpoint.
5. Associate the correct product or factory video only after the product ID is known.
6. Read the product back, check quality score, and verify the public page when it becomes available.

Use browser only when OAuth consent, CAPTCHA, a field absent from the API, or visible public-page verification requires it. Browser fallback does not replace API-side readback.

For a catalog-wide image audit, use `scripts/catalog_image_audit.py`. It is read-only: it retrieves every live product gallery, creates compact six-image contact sheets, checks image count/resolution/hero occupancy, and can match a user screenshot to the closest live image without storing hundreds of full-size CDN files.

## Documentation routing

- Authentication, signing, endpoints, and token handling: [references/auth-and-signing.md](references/auth-and-signing.md)
- All currently authorized APIs and their risk class: [references/permissions.md](references/permissions.md)
- Schema publishing, image-bank invariants, video binding, and verification: [references/product-publishing.md](references/product-publishing.md)
