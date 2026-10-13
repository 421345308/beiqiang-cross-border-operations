# Live Publishing Gates

Use this reference for Alibaba product creation, live-product repair, and final verification.

## Canonical workflow

For Beiqiang, read `02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md` first. Its current workflow and `.agents/skills/alibaba-openapi-operator/SKILL.md` govern API-first execution. The notes below are supporting checks, not an alternate SOP; Workctl is retired; historical observations below are evidence only and must not be replayed.

## Source Of Truth

- Current SKU raw package and physical evidence.
- Current SKU `00_上架填写表.md`.
- Visually approved upload images and official Alibaba image-bank/CDN URLs.
- Current-run supported OpenAPI/category schema and current platform readback.

Never inherit product facts from an older listing. BQ032 and later are regular fit unless SKU-specific evidence or the user confirms a wide last.

## Current verification scope

Use lifecycle SOP §§5–9 for current supported execution, before/after field preservation and public verification. Unknown writes are reconciled before retry; already-bound IDs are not recreated. Local changes cover the target and linked fields; shared assets cover their binding impact set; shop-wide blocking requires a real shop-wide risk. Retired interface commands remain in historical receipts, not this execution route.

## Detail Types

- `productDescType=4`: verify structured `detailImage` and `companyImage` counts and URLs.
- `productDescType=5`: structured arrays can be empty while AI/HTML content exists. Verify the pageId/HTML or public buyer page before diagnosing missing content.
- Legacy detail repair must preserve exact-SKU modules and verify actual public HTML; use the supported route in the SOP, not a retired structured-detail command. PC/mobile synchronization is only within existing applicable authorization after PC verification.
- Read the seller `sellPreview` before submission. After submission, separately read the public `descIframe`. A safe seller preview with an old public iframe means review/propagation is pending; record it as pending and do not call this target complete; unrelated authorized preparation can continue under the SOP risk scope.
- Scan both English and translated public text for fixed sample-fee promises (`refund`, `deduct`, `退还`, `抵扣`, `扣除`), unsupported fit claims (`wide toe`, `roomy toe`, `宽楦`, `宽敞鞋头`), and generic material wording (`Flyknit`, `飞织`). Keep only current-SKU evidenced product claims.
- If a malformed temporary URL cannot be removed through DELETE, clear the affected browser image groups, save the empty draft, then add only approved CDN URLs.

## Acceptance authority

Apply lifecycle SOP §3 for source/claim/brand/image truth, §4 for the current six-main/four-detail/five-company default and the exact 2627BSK exception, and §§7–9 for scoped acceptance. Do not lower the store default, invent missing views or add filler. A score does not replace fact, field-preservation or public checks; the current actual ≥5.0 requirement remains in the SOP.

## Completion Receipt

Record SKU, source model, productId, title/model result, main image count, SKU equation, detail/company counts, bad-URL scan, draft/copy/trunk/public-page results, and local payload/audit paths.

完整经营验收同时填写现有采集模板 E/F：关键词须正式持久化，实际评分须有时间与来源，旧新映射与授权旧品收尾须回读。只完成公开内容与评分可以报阶段通过，不能抹去经营待办。
