# Refund rule checklist

- [ ] The boundary has a test (exactly at the limit, and one step either side)
- [ ] No floats: amounts are integer cents
- [ ] No `datetime.now()` inside a rule
- [ ] The reason text is not logged or sent anywhere
- [ ] Existing tests that depend on the old rule were updated on purpose, and the diff says why
