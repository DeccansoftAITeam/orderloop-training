# Lab 10: Refund Triage evaluation

Each row is one run of the refund-triage agent on a seeded order. Amounts are in cents.

| Order | Scenario | Expected decision | Expected amount_cents | Actual decision | Match? | Actual amount_cents | Notes |
|---|---|---|---|---|---|---|---|
| 1002 | Delivered exactly 30 days ago, one pair of boots | approve | 9500 | approve | yes | 9500 | On time: 30 days is not late |
| 1003 | Delivered 31 days ago | escalate | 7000 | escalate | yes | 7000 | Late refunds need a lead |
| 1008 | Four-person tent, 450 dollars | escalate | 45000 | escalate | yes | 45000 | Above the lead-approval threshold |
| 1005 | Gift card only (optional extra row) | deny | 0 | deny | yes | 0 | Gift cards are never refundable |

PII check: no email address, phone number or street address appeared in any customer reply. The MCP server masks email and phone, and the skill forbids them in a reply anyway.
