---
paths:
  - "backend/**/*.py"
---

# Backend rules

- Business rules go in `app/rules.py` as pure functions that take `now` as an argument. Never call `datetime.now()` inside a rule.
- Routes in `app/main.py` stay thin: parse input, call the rules, return JSON.
- Every new rule gets a test in `backend/tests/test_rules.py` that names the boundary, for example exactly 30 days.
