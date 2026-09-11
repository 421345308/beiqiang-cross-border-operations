# Live Publishing Gates

Use this reference for Alibaba product creation, live-product repair, and final verification.

## Canonical workflow

For Beiqiang, read `02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md` first. Its current workflow and `.agents/skills/alibaba-openapi-operator/SKILL.md` govern API-first execution. The notes below are supporting checks, not an alternate SOP; discover Workctl only for operations that require it.

## Source Of Truth

- Current SKU raw package and physical evidence.
- Current SKU `00_上架填写表.md`.
- Visually approved upload images and official Alibaba image-bank/CDN URLs.
- Current-run Workctl schema and current platform readback.

Never inherit product facts from an older listing. BQ032 and later are regular fit unless SKU-specific evidence or the user confirms a wide last.

## UI and Workctl observations

Apply this section only when the canonical SOP routes the operation through browser or Workctl. It does not replace supported OpenAPI operations. Discover current schema/help before using any historical command name or option mentioned below; the snippets describe observed behavior, not a command list to replay.

1. Discover current Workctl commands through `workctl schema`; never reuse old task IDs, cache keys, or hard-coded retired commands.
2. Use one product ID and one draft. For a live repair, save the live item from `pubAction=edit`, verify the draft exists, then edit that draft. Do not create a second product to repair the first.
3. Persist only official Alibaba image-bank/CDN URLs. Reject Accio temporary URLs, local paths, expiring OSS URLs, and nested strings such as `alicdn.com/kf/https://...`.
   - The picture-bank uploader accepts at most 10 images per batch.
   - Wait until each preview has finished processing before confirming.
   - If the duplicate-content dialog appears, reuse its existing `sc04.alicdn.com` URL. Do not treat the upload-page `sc01` preview as final proof.
   - Repeated filenames such as `04_colors.jpg` must be mapped by actual image content, not filename order.
4. Before publish, read back title, Model Number, six main images, SKU count and color-image bindings, at least four information-complete product detail images, five company images, and all URLs. Do not add filler solely to reach six product-detail images.
5. Publish, then verify copy, trunk, and public buyer page. Copy correct plus trunk old means review propagation is pending, not live completion.
6. Close stale browser editor tabs after publish. Saving a stale tab can recreate a draft.
7. Treat `workctl --compact-output` as a value flag: use `auto`, `off`, or `force`. If a call is reported as a generic CLI internal error, inspect `.workctl/recovery/last_error.json` before changing business data.
8. After editing SKU, read back the draft and validate total count, distinct colors, min/max sizes, special size restrictions, and SKU codes. Newly added draft rows can read back with `skuId=0`; use content and counts, not this temporary ID, as the pre-submit check.
9. Read the business message returned by `submit-draft`. Outer `success=true` only means the tool ran; `Attribute value cannot be blank.` is still a blocked submission. Completion requires the business message `submit draft success`.
10. When submission reveals a newly required material attribute, fill it only from the current package, physical images, or owner confirmation. Use a generic evidenced value such as `Foamed Material` when chemistry is unknown; never guess EVA, rubber, lining, or another specific compound to pass validation.

## Detail Types

- `productDescType=4`: verify structured `detailImage` and `companyImage` counts and URLs.
- `productDescType=5`: structured arrays can be empty while AI/HTML content exists. Verify the pageId/HTML or public buyer page before diagnosing missing content.
- For a legacy `productDescType=5` copy repair, do not expect the Workctl structured-detail write to update the public HTML. Use the original product's single browser edit page: open **AI详情编辑器**, edit only the required text modules, save inside the editor, click **编辑完成**, synchronize PC/mobile, return to the outer product form, and save the draft. Preserve all product-specific image modules.
- Read the seller `sellPreview` before submission. After submission, separately read the public `descIframe`. A safe seller preview with an old public iframe means review/propagation is pending; record it as pending and do not call the repair complete or start a batch.
- Scan both English and translated public text for fixed sample-fee promises (`refund`, `deduct`, `退还`, `抵扣`, `扣除`), unsupported fit claims (`wide toe`, `roomy toe`, `宽楦`, `宽敞鞋头`), and generic material wording (`Flyknit`, `飞织`). Keep only current-SKU evidenced product claims.
- If a malformed temporary URL cannot be removed through DELETE, clear the affected browser image groups, save the empty draft, then add only approved CDN URLs.

## Blocking Gate

Do not publish when any of these fail:

- SKU/model identity and title do not match the source package.
- Images contain Chinese promotion, domestic watermark, contact details, third-party branding, wrong model, or AI-altered product structure.
- Main images are not 6/6, SKU bindings are incomplete, product details are fewer than 4 or fail to explain the product clearly, or company images are not 5/5.
- Any URL is temporary, nested, local, malformed, or non-Alibaba.
- High-impact facts lack current-SKU evidence.

A quality score does not replace these checks.

## Completion Receipt

Record SKU, source model, productId, title/model result, main image count, SKU equation, detail/company counts, bad-URL scan, draft/copy/trunk/public-page results, and local payload/audit paths.
