# Authorized Alibaba API inventory

Observed from Beiqiang application `SELF_APP2218064103529` on 2026-09-03. Application state: online. Flow limit: 1,000,000 calls/day. Four permission groups are effective, totaling 72 APIs.

Risk classes: **R** read-only; **W-product** product/media mutation; **W-order** order/logistics/address mutation; **Auth** token operation.

## Product, image, video, showcase and shipping-template package — 40

| API | Purpose | Risk |
|---|---|---|
| `alibaba.icbu.category.attr.get` | Category attributes | R |
| `alibaba.icbu.photobank.list` | Image-bank query | R |
| `alibaba.icbu.photobank.upload` | Upload image | W-product |
| `alibaba.icbu.product.group.get` | Product groups | R |
| `alibaba.icbu.product.group.add` | Add product group | W-product |
| `alibaba.icbu.category.attribute.get` | Legacy category attributes | R |
| `alibaba.icbu.product.update` | Legacy full update | W-product |
| `alibaba.wholesale.shippingline.template.list` | Shipping templates | R |
| `alibaba.icbu.product.list` | Product list | R |
| `alibaba.icbu.product.get` | Legacy product detail | R |
| `alibaba.icbu.product.id.decrypt` | Decrypt legacy product ID | R |
| `alibaba.icbu.product.update.field` | Legacy field update | W-product |
| `alibaba.scbp.showcase.status` | Showcase status | R |
| `alibaba.scbp.showcase.list` | Showcase list | R |
| `alibaba.scbp.showcase.deleteproduct` | Remove showcase products | W-product |
| `alibaba.scbp.showcase.addproduct` | Add showcase products | W-product |
| `alibaba.scbp.showcase.sort` | Reorder showcase | W-product |
| `alibaba.scbp.showcase.updateproduct` | Replace showcase product | W-product |
| `alibaba.icbu.photobank.group.operate` | Image-bank group operation | W-product |
| `alibaba.icbu.product.batch.update.display` | Batch online/offline | W-product |
| `alibaba.icbu.product.add.draft` | Legacy product draft | W-product |
| `alibaba.icbu.product.score.get` | Product quality score | R |
| `alibaba.icbu.category.level.attr.get` | Legacy child attributes | R |
| `alibaba.icbu.video.query` | Video query | R |
| `alibaba.icbu.product.schema.get` | Current publish Schema | R |
| `alibaba.icbu.category.get.new` | Current category tree | R |
| `alibaba.icbu.product.schema.add` | Current product publish | W-product |
| `alibaba.icbu.video.relation.product.detail` | Bind detail video | W-product |
| `alibaba.icbu.video.relation.product.main` | Bind main video | W-product |
| `alibaba.icbu.product.schema.add.draft` | Current Schema draft | W-product |
| `alibaba.icbu.product.schema.render` | Render/read product | R |
| `alibaba.icbu.product.schema.update` | Current incremental update | W-product |
| `alibaba.icbu.product.schema.render.draft` | Render/read draft | R |
| `alibaba.icbu.product.id.encrypt` | Encrypt current ID for legacy calls | R |
| `alibaba.icbu.video.relation.product.list` | Product-video bindings | R |
| `alibaba.icbu.category.schema.level.get` | Current hierarchical attributes | R |
| `alibaba.icbu.category.id.mapping` | Old/new attribute mapping | R |
| `alibaba.icbu.product.inventory.update` | Update SKU inventory | W-product |
| `alibaba.icbu.product.sku.inventory.get` | Read SKU inventory | R |
| `alibaba.icbu.product.country.getcountrylist` | Product-country list | R |

## Order package — 20

| API | Purpose | Risk |
|---|---|---|
| `alibaba.seller.order.list` | Order list | R |
| `alibaba.seller.order.fund.get` | Order funds | R |
| `alibaba.seller.order.logistics.get` | Order logistics | R |
| `alibaba.seller.order.get` | Order detail | R |
| `alibaba.seller.order.shipping` | Ship an order | W-order |
| `alibaba.seller.order.shipping.channels` | Carrier list | R |
| `alibaba.trade.fulfillment.channel.get` | Fulfillment channels | R |
| `alibaba.trade.service.charge.get` | Trade service fees | R |
| `alibaba.seller.order.shipping.fetch.batchorder` | Create/get shipment batch | W-order |
| `alibaba.seller.assurance.credit.card` | Seller credit report | R |
| `alibaba.order.trade.tt.get` | Trade Assurance TT account | R |
| `alibaba.trade.address.get` | Address query | R |
| `alibaba.seller.order.multi.shipping` | Multi-batch shipment | W-order |
| `alibaba.seller.order.shippingorder.query` | Shipping order query | R |
| `alibaba.seller.order.shipping.batch.modify` | Modify shipment batch | W-order |
| `alibaba.icbu.ecology.write` | Trade-ecosystem authorization admission | W-order |
| `alibaba.intention.order.save` | Create intention order | W-order |
| `alibaba.seller.address.save` | Save seller address | W-order |
| `alibaba.seller.trade.query.drafttype` | Query order-draft permission | R |
| `alibaba.trade.address.delete` | Delete address | W-order |

## Online express logistics package — 10

| API | Purpose | Risk |
|---|---|---|
| `alibaba.onetouch.logistics.express.special.product.type.list` | Cargo type options | R |
| `alibaba.onetouch.logistics.express.charge.calculate` | Freight calculation and parameter check | R |
| `alibaba.onetouch.logistics.express.logistics.product.list` | Logistics capacity/options | R |
| `alibaba.onetouch.logistics.express.address.city.list` | City list | R |
| `alibaba.onetouch.logistics.express.address.province.list` | Province list | R |
| `alibaba.onetouch.logistics.express.address.division.list` | District list | R |
| `alibaba.onetouch.logistics.express.address.street.list` | Street list | R |
| `alibaba.onetouch.logistics.express.order.detail.get` | Logistics order and label detail | R |
| `alibaba.onetouch.logistics.express.logistics.solution.semi.list` | Semi-managed routes | R |
| `alibaba.onetouch.logistics.express.pickup.query` | First-mile pickup query | R |

## System authorization — 2

| API | Purpose | Risk |
|---|---|---|
| `/auth/token/create` | Exchange authorization code for token | Auth |
| `/auth/token/refresh` | Refresh token | Auth |
