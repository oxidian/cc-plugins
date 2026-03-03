---
allowed-tools: Bash(glab issue create:*), Bash(glab issue update:*), Bash(glab api:*), Bash(glab repo view:*)
description: Create GitLab Issue
disable-model-invocation: true
---

## Context

- Current project: !`glab repo view --output json | jq -r '.path_with_namespace'`

## Issue type labels

GitLab uses scoped labels for issue types. Add the appropriate label when creating or updating an issue:

```bash
glab issue update {number} --label "type::bug"
```

Valid type labels: `type::bug`, `type::feature`, `type::task`

## Linking issues

To link an issue as related to a parent, use the issue links API. First get the project ID:

```bash
glab repo view --output json | jq '.id'
```

Then create the link:

```bash
glab api --method POST "/projects/{project_id}/issues/{child_iid}/links" -f target_project_id={project_id} -f target_issue_iid={parent_iid} -f link_type=is_blocked_by
```

Link types: `relates_to`, `blocks`, `is_blocked_by`

## Inheriting from parent issue

When creating a linked issue, it should have the same milestone and labels as its parent.

### Get parent issue labels and milestone

```bash
glab api "/projects/{project_id}/issues/{parent_iid}" --jq '{labels, milestone: .milestone.title}'
```

### Set labels on new issue

```bash
glab issue update {number} --label "type::bug" --label "component::backend" --label "priority::high"
```

### Set milestone on new issue

```bash
glab issue update {number} --milestone "Sprint 42"
```

## Your task

Based on the user's request:

1. If a parent issue was specified, fetch its labels and milestone first
2. Create the issue with `glab issue create --title "..." --description "..."`
3. Add the type label using `glab issue update {number} --label "type::..."`
4. If a parent issue was specified:
   - Link it using the issue links API
   - Copy the parent's scoped labels (component, priority, size)
   - Copy the parent's milestone (if set)
5. You have the capability to call multiple tools in a single response. Chain independent calls together. Do not send any other text or messages besides these tool calls.
