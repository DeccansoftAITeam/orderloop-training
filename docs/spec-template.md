# Spec: (feature name)

Status: draft
Risk tier: ?

Copy this file to `docs/specs/<your-feature>.md`, replace every placeholder, and delete these two lines.
`Status` is `draft` until a human approves the spec (then `approved`). `Risk tier` is 1, 2 or 3.

## 1. Problem

What is wrong today, for whom, and what does it cost? Two to four sentences. No solution yet.

## 2. User stories

- US-1: As a (role), I want (goal), so that (benefit).
- US-2: As a (role), I want (goal), so that (benefit).

## 3. Acceptance criteria

One row per testable behaviour. Use the EARS patterns:

| Pattern | Form |
|---|---|
| Always true | The (system) SHALL (response) |
| Event | WHEN (trigger), the (system) SHALL (response) |
| State | WHILE (state), the (system) SHALL (response) |
| Optional feature | WHERE (feature is present), the (system) SHALL (response) |
| Unwanted behaviour | IF (condition), THEN the (system) SHALL (response) |

`Test` is the name of the test function that proves the criterion (`test_...`).
`Package` is the work package that delivers it. `Status` is `todo` or `done`.

| ID | Criterion | Test | Package | Status |
|---|---|---|---|---|
| AC-1 | WHEN (trigger), the (system) SHALL (response) | test_name_here | WP-1 | todo |

## 4. Open questions

Every question needs an owner (a role or a person) and an answer before the spec is approved.

| ID | Question | Owner | Answer |
|---|---|---|---|
| Q-1 | (question) | (owner) | (answer) |

## 5. Design delta

What changes in the system, layer by layer. Only the changes, not a tour of the code.

## 6. Contracts between work packages

The exact signatures, field names and status codes one package hands to another.

## 7. Work packages

Each package owns files that no other package owns.

| ID | Goal | Files | Depends on | Done when |
|---|---|---|---|---|
| WP-1 | (goal) | (path, path) | none | (observable result) |

## 8. Risk and approval gates

Why this tier: (1 cosmetic or docs, 2 business logic, 3 money, customer data or security). Set the number at the top of the file.

Gates (who approves what, and when):

- G1: (gate)
