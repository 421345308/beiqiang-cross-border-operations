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

## Image invariant

All images persisted into product fields must come from the seller's Alibaba image bank. `photobank.upload` returns both `photobank_url` and `file_id`; Schema main-image fields need both. A URL copied from an existing product page is not automatically valid for republishing. Maximum raw upload size is 5 MB according to the image-upload API documentation.

For Beiqiang, keep the existing live-publishing visual gates: six strong gallery images, correct SKU/color binding, at least four information-complete product-detail images, five company images, no domestic Chinese overlays, no third-party marks, and no filler images.

## Detail page

The Open API supports ordinary rich-text detail pages. Set the detail type to ordinary editing and place the verified HTML in the Schema detail field. Structured/AI detail editing is not currently the API path; use the existing product-first HTML detail design.

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

## Verification and failure handling

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
