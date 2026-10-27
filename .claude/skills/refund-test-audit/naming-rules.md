# Test naming rules

A test name is a sentence that says what is true. Someone reading a failure in CI should know the rule that broke without opening the file.

- Start with `test_` and use at least three words after it.
- Name the behaviour or the boundary, not the function: `test_exactly_thirty_days_is_still_on_time`, not `test_window`.
- Do not end the name in a counter (`_1`, `_2`).
- Do not use vague words alone: `test_late`, `test_refund`, `test_works`.
- When a rule has a boundary, name the boundary value in words: "exactly thirty days", "thirty one days".
