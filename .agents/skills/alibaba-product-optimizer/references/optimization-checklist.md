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
5. Title: produce 3 options, 75-105 characters by default.
6. Attributes: align category, product group, required attributes, optional attributes, and custom attributes.
7. Main images: define roles before generating or selecting images.
8. Detail page: product proof first, company proof later.
9. Inquiry conversion: add sample/MOQ/customization prompt.
10. Final QA: ensure title, images, attributes, and detail modules do not contradict each other.

## Title Formula

```text
[B2B modifier] + [verified material/feature] + [closure/toe/sole] + [core product keyword] + [application/buyer use]
```

Good terms:

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

Default order:

1. Search hero: clean white/light background, product large and clear, minimal or no text.
2. Core differentiator: wide toe box, breathable knit, winter lining, flexible sole, or product-specific advantage.
3. Material/structure proof.
4. Comfort/use scene.
5. Color/variant overview.
6. Buyer decision support: OEM/ODM, sample, packing, size reference, or factory proof if product images are already strong.

## Detail Page Modules

Default product-first flow:

1. Product overview and application.
2. Specs table.
3. Size reference.
4. Material and structure details.
5. Function proof supported by photos or facts.
6. Color/SKU overview.
7. Order support: sample, MOQ discussion, packing, customization when true.
8. Company/factory proof after product modules.

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
