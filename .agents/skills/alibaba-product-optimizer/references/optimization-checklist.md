# Alibaba Product Optimization Checklist

Use this checklist for one Beiqiang Alibaba product page.

## Required Inputs

Collect or inspect:

- Product model or internal code.
- Source photos and color/SKU photos.
- Upper, outsole, lining, closure, season, size range.
- Target buyer and target market.
- Existing listing title, images, attributes, and detail page if available.
- Price, MOQ, packing, lead time, sample policy, and customization facts if confirmed.

If a high-impact fact is missing, proceed with a conservative draft and list it under pending confirmations.

## Workflow

1. Positioning gate: apply `beiqiang-positioning`.
2. Product role: new listing, variant, duplicate risk, seasonal style, or skip candidate.
3. Competitor check: use `competitor-research-firecrawl` if keyword or image strategy is uncertain.
4. Keyword cluster: choose one primary buyer intent and 3-5 supporting long-tail terms.
5. Title: produce up to 3 useful options when comparison adds value; length and structure follow current keyword evidence and buyer clarity rather than a permanent character target.
6. Attributes: align category, product group, required attributes, optional attributes, and custom attributes.
7. Main images: define roles before generating or selecting images.
8. Detail page: product proof first, company proof later.
9. Inquiry conversion: add sample/MOQ/customization prompt.
10. Final QA: ensure title, images, attributes, and detail modules do not contradict each other.

## Title Starting Structure

This is a `DEFAULT_HEURISTIC`, not a fixed formula. Reorder or replace it when current keyword evidence and buyer intent support a clearer title.

```text
[B2B modifier] + [verified material/feature] + [closure/toe/sole] + [core product keyword] + [application/buyer use]
```

Possible terms when supported by the exact SKU and current keyword intent:

- `Wholesale`
- `Factory Direct`
- `Breathable Knit`
- `Wide Toe Box`
- `Slip-On`
- `Lightweight`
- `EVA Sole`
- `Comfort Walking Shoes`
- `Casual Sneakers`
- `for Daily Walking`
- `for Travel and Commuting`

Avoid:

- Repeated words just for length.
- `Flyknit` if platform flags it.
- Unsupported `orthopedic`, `medical`, `waterproof`, `leather`, `certified`, or brand terms.

## Main Image Roles

M1 is normally a clean product-first search hero. Select the remaining roles only after listing the target buyer's unresolved questions. Available roles include additional angles, verified construction, color/size choice, supported use evidence, OEM/ODM scope, quote inputs, packing/order support and supplier proof. Each image must add distinct decision value; do not repeat a white-background shoe, color or factory scene merely to fill six slots.

## Detail Page Modules

Use a product-first flow, but combine and reorder modules around current buyer questions and platform limits. Cover product identity, verified choices/structure, procurement support and supplier trust without redundant sections. Company/factory proof follows enough product proof for the buyer to know what is being sourced.

## Output Template

```text
Product:
Product role:
Buyer intent:
Primary keyword cluster:

Title options:
1.
2.
3.

Keywords:

Attributes:
- Required:
- Optional:
- Custom:

Selling points:

Main image plan:

Detail page plan:

Inquiry hook:

Pending confirmations:

Operator notes:
```
