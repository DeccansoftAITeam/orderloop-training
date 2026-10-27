---
name: refund-test-audit
description: Audits the names of the OrderLoop backend tests and reports the ones that do not state the behaviour they check. Use when asked to audit, review or clean up test names or test quality for the refund rules.
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/list_rule_tests.py *)
disallowed-tools: Edit Write
---

# Refund test audit

Key rules (read these first):

- This skill only reports. Do not rename or edit anything while it runs.
- Run the script. Do not judge test names by eye.
- A test name must state the behaviour, using the rules in `naming-rules.md` in this folder.

## Steps

1. Run `python ${CLAUDE_SKILL_DIR}/scripts/list_rule_tests.py backend/tests` and read its output.
2. For each `WEAK` line, read the test body and write one proposed new name that follows `naming-rules.md`.
3. Report a table: current name, file, proposed name. If the script printed no `WEAK` line, say so and stop.
