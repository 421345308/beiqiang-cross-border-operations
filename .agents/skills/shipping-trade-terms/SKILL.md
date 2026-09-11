---
name: shipping-trade-terms
description: Shipping and trade terms assistant for Beiqiang B2B shoe exports. Use when explaining or drafting EXW, FOB, DDP, FCA, air freight, sea freight, express delivery, Amazon FBA shipment, packing, carton, sample shipping, freight quotation questions, and buyer-facing logistics copy for Alibaba inquiries, RFQ replies, product pages, and follow-ups.
---

# Shipping Trade Terms

Use this skill to explain trade terms and draft buyer-safe logistics copy for shoe export conversations.

## 适用场景

- Explain EXW, FOB, FCA, DDP, air freight, sea freight, express, or Amazon FBA shipping.
- Draft Alibaba product-page shipping notes.
- Ask buyers for shipping data before quote.
- Reply to buyers asking DDP to door, DDP to Amazon FBA, sample courier cost, or sea freight estimate.
- Clarify what is included and not included in a price.

## 贝强业务规则

- Keep terms conservative and clear for B2B shoe buyers.
- Separate product price from freight, duty, tax, and local delivery unless a confirmed DDP quote is available.
- For DDP or Amazon FBA, request destination country/address, warehouse code, quantity, carton size, gross weight, packing method, and delivery time.
- For samples, prefer express/courier language and ask for receiver details.
- For bulk, suggest sea freight, air freight, or forwarder discussion based on urgency and quantity.

## 输出格式

Return:

```text
Scenario:
Recommended term:
Buyer-facing explanation:
Message template:
Data needed for final quote:
Risk notes:
Internal operator note:
```

## 禁止事项

- Do not give final DDP, freight, duty, tax, or FBA cost without confirmed logistics data.
- Do not promise customs clearance success.
- Do not say FOB includes door delivery.
- Do not blur EXW, FOB, FCA, and DDP responsibilities.
- Do not recommend high-frequency freight quote changes without buyer intent.
