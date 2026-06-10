---
allowed-tools: Bash(git checkout --branch:*), Bash(git checkout -b:*), Bash(git add:*), Bash(git status:*), Bash(git diff:*), Bash(git commit:*), Bash(git log:*)
description: Commit changes with a clean commit message
model: haiku
---

## Context

- Current git status: !`git status --porcelain`
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`

You usually already know what changed in this session. If you are unsure what the changes are, run `git diff HEAD` (or a targeted `git diff HEAD -- <file>`) before committing.

## Commit style

- Use a short commit message (one line, imperative mood) that describes WHAT changed - never meta-messages like "Address review feedback" or "Fix PR comments"
- The commit body should usually be blank - the code should speak for itself
- ONLY add a body to explain NON-OBVIOUS changes that aren't clear from the code
- Do NOT repeat or describe what the code does - that's redundant
- Do NOT prepend commit messages with "RED", "GREEN", or other TDD phase labels - just describe the change
- See recent commits for examples (ignore dependabot and github-actions commits)

## Your task

Based on the above changes:

1. Create a new branch if on main (do NOT add timestamps to branch names)
2. Create a single commit with an appropriate message
3. You have the capability to call multiple tools in a single response. You MUST do the above in a single message using separate tool calls for each command. Do NOT chain commands with && or ;. Apart from an optional `git diff` to understand the changes first, do not use any other tools or do anything else. Do not send any other text or messages besides these tool calls.
