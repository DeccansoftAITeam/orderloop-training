---
name: add-refund-rule
description: Adds or changes an OrderLoop refund business rule. Use when the user asks to add, change or fix a refund rule, fee, window, limit or eligibility condition in backend/app/rules.py.
---

# Add or change a refund rule

Follow these steps in order. Stop and ask if the rule is not written down in AGENTS.md or the request.

1. Restate the rule in one sentence, with its boundary (for example "exactly 30 days is on time").
2. Write the failing test first in `backend/tests/test_rules.py`. The name states the boundary.
3. Change `backend/app/rules.py` only. It stays pure: `now` is a parameter, money is integer cents.
4. Run `cd backend && uv run pytest -q`. Fix causes, never loosen a test.
5. Walk through `checklist.md` in this folder and report each item as done or not applicable.
