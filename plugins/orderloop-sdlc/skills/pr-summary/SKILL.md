---
name: pr-summary
description: Summarises the current branch as a pull request description
argument-hint: "[focus]"
disable-model-invocation: true
allowed-tools: Bash(git diff *) Bash(git log *)
---

# Pull request summary

Changed files on this branch:

!`git diff main...HEAD --stat`

Commits on this branch:

!`git log main..HEAD --oneline`

Write a pull request description with three sections: **What changed**, **Why**, **How to test**. Keep it under 150 words. Extra focus from the user: $ARGUMENTS
