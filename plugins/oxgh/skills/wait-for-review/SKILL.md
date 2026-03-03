---
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wait_for_ai_review.py:*), Bash(gh pr view:*), Bash(gh pr checkout:*), Bash(gh api:*), Bash(git remote get-url origin)
description: Wait for AI code review on a PR, analyze findings, and offer to address issues
disable-model-invocation: true
---

## Context
- Git remote: !`git remote get-url origin`

## Your Task

1. **Get PR number**: Use `$ARGUMENTS` if provided, otherwise detect from current branch with `gh pr view --json number --jq '.number'`
2. **Checkout PR branch**: Run `gh pr checkout <PR_NUMBER>` to ensure you're on the PR's branch (safe to run even if already on the branch)
3. **Wait for AI review**: Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wait_for_ai_review.py <PR_NUMBER>` (use 45 minute timeout)
4. **Read all PR comments**: Parse the owner/repo from the git remote above, then run `gh api repos/{owner}/{repo}/issues/<PR_NUMBER>/comments`
5. **Analyze and respond**:
   - If there are findings: identify the highest priority review comment only. Investigate the codebase to understand that specific issue, then immediately create an implementation plan to fix it using TDD. Do NOT ask the user whether they want to fix the issue - assume they do. Write the full plan directly. Ignore lower priority comments for now.
   - If no findings: report success
