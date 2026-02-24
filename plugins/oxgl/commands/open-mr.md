---
allowed-tools: Bash(git checkout --branch:*), Bash(git checkout -b:*), Bash(git add:*), Bash(git status:*), Bash(git push:*), Bash(git commit:*), Bash(git log:*), Bash(glab mr create:*)
description: Commit, push, and open a merge request
---

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`

## Commit and MR style

- Use a short commit/MR title (one line, imperative mood) that describes WHAT changed - never meta-messages like "Address review feedback" or "Fix MR comments"
- The commit/MR body should usually be blank - the code should speak for itself
- ONLY add a body to explain NON-OBVIOUS changes that aren't clear from the code
- AVOID summarising or describing what the code does in the MR body - that's redundant. AVOID including test plans.
- If we were working on a known GitLab issue, include "Closes #ISSUE" in the MR body
- See recent commits for examples (ignore bot commits)

## Your task

Based on the above changes:

1. Create a new branch if on main (do NOT add timestamps to branch names)
2. Create a single commit with an appropriate message
3. Push the branch to origin
4. Create a merge request using `glab mr create`
5. You have the capability to call multiple tools in a single response. You MUST do all of the above in a single message. Do not use any other tools or do anything else. Do not send any other text or messages besides these tool calls.
