---
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wait_for_ai_review.py:*), Bash(glab mr view:*), Bash(glab mr checkout:*), Bash(glab mr merge:*), Bash(glab api:*), Bash(git remote get-url origin)
description: Wait for AI code review on an MR — auto-merge if clean, fix issues if not
disable-model-invocation: true
---

## Context
- Git remote: !`git remote get-url origin`

## Your Task

1. **Get MR number**: Use `$ARGUMENTS` if provided, otherwise detect from current branch with `glab mr view --output json | jq '.iid'`
2. **Checkout MR branch**: Run `glab mr checkout <MR_IID>` to ensure you're on the MR's branch (safe to run even if already on the branch)
3. **Wait for AI review**: Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wait_for_ai_review.py <MR_IID>` (use 45 minute timeout)
4. **Read all MR notes**: Parse the project path from the git remote above, then get the project ID with `glab repo view --output json | jq '.id'` and run `glab api "/projects/{project_id}/merge_requests/<MR_IID>/notes" --jq '[.[] | select(.system == false)]'`
5. **Analyze and respond**:
   - If there are findings: identify the highest priority review comment only. Investigate the codebase to understand that specific issue, then immediately create an implementation plan to fix it using TDD. Do NOT ask the user whether they want to fix the issue - assume they do. Write the full plan directly. Ignore lower priority comments for now.
   - If no findings: auto-merge by running exactly `glab mr merge --when-pipeline-succeeds` (no other flags)
