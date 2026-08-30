# Direct Data API Catalog

Use this catalog to select a domain, then confirm the current operation contract in [Allegro REST API documentation](https://developer.allegro.pl/documentation). Paths, media types, scopes, pagination, and fields evolve.

## Recommended seller read coverage

| Domain | Principal GET resources | Purpose |
|---|---|---|
| Account | `/me` | Authorized identity and base marketplace |
| Seller offers | `/sale/offers`, `/sale/product-offers/{offerId}`, `/sale/product-offers/{offerId}/parts` | List and retrieve seller offer state |
| Offer changes | `/sale/offer-events` | Journal of recent offer changes |
| Products/categories | `/sale/products`, `/sale/products/{productId}`, category and category-event resources | Catalog matching and listing requirements |
| Sale settings | Return policies, warranties, shipping rates, delivery settings, services, size tables, tags | IDs and policies referenced by offers |
| Orders | `/order/events`, `/order/event-stats`, `/order/checkout-forms`, `/order/checkout-forms/{id}` | Incremental order discovery and full detail |
| Order shipment info | `/order/carriers`, `/order/checkout-forms/{id}/shipments`, carrier tracking | Carrier and tracking state |
| Customer returns | `/order/customer-returns`, `/order/customer-returns/{customerReturnId}` | Return requests and details |
| Billing | `/billing/billing-entries`, `/billing/billing-types` | Fees and account charges |
| Payments | `/payments/payment-operations`, `/payments/refunds` | Payment operations and refund history |
| Shipment management | Delivery service, shipment, command, and pickup GET resources | Allegro shipment capabilities and state |
| Disputes | `/sale/issues` and issue detail/chat/attachment GETs | Complaints and transaction disputes |
| Messages | Thread, message, and attachment GET resources | Buyer/seller correspondence |
| Ratings | Seller rating/statistics and feedback resources | Account reputation |
| One Fulfillment | Inventory, product, ASN, label/status GET resources | Allegro fulfillment programs |

## High-value synchronization patterns

### Orders

Use `/order/events` as the incremental source and persist the last durably processed event ID. Fetch `/order/checkout-forms/{id}` for the current aggregate. Use `/order/event-stats` for gap detection and list checkout forms for reconciliation. Events can represent purchase, delivery-form completion, payment changes, cancellation, surcharge, and fulfillment changes; do not infer full order state from one event.

### Offers

Use `/sale/offer-events?from={eventId}` for recent changes and `/sale/offers` plus detail calls for reconciliation. The offer event journal documents only a limited recent retention window, currently 24 hours, so a stalled consumer must fall back to list/detail reconciliation rather than assuming an old cursor remains complete.

### Billing and payments

Use `/billing/billing-entries` for Allegro fees/charges and `/payments/payment-operations` for payment balance operations. They answer different accounting questions. Keep amount plus currency, occurrence time, order/offer identifiers, entry/operation IDs, and retrieval time. Never substitute fee previews for posted billing truth.

### Marketplace and localization

Call `/me` to learn `baseMarketplace.id`. Pass `marketplaceId` only where supported. Use documented `Accept-Language` values for localized messages; do not use it as a data partition key. API date-times are UTC (`Z`), while web UI dates can display marketplace-local time.

## Pagination

- Ordinary lists commonly use `limit` and `offset`; respect each operation's maximum and returned totals.
- Event journals use an event ID such as `from`; advance only after durable processing and deduplicate by event ID.
- Some product resources use `page.id` cursors. Treat them as opaque and do not mix them with offsets.
- Retain cursors per environment, application, authorized account, and domain.

Official guides:

- [Complete method list](https://developer.allegro.pl/tutorials/lista-metod-rest-api-allegro-yPyaj0wG3C4)
- [Offer management](https://developer.allegro.pl/tutorials/jak-zarzadzac-ofertami-7GzB2L37ase)
- [Order handling](https://developer.allegro.pl/tutorials/jak-obslugiwac-zamowienia-GRaj0qyvwtR)
- [Fees and billing](https://developer.allegro.pl/tutorials/jak-sprawdzic-oplaty-nn9DOL5PASX)
- [Shipment management](https://developer.allegro.pl/tutorials/jak-zarzadzac-przesylkami-przez-wysylam-z-allegro-LRVjK7K21sY)
- [Message Center](https://developer.allegro.pl/tutorials/jak-zarzadzac-centrum-wiadomosci-XxWm2K890Fk)
