# Pull request: Add 5% goodwill credit for late deliveries

Branch: `flawed-pr`. Author: a teammate who used an AI assistant. You are the reviewer.

## Description from the author

Support wants to give a customer a small credit when their order arrived late.

- New endpoint `POST /orders/{id}/goodwill-credit` records a credit of 5% of the order total as a refund.
- Refund creation now writes a log line so support can trace a refund back to the customer.
- Small tidy-up of the late-window check.
- No new dependencies.
- Tests: no test was changed, all 19 pass.

## What the team requires of every change

1. Money is integer cents everywhere. No floats.
2. Customer name, email, phone, address and refund reasons never go to logs.
3. Any endpoint that creates a refund requires an `Idempotency-Key` and never creates the same refund twice.
4. No new dependency unless the task asked for it and a person approved it.
5. A change to a rule moves its test with a stated reason. An existing test is never loosened to make a build pass.
6. Every name the code calls must exist in this repository or in a declared dependency.
7. New behaviour comes with tests.
