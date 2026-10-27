# Change under review: daily refund digest

Branch: the code is already on your lab branch in `backend/app/refund_digest.py`.
Test: `backend/tests/test_refund_digest.py`.

## What the author says

> Adds `build_digest(refunds, customers)`. The support lead gets one summary a day:
> how many refunds, the total, the average, the total per customer, and the refunds
> that are large enough to need a second look. It will be called from a nightly job
> and the result sent to the lead by e-mail. All amounts are integer cents (see
> `AGENTS.md`/`rules.py`: money is never a float).

## Contract the digest must keep

| Key | Meaning |
|---|---|
| `count` | number of refunds |
| `total_cents` | sum of `amount_cents`, an integer |
| `average_cents` | `total_cents // count`, an integer; `0` when there are no refunds |
| `by_customer` | `{customer id: total cents}`; a refund whose customer is not in the list goes under the key `"unknown"`, so the parts always add up to the total |
| `large` | ids of refunds that need lead approval: strictly more than `LEAD_APPROVAL_THRESHOLD_CENTS` in `app/rules.py` |

Nothing that identifies a customer (name, e-mail) may be written to a log or used as a key.
