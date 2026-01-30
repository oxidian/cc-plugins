---
allowed-tools: Bash(gh issue create:*), Bash(gh api:*), Bash(gh project:*), Bash(gh repo view:*)
description: Create GitHub Issue
---

## Context

- Current repo: !`gh repo view --json nameWithOwner --jq '.nameWithOwner'`

## Issue types

Issue types (Bug, Feature, Task) are NOT labels - they're a separate GitHub feature. The `gh` CLI doesn't support them directly yet, so use the REST API:

```bash
gh api -X PATCH repos/{owner}/{repo}/issues/{number} --field type=Bug
```

Valid types: `Bug`, `Feature`, `Task`

## Linking as a subissue

To make an issue a subissue of a parent, get the numeric ID (not the issue number) and POST it:

```bash
gh api repos/{owner}/{repo}/issues/{child_number} --jq '.id'
# Returns: 3860943964

echo '{"sub_issue_id": 3860943964}' | gh api -X POST repos/{owner}/{repo}/issues/{parent_number}/sub_issues --input -
```

The sub_issues endpoint requires the numeric ID as an integer in JSON, hence piping through `--input -`.

## Inheriting from parent issue

When creating a subissue, it should have the same milestone and project triage as its parent.

### Get parent issue milestone

```bash
gh api repos/{owner}/{repo}/issues/{parent_number} --jq '.milestone.number // empty'
```

### Get parent issue project fields

First get the parent's project item ID:

```bash
gh project item-list {project_number} --owner {owner} --limit 300 --format json | jq '.items[] | select(.content.number == PARENT_NUMBER) | {id, component: .component, priority: .priority, size: .size}'
```

### Set milestone on new issue

```bash
gh api -X PATCH repos/{owner}/{repo}/issues/{number} --field milestone={milestone-number}
```

### Set project fields on new issue

First get the new issue's project item ID (issue must be added to project first):

```bash
gh project item-list {project_number} --owner {owner} --limit 300 --format json | jq '.items[] | select(.content.number == NEW_ISSUE_NUMBER) | .id'
```

Then copy each field using the option IDs from context:

```bash
gh project item-edit --id {item-id} --project-id {project-id} --field-id {field-id} --single-select-option-id {option-id}
```

## Your task

Based on the user's request:

1. If a parent issue was specified, fetch its milestone and project fields first
2. Create the issue with `gh issue create --title "..." --body "..."`
3. Set the issue type using the API
4. If a parent issue was specified:
   - Link it as a subissue
   - Copy the parent's milestone (if set)
   - Copy the parent's project triage (component, priority, size)
5. You have the capability to call multiple tools in a single response. Chain independent calls together. Do not send any other text or messages besides these tool calls.
