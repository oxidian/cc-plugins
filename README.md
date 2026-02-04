# Oxidian Claude Marketplace

A Claude Code plugin marketplace providing commit workflows, code quality hooks, and platform-specific commands for Oxidian projects.

## Plugins

| Plugin | Purpose |
|--------|---------|
| [**ox**](plugins/ox/) | Base plugin — commit command, code quality hooks, auto-format and checks |
| [**oxgh**](plugins/oxgh/) | GitHub workflow — PR, issue, triage, review, and merge commands |
| [**oxgl**](plugins/oxgl/) | GitLab workflow — MR, issue, review, and merge commands |

## Installation

### 1. Add the marketplace to your project

Add to `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "oxidian": {
      "source": {
        "source": "git",
        "url": "git@github.com:oxidian/cc-plugins.git"
      }
    }
  },
  "enabledPlugins": {
    "ox@oxidian": true,
    "oxgh@oxidian": true
  }
}
```

Enable whichever plugins you need:
- `ox@oxidian` — Base plugin (recommended)
- `oxgh@oxidian` — GitHub workflows
- `oxgl@oxidian` — GitLab workflows

### 2. Auto-updates

Plugins do not auto-update by default. To enable auto-updates, use the Claude Code interface (`/plugins` command) to configure update settings.

### 3. Configure hooks (ox plugin)

Create `.claude/ox-hooks.json` to configure the check commands that run before Claude stops:

**Single project:**
```json
{
  "checks": [
    {
      "fast": "make format",
      "slow": "make check"
    }
  ]
}
```

**Monorepo with scoped commands:**
```json
{
  "checks": [
    {
      "directory": "packages/api",
      "fast": "npm run lint --fix",
      "slow": "npm test"
    },
    {
      "directory": "packages/web",
      "fast": "npm run lint --fix",
      "slow": "npm test"
    }
  ]
}
```

See [.claude/ox-hooks.json](.claude/ox-hooks.json) for a working example.

### 4. Prerequisites

- **oxgh**: Requires the [GitHub CLI](https://cli.github.com/) (`gh`)
- **oxgl**: Requires the [GitLab CLI](https://gitlab.com/gitlab-org/cli) (`glab`)
