# Capstone: refund summary for one order

## Feature
Feature A from docs/capstone-brief.md: `GET /orders/{id}/refund-summary`. Spec: docs/specs/refund-summary.md (5 criteria, AC-1 to AC-5, approved before any code). Tests: backend/tests/test_capstone_refund_summary.py, committed red before the code. Implementation: a pure `refund_summary` function in rules.py and one route in main.py.

## What Claude got wrong
- Its first test set asserted only the status code for the 404 case, not the error code `order_not_found`. I asked for the body to be checked too.
- It computed `remaining_cents` from all items, so final-sale socks on order 1004 counted as refundable. A test with that order caught it before the code existed to hide it.
- It proposed adding `reason` to the response "for convenience". That breaks AC-5, so I rejected it.

## Review findings
- `/code-review` found no correctness bug; it suggested reusing `load_order` instead of a second query (done).
- My checklist: money is integer cents (yes); no customer fields in the response (yes); `last_refund_at` uses max of ISO strings, which sorts correctly because the format is fixed (noted, covered by AC-3 test); no change outside backend/app and backend/tests (yes).
- Not fixed: the endpoint has no pagination because an order has few refunds. Recorded as out of scope.

## Cost
About 1.8 million tokens in total on the seat, roughly 40 minutes of agent time. The test-writing step was the cheapest; the review pass cost the most because it read the whole diff twice.

## What I would change
- Write the approval block before asking Claude for the plan, not after; I edited the plan twice to match it.
- Use a read-only subagent for the first review so my main context stays small.
- Add the not-delivered order to the tests (open question 2) instead of only answering it in the spec.

## Pull request
https://github.com/example-learner/orderloop-training/pull/1 (example link for the reference solution; use your own fork). CI: backend and frontend jobs green.
