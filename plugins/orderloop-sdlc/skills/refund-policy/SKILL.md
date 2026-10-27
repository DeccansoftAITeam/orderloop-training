---
name: refund-policy
description: OrderLoop refund policy as a decision procedure. Use when deciding whether a refund should be approved, denied or escalated to a team lead, or when drafting the customer reply for that decision.
---

# OrderLoop refund policy

Input: the results of `check_refund_eligibility` and `lookup_order` for one order.
Money is integer cents. Use the limits the tool returns (`window_days`, `lead_approval_threshold_cents`); never type a limit from memory.

## Decide: the first rule that matches wins

1. `blockers` contains `not_delivered` -> **deny**. Nothing has arrived to return.
2. `blockers` contains `no_refundable_items` or `nothing_left_to_refund` -> **deny**. Final-sale items and gift cards are never refundable.
3. `late` is true -> **escalate**. Refunds after the window need a team lead.
4. `max_refundable_cents` is above `lead_approval_threshold_cents` -> **escalate**. Large refunds need a team lead.
5. Otherwise -> **approve** for the full `max_refundable_cents`.

Exactly `window_days` days after delivery is still on time (`late` is false).
`amount_cents` is `max_refundable_cents` for approve and escalate, and `0` for deny.

## Customer reply

- Address the customer by first name only. Never include an email, phone number or address, not even masked.
- Refer to the order by its number.
- approve: say the refund is approved for the amount, written as dollars (`$95.00`), and a team member will process it.
- deny: say plainly why, using the reason in plain words, and offer to help with anything else.
- escalate: say a team lead is reviewing; do not promise an outcome or an amount.
- Under 80 words, friendly, no jargon.

## Return exactly this JSON object, in one fenced json block

```json
{
  "order_id": 1002,
  "decision": "approve",
  "amount_cents": 9500,
  "reason": "One sentence naming the rule that decided it.",
  "rules_checked": ["delivered", "within window", "under lead-approval threshold"],
  "customer_reply": "Hi Ben, ...",
  "human_next_step": "What the support lead does next."
}
```

`decision` is one of `approve`, `deny`, `escalate`. Include no other text.
