---
name: commit
description: Commit changes with a clean commit message
---

## Context

First, run these commands and review their output:

- Current git status: `git status`
- Current git diff (staged and unstaged changes): `git diff HEAD`
- Current branch: `git branch --show-current`
- Recent commits: `git log --oneline -10`

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
3. Execute each step as a separate command. Do NOT chain commands with && or ;.