# Spec: Refund summary for one order

Status: Approved
Risk tier: Low

## Problem
Support agents open the full order detail just to learn how much has been refunded and how much is left. A small read-only summary endpoint lets the queue and the reply assistant ask that one question cheaply.

## User stories
- As a support agent, I want a summary of the refunds on an order so that I can answer "how much is left?" at a glance.
- As a finance analyst, I want the summary to omit refund reasons so that no customer text leaks into reports.

## Acceptance criteria
EARS patterns used: "When ..., the system shall ..." and "If ..., then the system shall ...".

- AC-1: When the order exists, the system shall return order_id, refund_count, refunded_cents, remaining_cents and last_refund_at.
- AC-2: When the order has no refunds, the system shall return refund_count 0, refunded_cents 0 and last_refund_at null.
- AC-3: When the order has refunds, the system shall set remaining_cents to the refundable total minus refunded_cents, never below zero.
- AC-4: If the order does not exist, then the system shall return status 404 with code order_not_found.
- AC-5: The system shall not include the refund reason text in the response.

## Out of scope
- No frontend change.
- No change to how refunds are created or validated.

## Open questions
| # | Question | Owner | Answer |
|---|---|---|---|
| 1 | Does remaining_cents ignore the lead-approval threshold? | Support lead | Yes: it equals max_refundable_cents from the eligibility rules |
| 2 | What if the order is not delivered? | Support lead | Same numbers; eligibility is a separate concern |

## Plan
1. Add the pure function refund_summary(refundable_cents, amounts) to backend/app/rules.py, tested by AC-3.
2. Add GET /orders/{order_id}/refund-summary to backend/app/main.py using load_order, tested by AC-1, AC-2, AC-4 and AC-5.
3. Run the full backend suite and the frontend build.

## Approval
Approved by: Priya Nair (tech lead, synthetic)
Date: 2030-03-01
