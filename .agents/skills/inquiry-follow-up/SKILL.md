---
name: inquiry-follow-up
description: Draft or review post-inquiry follow-ups for Beiqiang B2B shoe buyers by Alibaba, WhatsApp or email. Use for next-step messages, no-reply follow-ups and sample discussions; use rfq-quote-assistant for a first quotation.
---

# Inquiry Follow Up

## Required reads

- Read the relevant buyer record and exact SKU/commercial evidence; apply [workspace boundaries](../../../AGENTS.md).

Use this skill to move a buyer from inquiry to confirmed specs, sample order, or bulk-order discussion.

## 适用场景

- Alibaba International Station inquiry follow-up.
- WhatsApp short follow-up.
- Sample order push after buyer shows interest.
- No-reply buyer second or third follow-up.
- Quotation reminder after sending FOB/DDP/sample details.
- Buyer qualification: market, quantity, size range, color, packing, logo, delivery time.

## 贝强业务规则

- Position Beiqiang as a Quanzhou footwear factory supplier.
- Keep the buyer type B2B: importer, wholesaler, Amazon/TikTok seller, brand buyer, sourcing agent.
- Discuss only the current SKU's verified shoe type, fit, materials, source and feasible order options. Wide toe, EVA, samples, mixed sizes/colors and OEM/ODM are conditional.
- Use FOB `8-12 USD/pair` only as a reference range when relevant; final price depends on style, quantity, material, size ratio, packing, and trade terms.
- Ask for one clear next action, not a long survey.
- Identify whether this is a new inquiry, quoted-buyer follow-up, sample follow-up or visitor outreach. Read the actual buyer stage, earlier answer and stop-contact state. A first-inquiry automatic reply does not establish visitor popup access; verify account feature and trigger separately before any proposal. Country informs language, destination rules and timezone, never a stereotype of price or certification interest.
- Deliver a stage-specific draft and internal next-check only; do not activate automation or send a message. For translation, preserve model facts, units and confirmed sizes, and verify local buyer language rather than treating machine translation as search-demand evidence.

## 输出格式

Return only the message and internal notes needed for the requested channel and buyer stage. For a complete follow-up sequence, use:

```text
Buyer status:
Follow-up goal:
Recommended channel:

Alibaba message:

WhatsApp short message:

Sample-order push:

No-reply follow-up:

Questions to confirm:

Internal note:
```

## 禁止事项

- Do not write retail-consumer discount language.
- Do not promise final price, delivery date, certificates, stock, DDP cost, or Amazon FBA delivery before confirmation.
- Do not use pressure tactics or spammy repeated messages.
- Do not invent buyer details.
- Do not copy competitor wording.
