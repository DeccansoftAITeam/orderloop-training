# Feature request: refund status in the order queue

Support agents cannot tell from the order queue whether an order has been refunded. They open every order to find out.

## What we want

Each row of `GET /orders` gets two new fields:

| Field | Type | Meaning |
|---|---|---|
| `refunded_cents` | integer | Total refunded so far on the order |
| `refund_status` | `"none"`, `"partial"` or `"full"` | `none`: nothing refunded. `partial`: something refunded and more can still be refunded. `full`: everything refundable has been refunded |

`GET /orders` also accepts `?refund_status=none|partial|full` to filter the queue. Any other value is rejected with status 422. It combines with the existing `q` and `status` filters.

## Rules

- Money is integer cents. No floats.
- "Refundable" means the same as in the eligibility rules: items that are final sale or gift cards never count.
- The status calculation is a pure function in `backend/app/rules.py`:
  `refund_status(refundable_cents: int, refunded_cents: int) -> str`.
- An order with nothing refundable and nothing refunded is `none`.
- The list response must not contain customer email, phone, address or the refund reason text.

## Out of scope

- No change to the frontend.
- No change to how refunds are created or validated.
