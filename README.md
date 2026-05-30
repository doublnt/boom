# boom

A unified launcher for [Claude Code](https://claude.ai/code) and [Codex](https://github.com/openai/codex) that manages multiple named profiles — useful when you have several API accounts, providers, or subscription plans.

## Features

- **Multiple profiles** — switch between different API keys, base URLs, and models with a named shortcut
- **Common settings** — share a `common.json` base config across all Claude profiles, with per-profile overrides
- **Quota dashboard** — `boom status` fetches live usage from Claude (official + MiniMax), Codex, and shows quota windows
- **Token usage** — `boom usage` scans local session files for Claude, Codex, and Gemini token counts
- **Safe defaults** — automatically adds `--dangerously-skip-permissions` / `--dangerously-bypass-approvals-and-sandbox`; pass `--safe` to disable

## Requirements

- **bash** 3.2+
- **node** (any recent version; used for JSON merging and status display)
- **jq** (only for `boom claude show`)
- Claude Code CLI and/or Codex CLI installed separately

## Installation

```bash
git clone https://github.com/doublnt/boom.git
cd boom
bash install.sh
```

By default the script is installed to `~/.local/bin/boom`. Override with:

```bash
BOOM_INSTALL_DIR=/usr/local/bin bash install.sh
```

Or just copy the `boom` file somewhere on your `PATH` and `chmod +x` it.

## Quick start

```bash
# Add a Claude profile (third-party provider via OpenAI-compatible endpoint)
boom claude add myplan

# Set it as the default
boom claude default myplan

# Launch Claude with the default profile
boom claude

# Launch with a specific profile
boom claude myplan

# Check quota across all accounts
boom status

# Show token usage breakdown
boom usage
```

## Configuration

boom stores everything under `~/.boom/` (override with `$BOOM_HOME`):

```
~/.boom/
  claude/
    common.json          # merged into every Claude profile
    default              # name of the default profile
    profiles/
      myplan.json        # per-profile settings (env vars, model, etc.)
  codex/
    default
    profiles/
      myaccount/         # per-profile Codex home directory
        config.toml
        auth.json
    shared/
      sessions/          # shared across all Codex profiles
      history.jsonl
```

### Claude profiles

Each file in `claude/profiles/` is a Claude Code settings JSON. The `env` block sets environment variables before launching Claude:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://your-provider/v1",
    "ANTHROPIC_AUTH_TOKEN": "sk-...",
    "ANTHROPIC_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-sonnet-4-5",
    "CLAUDE_CODE_SUBAGENT_MODEL": "claude-sonnet-4-5",
    "API_TIMEOUT_MS": "600000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  }
}
```

`common.json` is deep-merged first; profile keys override common ones.

Profiles that point to the official Anthropic API (no custom `ANTHROPIC_BASE_URL`) are launched via a temporary `~/.claude/settings.json` swap instead of `--settings`, so Claude's own auth flow works normally.

### Codex profiles

Each directory in `codex/profiles/` is an isolated `CODEX_HOME`. Sessions and history are symlinked to a shared location so `/resume` works across profiles.

## Commands

```
boom claude [name] [--safe] [--no-profile] [-- <claude args>]
boom c      [name] [...]

boom codex  [name] [--safe] [--no-profile] [-- <codex args>]
boom x      [name] [...]
```

### Claude management

| Command | Description |
|---|---|
| `boom claude add <name>` | Create a new profile (interactive) |
| `boom claude edit [name]` | Edit an existing profile |
| `boom claude show [name]` | Print merged settings JSON |
| `boom claude list` | List all profiles |
| `boom claude default <name>` | Set the default profile |
| `boom claude remove <name>` | Delete a profile |
| `boom claude doctor` | Check installation health |

### Codex management

| Command | Description |
|---|---|
| `boom codex add <name>` | Create profile and run `codex login` |
| `boom codex edit [name]` | Rename or re-login |
| `boom codex list` | List all profiles |
| `boom codex default <name>` | Set the default profile |
| `boom codex remove <name>` | Delete a profile |
| `boom codex doctor` | Check installation health |

### Other commands

| Command | Description |
|---|---|
| `boom status` | Fetch live quota from Claude / Codex APIs |
| `boom usage` | Aggregate token usage from local session files |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `BOOM_HOME` | `~/.boom` | Root directory for all boom data |
| `BOOM_REAL_CLAUDE` | auto-detected | Path to the real `claude` binary |
| `BOOM_REAL_CODEX` | `/opt/homebrew/bin/codex` | Path to the real `codex` binary |

## License

MIT
