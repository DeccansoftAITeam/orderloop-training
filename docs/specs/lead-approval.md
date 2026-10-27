# Spec: Lead approval for large refunds

Status: approved
Risk tier: 3

## 1. Problem

Refunds above the lead-approval threshold (200.00) are blocked today with the error `approval_required` and the note "not supported yet". A support agent cannot refund a large order at all, so large cases are handled outside OrderLoop by email, with no record of who approved what. Finance cannot reconcile them.

## 2. User stories

- US-1: As a support agent, I want to submit a refund above the threshold and see it wait for a lead, so that I do not have to handle large refunds outside OrderLoop.
- US-2: As a support lead, I want to approve a pending refund, so that the customer is paid and the decision is on record.
- US-3: As a finance analyst, I want pending refunds kept apart from paid ones, so that the nightly settlement only contains approved money.

## 3. Acceptance criteria

| ID | Criterion | Test | Package | Status |
|---|---|---|---|---|
| AC-1 | WHEN the requested refund amount is above the lead-approval threshold, the rules SHALL report that lead approval is required | test_amount_above_threshold_requires_lead_approval | WP-1 | done |
| AC-2 | WHEN the requested refund amount is exactly the threshold, the rules SHALL report that no lead approval is required | test_amount_exactly_at_threshold_needs_no_approval | WP-1 | done |
| AC-3 | IF the requested amount is not an integer number of cents, THEN the rules SHALL raise TypeError | test_float_amount_is_rejected_as_not_cents | WP-1 | done |
| AC-4 | WHEN an agent submits a refund above the threshold, the API SHALL store it as pending_approval and answer 202 | test_large_refund_is_held_for_lead_approval | WP-2 | todo |
| AC-5 | WHEN a lead approves a pending refund, the API SHALL mark it approved and count it against the refundable maximum | test_lead_approval_makes_the_refund_count | WP-2 | todo |
| AC-6 | IF a caller without the lead role tries to approve a refund, THEN the API SHALL answer 403 and leave the refund pending | test_non_lead_cannot_approve | WP-2 | todo |
| AC-7 | WHILE a refund is pending approval, the order screen SHALL show the text "Awaiting lead approval" | test_pending_refund_label_is_shown | WP-3 | todo |

## 4. Open questions

| ID | Question | Owner | Answer |
|---|---|---|---|
| Q-1 | Is "above the threshold" strict, or does exactly 200.00 also need approval? | Support lead | Strictly above. Exactly 200.00 needs no approval, which matches the current code (`amount_cents > LEAD_APPROVAL_THRESHOLD_CENTS`). |
| Q-2 | Does the threshold apply to one refund request, or to the running total on the order? | Finance analyst | One request. A running total is a separate follow-up spec. |
| Q-3 | Do late refunds (over 30 days) use the same approval path? | Product owner | No. Late refunds stay blocked as `late_requires_lead`; they need a written justification and get their own spec. |
| Q-4 | Who may approve, and how does the API know the caller is a lead? | Security reviewer | A caller with the role lead. In this training build the role arrives in an X-Role header; real sign-in is out of scope. |
| Q-5 | Does a pending refund reduce what can still be refunded on the order? | Finance analyst | Yes. A pending amount is reserved so the order cannot be over-refunded while it waits. |

## 5. Design delta

- rules.py: one new pure function that answers "does this amount need a lead?". `decide` is not changed in WP-1.
- schema: `refunds` gets a `status` column (`approved` or `pending_approval`, default `approved`).
- API: a large refund returns 202 and is stored as pending; a new endpoint approves it; the eligibility maximum counts pending and approved amounts.
- Screen: the refund panel shows "Awaiting lead approval" for a pending refund.

## 6. Contracts between work packages

- WP-1 to WP-2: `rules.requires_lead_approval(amount_cents: int) -> bool`. True only when the amount is above `LEAD_APPROVAL_THRESHOLD_CENTS`. Raises TypeError for a non-integer.
- WP-2 to WP-3: refund JSON carries `"status": "pending_approval"` or `"status": "approved"`. Approve endpoint: `POST /refunds/{id}/approve` with header `X-Role: lead`; 200 on success, 403 otherwise.

## 7. Work packages

| ID | Goal | Files | Depends on | Done when |
|---|---|---|---|---|
| WP-1 | Pure rule: does an amount need lead approval? | backend/app/rules.py, backend/tests/test_rules.py | none | AC-1 to AC-3 tests pass and the suite is green |
| WP-2 | API: hold large refunds, approve them as a lead | backend/app/main.py, backend/app/schema.sql, backend/tests/test_api.py | WP-1 | AC-4 to AC-6 tests pass and the old "not supported yet" API test is replaced |
| WP-3 | Screen: show the pending state | frontend/src/App.tsx, frontend/src/api.ts | WP-2 | the label shows for a pending refund and the build passes |

## 8. Risk and approval gates

Why this tier: the feature decides who can release money, so it is tier 3.

Gates:

- G1: a human (the support lead) approves this spec before any test or code is written.
- G2: a human reads the failing tests of each package before the implementation starts.
- G3: a human reviews the diff of each package before it is merged; no package merges itself.
- G4: a human lead signs off the whole feature before it is released.
