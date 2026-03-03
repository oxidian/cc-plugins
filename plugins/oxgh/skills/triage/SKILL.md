---
allowed-tools: Bash(gh project:*), Bash(gh issue view:*), Bash(gh api:*)
description: Triage a GitHub issue (set component, priority, size, milestone)
disable-model-invocation: true
---

## Context

- Current repo: !`gh repo view --json nameWithOwner --jq '.nameWithOwner'`

## Getting the item ID

To set project fields, you need the project item ID (not the issue number):

```bash
gh project item-list {project_number} --owner {owner} --limit 300 --format json | jq '.items[] | select(.content.number == ISSUE_NUMBER) | .id'
```

## Setting a project field

```bash
gh project item-edit --id {item-id} --project-id {project-id} --field-id {field-id} --single-select-option-id {option-id}
```

## Issue types

Check if an issue type is set:

```bash
gh api repos/{owner}/{repo}/issues/{number} --jq '.type.name // empty'
```

Set an issue type (only if not already set):

```bash
gh api -X PATCH repos/{owner}/{repo}/issues/{number} --field type=Bug
```

Valid types: `Bug`, `Feature`, `Task`

## Parent issues

Find an issue's parent (for sub-issues):

```bash
gh api graphql -f query='
{
  repository(owner: "{owner}", name: "{repo}") {
    issue(number: ISSUE_NUMBER) {
      parent {
        number
        title
      }
    }
  }
}'
```

Get the parent's project fields (to copy them):

```bash
gh project item-list {project_number} --owner {owner} --limit 300 --format json | jq '.items[] | select(.content.number == PARENT_NUMBER)'
```

## Milestones

Check current milestone:

```bash
gh api repos/{owner}/{repo}/issues/{number} --jq '.milestone.title // empty'
```

Set a milestone (use the milestone number, not title):

```bash
gh api -X PATCH repos/{owner}/{repo}/issues/{number} --field milestone={milestone-number}
```

## Your task

Based on the user's request:

1. View the issue to understand its scope: `gh api repos/{owner}/{repo}/issues/{number} --jq '{title, body, type: .type.name}'`
2. Get the project item ID for the issue
3. Determine appropriate Component, Priority, Size, and Type (if not set) based on the issue content
4. Set all project fields using `gh project item-edit`
5. If the issue type is not set, set it using `gh api -X PATCH`
6. If the user specified a milestone in their request, set it using `gh api -X PATCH`
7. You have the capability to call multiple tools in a single response. Chain independent calls together.
