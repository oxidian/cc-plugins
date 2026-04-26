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

For team-wide Codex usage, install at the consuming repo level by committing a Codex marketplace file and bootstrap script to that repo.

**GitHub-backed repos** should copy:

```text
templates/codex/github/.agents/plugins/marketplace.json  →  <your-repo>/.agents/plugins/marketplace.json
templates/codex/github/scripts/bootstrap-codex-plugins.sh →  <your-repo>/scripts/bootstrap-codex-plugins.sh
```

That enables and installs `ox` and `oxgh` from this repo's generated Codex plugin packages.

**GitLab-backed repos** should copy:

```text
templates/codex/gitlab/.agents/plugins/marketplace.json  →  <your-repo>/.agents/plugins/marketplace.json
templates/codex/gitlab/scripts/bootstrap-codex-plugins.sh →  <your-repo>/scripts/bootstrap-codex-plugins.sh
```

That enables and installs `ox` and `oxgl` from this repo's generated Codex plugin packages.

The marketplace templates use Git-backed `git-subdir` plugin sources with `INSTALLED_BY_DEFAULT`, so each consuming repo stores only the marketplace file and bootstrap script. The bootstrap script starts Codex's app-server and installs any listed plugins that are not already installed and enabled.

Add the bootstrap to your repo setup command:

```make
setup:
	@bash scripts/setup.sh
	@bash scripts/bootstrap-codex-plugins.sh
```

The bootstrap keeps its temporary checkout under:

```text
<your-repo>/.codex/cc-plugins
```

Add `<your-repo>/.codex/` to that repo's `.gitignore`. If you mirror `cc-plugins` to GitLab or want reproducible installs, update each marketplace `source.url` / `source.ref` before committing the template. At runtime, the bootstrap can be overridden with `CODEX_PLUGINS_REPO_URL`, `CODEX_PLUGINS_REPO_REF`, `CODEX_PLUGINS_BOOTSTRAP_DIR`, and `CODEX_PLUGINS`.

With the GitHub template, skills are available in that repo as `$oxgh:open-pr`, `$oxgh:issue`, `$oxgh:triage`, `$oxgh:wait-for-review`, `$oxgh:merge-or-fix`, and `$oxgh:shipit`. With the GitLab template, the equivalent MR-oriented skills are available as `$oxgl:open-mr`, `$oxgl:issue`, `$oxgl:wait-for-review`, `$oxgl:merge-or-fix`, and `$oxgl:shipit`.

For reference, the marketplace file lives at:

```text
<your-repo>/.agents/plugins/marketplace.json
```

and the bootstrap script lives at:

```text
<your-repo>/scripts/bootstrap-codex-plugins.sh
```

For personal/global Codex usage, you can still install or link the generated standalone skills into your Codex home:

```bash
make install-codex PLUGINS=oxgh
# or, for live updates while developing this repo:
make link-codex PLUGINS=oxgh
```

Those user-level installed skills are available from any repo as `$oxgh:open-pr`, `$oxgh:issue`, `$oxgh:triage`, `$oxgh:wait-for-review`, `$oxgh:merge-or-fix`, and `$oxgh:shipit`.

The generated Codex plugin packages under `codex/plugins/` are for Codex plugin marketplace workflows. The repo-local marketplace at `.agents/plugins/marketplace.json` points at those packages when working in this repository.

The generated `ox` Codex plugin also includes PostToolUse and Stop hooks. Configure checks with the same `.claude/ox-hooks.json` file shown below: Codex runs `fast` checks after edits and `slow` checks before it finishes a turn.

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
