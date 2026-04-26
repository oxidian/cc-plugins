# Oxidian Claude Marketplace

A Claude Code plugin marketplace providing commit workflows, code quality hooks, and platform-specific commands for Oxidian projects.

## Quickstart

```
cd your-project/
claude
> Install github.com/oxidian/cc-plugins in this project following instructions in the README
```

## Plugins

| Plugin | Purpose |
|--------|---------|
| [**ox**](plugins/ox/) | Base plugin — commit skill, code quality hooks, auto-format and checks |
| [**oxgh**](plugins/oxgh/) | GitHub workflow — PR, issue, triage, review, and merge skills |
| [**oxgl**](plugins/oxgl/) | GitLab workflow — MR, issue, review, and merge skills |

## Installation

### Codex

Claude Code skills remain the source of truth under `plugins/*/skills`. Codex-compatible copies are generated separately so Claude-specific syntax like `!git status` stays intact.

Generate Codex copies:

```bash
make codex
```

Start Codex with local generated skills linked into the repo:

```bash
make dev-codex
```

`make codex` writes:

```text
codex/skills/              # standalone global skills, namespaced as oxgh:open-pr
codex/plugins/             # Codex plugin packages with .codex-plugin/plugin.json
.agents/plugins/           # repo-local Codex marketplace for this plugin repo
```

`make dev-codex` also creates ignored `.agents/skills/` symlinks so Codex can see the local generated skills while developing this repo.

For team-wide Codex usage, install at the consuming repo level by committing a Codex marketplace file to that repo.

**GitHub-backed repos** should copy [templates/codex/github/.agents/plugins/marketplace.json](templates/codex/github/.agents/plugins/marketplace.json) to:

```text
<your-repo>/.agents/plugins/marketplace.json
```

That enables `ox` and `oxgh` from this repo's generated Codex plugin packages.

**GitLab-backed repos** should copy [templates/codex/gitlab/.agents/plugins/marketplace.json](templates/codex/gitlab/.agents/plugins/marketplace.json) to:

```text
<your-repo>/.agents/plugins/marketplace.json
```

That enables `ox` and `oxgl` from this repo's generated Codex plugin packages.

The templates use Git-backed `git-subdir` plugin sources, so each consuming repo stores only the small marketplace file. If you mirror `cc-plugins` to GitLab or want reproducible installs, update each `source.url` and pin `source.ref` to a tag or commit SHA before committing the template.

With the GitHub template, skills are available in that repo as `$open-pr`, `$issue`, `$triage`, `$wait-for-review`, `$merge-or-fix`, and `$shipit`. With the GitLab template, the equivalent MR-oriented skills are available from `oxgl`.

For personal/global Codex usage, you can still install or link the generated standalone skills into your Codex home:

```bash
make install-codex PLUGINS=oxgh
# or, for live updates while developing this repo:
make link-codex PLUGINS=oxgh
```

Those user-level installed skills are available from any repo as `$oxgh:open-pr`, `$oxgh:issue`, `$oxgh:triage`, `$oxgh:wait-for-review`, `$oxgh:merge-or-fix`, and `$oxgh:shipit`.

The generated Codex plugin packages under `codex/plugins/` are for Codex plugin marketplace workflows. The repo-local marketplace at `.agents/plugins/marketplace.json` points at those packages when working in this repository.

### Claude Code

#### 1. Add the marketplace to your project

Add to `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "oxidian": {
      "source": {
        "source": "git",
        "url": "https://github.com/oxidian/cc-plugins.git"
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

#### 2. Auto-updates

Plugins do not auto-update by default. To enable auto-updates, use the Claude Code interface (`/plugins` command) to configure update settings.

#### 3. Configure hooks (ox plugin)

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

#### 4. Prerequisites

- **oxgh**: Requires the [GitHub CLI](https://cli.github.com/) (`gh`)
- **oxgl**: Requires the [GitLab CLI](https://gitlab.com/gitlab-org/cli) (`glab`)
