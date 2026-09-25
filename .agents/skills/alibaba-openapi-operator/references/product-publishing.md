# Product publishing through Alibaba OpenAPI

## Use the new Schema flow

The maintained product flow is Schema-driven:

1. `alibaba.icbu.category.get.new` — resolve a leaf category.
2. `alibaba.icbu.product.schema.get` — fetch current XML fields and rules.
3. `alibaba.icbu.photobank.upload` — upload local product/detail/company images.
4. `alibaba.icbu.product.schema.add.draft` — create a draft when a validation pass is needed.
5. `alibaba.icbu.product.schema.render.draft` — read the draft back.
6. `alibaba.icbu.product.schema.add` — publish a completed product.
7. `alibaba.icbu.product.schema.render` — read a submitted/approved product.
8. `alibaba.icbu.product.schema.update` — incrementally update supported fields.
9. `alibaba.icbu.product.score.get` — inspect quality score.

Legacy `product.add`, `product.update`, and older attribute interfaces remain authorized but should not be the default because Alibaba directs new integrations to the Schema flow.

## Incremental update discipline

Alibaba's official update guide states that `alibaba.icbu.product.schema.update` is incremental: only submitted fields should change. For an ordinary repair, render the current target product to discover the live field shape, then submit a minimal `<itemSchema>` containing only the intended fields and any documented linked dependencies. Do not clone another product's full rendered Schema merely to change one title, model or image.

Category input properties can encode typed text in the `inputValue` attribute while the value node retains a negative custom marker. For example, a rendered model field may be `<value inputValue="8025">-2</value>`; changing only the node text is incorrect. Preserve the current field type and marker and update `inputValue` according to the rendered Schema and official examples.

Use full-Schema replacement only for a deliberate whole-product migration. Before such a write, scrub source identity, SKU codes, videos, groups, company/detail content and every inherited field that is not intentionally shared. Compare the target before/after snapshots and stop if an unrelated field would change.

Alibaba can return `biz_success=true` for an incremental field payload that produces no formal-data change. A successful update receipt is therefore submission evidence, not field verification. After review, compare `product.get` and the target's rendered Schema with the intended value. If the formal value is unchanged, record the attempt as a no-op and stop repeating it.

Do not assume that omission, `<values />`, `<complex-value />`, or an empty `multiComplex` means “delete the existing value.” The official Schema update documentation defines the endpoint as incremental and does not document a generic deletion marker for `customMoreProperty`. In particular, an empty `customMoreProperty` payload must not be treated as a verified deletion method. If an existing custom property must be removed, use the current seller UI unless Alibaba publishes a field-specific delete contract, then verify the approved formal value again through OpenAPI.

Keep status polling separate from editable-Schema rendering. `alibaba.icbu.product.get` remains the status source. During `modified/N` review, `alibaba.icbu.product.schema.render` may return request and trace IDs without `data`; this is an expected transient platform state. Do not classify it as token failure, and do not use browser state to replace the API status check.

## Image invariant

All images persisted into product fields must come from the seller's Alibaba image bank. `photobank.upload` returns both `photobank_url` and `file_id`; Schema main-image fields need both. A URL copied from an existing product page is not automatically valid for republishing. Maximum raw upload size is 5 MB according to the image-upload API documentation.

Main-image values carry both the image-bank URL and `fileId`. A URL copied from a product or CDN page is not a substitute for the image-bank asset returned by `photobank.upload`/`photobank.list`.

`schema.render` may expose seller-page fields such as `detailImage`, `companyImage`, `textDesc`, or other structured/AI-detail components. Their presence in rendered XML is read evidence, not proof that `schema.update` supports writing or deleting them. Alibaba's official publishing guide states that the API supports only ordinary rich-text detail editing. Do not submit structured detail-gallery replacements through `schema.update` as a normal supported path. If a historical experiment returns `biz_success=true` but the approved structured detail remains unchanged, record the no-op once and switch that field to the seller UI; do not retry with flat CDN URLs, fuller Schema copies, or alternate empty-node shapes.

For Beiqiang, keep the existing live-publishing visual gates: six strong gallery images, correct SKU/color binding, at least four information-complete product-detail images, five company images, no domestic Chinese overlays, no third-party marks, and no filler images.

## Detail page

The OpenAPI supports ordinary rich-text detail pages only. The official guide specifies `productDescType=2` with verified HTML in `superText`, and explicitly says API publishing supports only the ordinary-editor detail type. Structured/AI detail modules and their gallery fields must be edited in the seller UI unless Alibaba later documents a supported write API. Do not convert an existing structured detail page to ordinary HTML merely to avoid the UI unless the user has intentionally chosen that page-type migration and the conversion has been reviewed.

Do not confuse Schema updates with Work Agent draft-edit operations. `alibaba.icbu.product.schema.update` has no documented generic delete marker for a structured detail gallery, so omission or an empty node is not a deletion request. Where the current Work Agent schema exposes `product-edit-draft-detail`, its `detailImage`, `companyImage`, and `faqs` inputs are operation lists rather than final-state arrays: delete an existing image with `operationType=DELETE` plus the exact `originalImageUrl` returned by the current draft readback, and add a replacement separately with `operationType=ADD` plus the approved image-bank URL. Verify the draft count and contents after each phase. A `draft edit success` receipt is not proof that the gallery changed; if exact DELETE operations still leave auto-migrated images, stop retrying and use the seller UI to reach and save a verified zero-image state before adding the whitelist.

## Video

- Query available videos with `alibaba.icbu.video.query`.
- The verified minimal query is `current_page=1&page_size=1`.
- The platform also exposes `alibaba.icbu.video.upload`, which imports a video from a publicly reachable HTTPS `video_path`; it is not a direct local-file/multipart upload API. As rechecked on 2026-09-05, Beiqiang application `SELF_APP2218064103529` does not currently have this upload permission. Do not try to call it until that permission is granted.
- Bind a product-specific video to the main gallery with `alibaba.icbu.video.relation.product.main`.
- Bind a video in the detail area with `alibaba.icbu.video.relation.product.detail`.
- Read bindings with `alibaba.icbu.video.relation.product.list`.

Before any product write, inspect rendered `imageVideo` and `detailVideo` values when present. Query `alibaba.icbu.video.relation.product.list` for a reused video if a relation limit may apply. `CHK_VIDEO_PRODUCT_LINK_LIMIT` means the existing main video has reached the platform's product-link limit; retrying the same payload or switching to a full Schema does not fix it. Preserve request/trace IDs and stop repeated writes. If the video is still the correct generic factory evidence, the seller UI may save unrelated fields to a draft even when OpenAPI rejects the same edit; use that as an explicit UI fallback, preserve the video, and verify the saved draft separately. Do not report a UI draft save as a public update. Otherwise resolve the video relation through a supported reassignment or unbinding path before retrying. Never detach unrelated products just to make a field edit pass.

For visual classification, do not scrub a short video manually in the seller-page player unless no media source can be acquired. Prefer the `video-use` workflow: obtain the verified video-bank HTTPS URL, download it into the task's temporary review directory, run `video_qa.py scan --kind reference`, inspect the timestamped whole-video contact sheet, and open original-resolution or focused frames only where the sheet is ambiguous. Use the seller UI only to confirm the live binding and final state. A few manually selected player frames are not a substitute for a whole-video scan.

Never reuse a product-led video for a visibly different shoe. A general factory video is acceptable where the page role is supplier proof rather than product demonstration. Other styles may appear incidentally in production, inspection, packing or multi-style factory scenes; this does not make the video product-specific. Reject it only when another style becomes the featured hero, receives isolated appearance/fit/feature demonstration, or is presented with claims that a buyer could attribute to the current SKU.

When one verified company-owned factory video reaches the platform product-link ceiling, a duplicate video-bank entry may be used as an association-capacity shard if the platform accepts it. This is an operational copy, not a new creative: keep the title/notes explicit, maintain product-to-video mapping, and normally cap each entry at 15-18 products to leave headroom below 20. Do not manufacture multiple videos merely to imply broader factory evidence. Create genuinely different production, quality or packing videos only when they add real evidence or buyer value.

## Read-only smoke-test recipes

- Product list: `alibaba.icbu.product.list` with `language=ENGLISH`, `current_page=1`, `page_size=1`.
- Image bank: `alibaba.icbu.photobank.list` with `extra_context={}`, `location_type=ALL_GROUP`, `current_page=1`, `page_size=1`.
- Video bank: `alibaba.icbu.video.query` with `current_page=1`, `page_size=1`.

Run these after first authorization or token refresh before any write call. A non-empty business response plus `request_id` confirms transport and authorization; it does not replace payload validation for publishing.

For catalog pagination, use the official `current_page` and `page_size` names. Do not substitute `pageNo` or `pageSize`: Alibaba may ignore unknown names and silently return page 1 repeatedly. Bound the page loop and stop with an explicit error if the returned page number disagrees with the request or a page payload repeats.

## Verification and failure handling

### Inventory update operation value (2026-09-23 verified)

For `alibaba.icbu.product.inventory.update`, the official `InventoryDto.operate` value for increasing stock is **`plus`**, not `add`; decreasing uses `sub`. The API can return `result.success=true` and `data=true` for an `add` payload while SKU inventory remains unchanged. Never accept that wrapper response alone: call `alibaba.icbu.product.sku.inventory.get` afterward and compare every target SKU's actual value. Existing opportunity products with no inventory rows may need a SKU-bearing Schema submission before the inventory endpoint can address them. While `product.get` reports `modified/N`, inventory mutation can return “product under review”; wait for review to finish before retrying. For sourced HR products, `999` remains the owner's availability marker, not a physical count. [Official inventory update API](https://developer.alibaba.com/docs/api.htm?apiId=53178).

- Draft readback: title/model, category, attributes, sizes, shoe length, prices, MOQ, lead time, package data, images, SKU mappings, detail HTML, and video IDs.
- Submitted readback: product ID, business-success flag, trace ID, and review state.
- Quality check: product score and exact platform diagnostics.
- Final check: public product page after review; report `submitted/reviewing` until it is visibly live.
- On an API error, preserve `request_id`/`trace_id`, error code, sub-code, and the exact rejected field. Repair the source payload; do not fall back to manual clicking without diagnosing the API failure.

Primary sources:

- New product publishing guide: https://developer.alibaba.com/docs/doc.htm?articleId=119213&docType=1&treeId=456
- Product API migration notice: https://developer.alibaba.com/docs/doc.htm?articleId=119212&docType=1&treeId=456
- Incremental product update guide: https://developer.alibaba.com/docs/doc.htm?articleId=119214&docType=1&treeId=456
- Schema update API: https://developer.alibaba.com/docs/api.htm?apiId=50189
- Product API catalog: https://developer.alibaba.com/docs/api.htm?apiId=25439
- Image upload API: https://developer.alibaba.com/docs/api.htm?apiId=24463
