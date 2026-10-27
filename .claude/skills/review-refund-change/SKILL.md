---
name: review-refund-change
description: Reviews the current branch's changes to the OrderLoop refund rules in a separate, read-only context. Use when asked to review a refund rule change before a pull request.
disable-model-invocation: true
context: fork
agent: Explore
background: false
allowed-tools: Bash(git diff *) Bash(git log *)
---

# Review a refund rule change

You are reviewing, not fixing. You cannot see the earlier conversation, so everything you need is below.

Files changed on this branch compared with `main`:

!`git diff main...HEAD --stat`

Full diff of the refund rules and their tests:

!`git diff main...HEAD -- backend/app/rules.py backend/tests`

Review against these points and report each as OK, problem, or not applicable:

1. Every boundary changed in `rules.py` has a test at the boundary and one step either side.
2. Money stays in integer cents; no floats.
3. No `datetime.now()` inside a rule; `now` is a parameter.
4. No test was loosened or deleted to make the change pass.

Finish with a verdict of at most three lines: ready, or the first thing to fix. Focus requested by the user: $ARGUMENTS
