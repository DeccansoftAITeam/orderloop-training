# Capstone brief: deliver one OrderLoop feature

Pick **one** of the three features. All three are backend-only and need no frontend change. All data is synthetic.

Rules that apply to every feature (from the project brief): money is integer cents; customer name, email, phone, address and the refund reason text must not appear in new responses unless stated; the refund rules in `backend/app/rules.py` are not changed.

---

## Feature A: Refund summary for one order

Support agents want a one-call summary of what has been refunded on an order.

`GET /orders/{order_id}/refund-summary` returns:

| Field | Type | Meaning |
|---|---|---|
| `order_id` | integer | The order |
| `refund_count` | integer | Number of refunds recorded |
| `refunded_cents` | integer | Sum of all refunds |
| `remaining_cents` | integer | What can still be refunded (same as `max_refundable_cents` in the eligibility rules) |
| `last_refund_at` | string or null | Timestamp of the newest refund, null if none |

Acceptance criteria to start from (rewrite them in your spec):

- When the order exists, the system shall return the five fields above.
- When the order has no refunds, the system shall return `refund_count` 0, `refunded_cents` 0 and `last_refund_at` null.
- If the order does not exist, then the system shall return 404 with code `order_not_found`.
- The system shall never include the refund reason text.

## Feature B: Daily refund report for finance

`GET /reports/refunds?date=YYYY-MM-DD` returns the refunds created on that day.

| Field | Type | Meaning |
|---|---|---|
| `date` | string | The day asked for |
| `count` | integer | Number of refunds that day |
| `total_cents` | integer | Their sum |
| `refunds` | list | Each with `refund_id`, `order_id`, `amount_cents` only |

Acceptance criteria to start from:

- When refunds exist on the date, the system shall list them oldest first with count and total.
- When no refund exists on the date, the system shall return count 0, total 0 and an empty list.
- If `date` is missing or not a valid calendar date, then the system shall return 422.
- The system shall not include the reason text or any customer data.

## Feature C: Possible-duplicate refund guard

A support agent double-clicks with two different idempotency keys and two identical refunds are created.

When a refund request has the same order and the same `amount_cents` as a refund created in the previous 5 minutes (by the clock `get_now`), and a different idempotency key, the system shall reject it with status 409 and code `possible_duplicate`.

Acceptance criteria to start from:

- If an identical refund (same order, same amount) exists within 5 minutes, then the system shall return 409 `possible_duplicate` and create nothing.
- When the same order and amount are requested exactly 5 minutes later or more, the system shall accept it.
- When the same amount is requested on a different order, the system shall accept it.
- When the same idempotency key is replayed, the system shall still return the original refund (unchanged behaviour).

---

## What you deliver

1. A spec at `docs/specs/<feature>.md`, from `docs/templates/spec.md`: EARS criteria with ids `AC-1`..., at least one "If ..., then" case, open questions answered, a plan, and an approval block signed by you **before** you write code.
2. Tests first: `backend/tests/test_capstone_<feature>.py`, committed before any change under `backend/app/`. Every `AC-n` appears in a test name or docstring.
3. The implementation. A custom skill or subagent where it helps (optional).
4. A review pass: `/code-review` plus your own checklist; findings listed in `CAPSTONE.md`.
5. A pull request from branch `capstone` on **your fork** with a green GitHub Actions run (`.github/workflows/ci.yml` is already there).
6. `CAPSTONE.md` at the repository root with the headings listed in the lab.
