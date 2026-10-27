# Team review: refund digest

Mode: team
Display mode: in-process

(Reference solution: written the way a finished report looks. The cost figures are illustrative.)

## Team

| Name | Angle |
|---|---|
| lead | splits the work, synthesises, writes this report |
| privacy | personal data in logs, keys and output |
| money | correct arithmetic, edge cases, business rules |
| perf-tests | speed and what the existing test misses |

## Findings

### Privacy

- [H] The log line writes the customer name and e-mail at INFO for every refund. Logs are copied to other systems.
- [M] The e-mail address is the key of `by_customer`, so personal data ends up in the digest that is e-mailed on.

### Money and correctness

- [H] An empty day divides by `len(refunds)` and crashes with a divide-by-zero error.
- [H] `average_cents` uses `/`, so it is a float such as 1001.5. Money is integer cents: use `//`.
- [M] A refund whose customer is not in the list is dropped from `by_customer` without a trace, so the parts do not add up to the total.
- [M] `large` uses `>= 20000`, but the rule is strictly more than the threshold; the number is also typed twice instead of imported from `rules.py`.

### Tests and performance

- [M] The nested loop over refunds and customers is quadratic: 4000 by 4000 takes seconds. Build a set of customer ids once.
- [M] The only test checks the total. Nothing covers the empty list, the boundary, unknown customers or the log.

## Debate

Challenged finding: the nested loop is a performance problem (perf-tests)
Challenged by: money
Outcome: changed. Kept as medium: the digest runs once a night on a few hundred refunds, so it is not urgent, but the same lookup fixes the unknown-customer bug, so it is done anyway.

## Cost and cleanup

Teammates spawned: 3
Teammates shut down: yes
Cost note: Three teammates each read the same two files, so the review cost several times one session for a change this small; a single reviewer would have found most of it.

## Decision

- Fix: guard the empty list and use integer division for the average
- Fix: key by customer id, bucket unknown customers under "unknown", never log name or e-mail
- Fix: strict greater-than against `LEAD_APPROVAL_THRESHOLD_CENTS` imported from rules
- Fix: build a set of known customer ids once
- Skip: e-mailing the digest (out of scope for this change)
