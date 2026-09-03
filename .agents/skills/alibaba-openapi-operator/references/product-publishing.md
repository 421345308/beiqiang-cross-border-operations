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

## Image invariant

All images persisted into product fields must come from the seller's Alibaba image bank. `photobank.upload` returns both `photobank_url` and `file_id`; Schema main-image fields need both. A URL copied from an existing product page is not automatically valid for republishing. Maximum raw upload size is 5 MB according to the image-upload API documentation.

For Beiqiang, keep the existing live-publishing visual gates: six strong gallery images, correct SKU/color binding, at least four information-complete product-detail images, five company images, no domestic Chinese overlays, no third-party marks, and no filler images.

## Detail page

The Open API supports ordinary rich-text detail pages. Set the detail type to ordinary editing and place the verified HTML in the Schema detail field. Structured/AI detail editing is not currently the API path; use the existing product-first HTML detail design.

## Video

- Query available videos with `alibaba.icbu.video.query`.
- The verified minimal query is `current_page=1&page_size=1`.
- Bind a product-specific video to the main gallery with `alibaba.icbu.video.relation.product.main`.
- Bind a video in the detail area with `alibaba.icbu.video.relation.product.detail`.
- Read bindings with `alibaba.icbu.video.relation.product.list`.

Never reuse a product video for a visibly different shoe. A general factory video is acceptable only where the page role is supplier proof rather than product demonstration.

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
- Product API catalog: https://developer.alibaba.com/docs/api.htm?apiId=25439
- Image upload API: https://developer.alibaba.com/docs/api.htm?apiId=24463
