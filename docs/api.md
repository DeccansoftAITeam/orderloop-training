# OrderLoop API reference

Base URL in development: `http://localhost:8000`. Money is always integer cents.

## GET /health

Returns `{"status": "ok"}`.

## GET /orders

The order queue. Query parameters:

| Parameter | Meaning |
|---|---|
| `q` | Search by order id or customer name |
| `status` | Only orders with this status (`delivered`, `shipped`) |

Each row has `id`, `status`, `placed_at`, `delivered_at`, `customer_name` and `total_cents`. Rows never contain email, phone or address.

## GET /orders/{id}

One order with its items, earlier refunds and the eligibility result (`eligible`, `late`, `days_since_delivery`, `max_refundable_cents`, `qualifying_skus`, `blockers`). Unknown id: `404 order_not_found`.

## POST /orders/{id}/refunds

Records a refund. Body: `{"amount_cents": 5000, "reason": "Item did not fit"}`. The header `Idempotency-Key` is required; sending the same key again returns the first refund with `"replayed": true` and never creates a second one.

| Status | Code | When |
|---|---|---|
| 201 | none | Refund recorded |
| 400 | `idempotency_key_missing` | No `Idempotency-Key` header |
| 404 | `order_not_found` | Unknown order |
| 409 | `not_eligible` | Not delivered, nothing refundable, or nothing left to refund |
| 409 | `late_requires_lead` | More than 30 days after delivery (not supported yet) |
| 409 | `approval_required` | Amount above the lead-approval threshold of 20000 cents (not supported yet) |
| 422 | `reason_invalid` | Reason shorter than 3 or longer than 200 characters |
| 422 | `amount_invalid` | Amount is zero or negative |
| 422 | `exceeds_max` | Amount is more than the refundable maximum |

## POST /orders/{id}/reply-draft

Body: `{"message": "..."}`. Returns a suggested customer reply and the masked message. The draft is a suggestion; nothing is sent.
