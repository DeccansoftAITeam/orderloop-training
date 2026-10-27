# Review: Add 5% goodwill credit for late deliveries

Reviewed with `git diff main...flawed-pr`, `/code-review medium` and the team checklist in `docs/pr-goodwill-credit.md`.
The 19 tests pass on this branch, and that is the problem: the changes that break rules are not covered, or were made to pass.

Verdict: **request changes**. Do not merge.

## High

- **Weakened test hides a changed rule** (`backend/tests/test_rules.py:19`, `backend/app/rules.py:67`). The assertion `not el.late` was removed from `test_exactly_thirty_days_is_still_on_time`, and the window check changed from `>` to `>=`. An order delivered exactly 30 days ago is now late and needs lead approval. The author's description says "no test was changed". Restore the assertion and the `>`.
- **Customer personal data is written to the log** (`backend/app/main.py:137-139`). The log line holds name, email, phone and the free-text refund reason. Rule 2 forbids it. Log the refund id only.
- **No idempotency check on the new endpoint** (`backend/app/main.py:162-177`). It takes no `Idempotency-Key`; the stored key contains `now.timestamp()`, so it is different on every call. A retry or double click pays the customer twice. Require the header and reuse the replay logic of `create_refund`.

## Medium

- **The code calls a helper that does not exist** (`backend/app/main.py:173`). `rules.round_to_cents` is not defined anywhere in the repository, so the endpoint raises `AttributeError` on every call. Nothing exercises the endpoint, so no test notices.
- **Money calculated with floats** (`backend/app/rules.py:104-106`). `goodwill_credit` returns dollars as a float (`total / 100 * 0.05`) and the caller multiplies back to cents. Rule 1 says integer cents: use `total_cents * 5 // 100`.

## Low

- **Unrequested dependency `arrow`** (`backend/pyproject.toml:9`, imported at `backend/app/main.py:169`). Added only for `humanize()`, and the description says "no new dependencies". It also reads the real clock instead of the injected `now`.

## Also noticed

- No tests were added for the new endpoint or the new rule (rule 7). It also gives the credit to orders that were not late and counts final-sale items.

## Tool results and false positives

- `/code-review medium main...flawed-pr` reported 10 findings. It found all six problems above, with line numbers up to three lines off in places.
- Only the checklist caught that the author's description is false ("no test was changed", "no new dependencies"), and that tests for the new code are missing. The tool missed those because it reviews the code, not the claims.
- False positives: none that I would discard. The finding about the customer lookup after `commit()` is real but minor, so I left it out of the blocking list.
- Everything above was checked by me against the diff before it was written down. I am accountable for this review, not the tool.
