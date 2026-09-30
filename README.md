# boom

A unified launcher for [Claude Code](https://claude.ai/code) and [Codex](https://github.com/openai/codex) that manages multiple named profiles — useful when you have several API accounts, providers, or subscription plans.

## Features

- **Multiple profiles** — switch between different API keys, base URLs, and models with a named shortcut
- **Common settings** — share a `common.json` base config across all Claude profiles, with per-profile overrides
- **Quota dashboard** — `boom status` fetches live usage from Claude (official + MiniMax), Codex, and shows quota windows
- **Token usage** — `boom usage` scans local session files for Claude, Codex, and Gemini token counts
- **Native permission defaults** — preserves the CLI's own permissions; only explicit `--unsafe` adds a dangerous bypass. `--safe` remains supported.
- **Local plugin development** — opt in once per repository; changed skills sync before the next launch in the selected CLI environment.

## Requirements

- **bash** 3.2+
- **node** 18+ (JSON merging and built-in fetch for quota queries)
- **jq** (only for `boom claude show`)
- Claude Code CLI and/or Codex CLI installed separately
- Python 3.11+ for registered local plugin sync adapters

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
# Add a Claude profile (a provider that supports Claude Code's Anthropic protocol)
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

Official profiles have no custom provider, API credential or apiKeyHelper. They use a mode-0600 temporary `--settings` file, preserving native login and user/project settings, including user plugins and skills. They never overwrite `~/.claude/settings.json`. Common provider credentials/aliases are removed; inherited user provider values are masked in the temporary settings (respecting `CLAUDE_CONFIG_DIR`), while explicit model selections in the profile remain. Managed policy still applies. Temporary files are cleaned on completion, error and handled cancellation. SIGKILL cannot run cleanup.

Third-party profiles also use temporary `--settings`, with their explicit provider configuration. A profile's model name alone does not make it a third-party account. Neither route is an OS sandbox; `--safe` means boom does not inject bypass flags, not that every setting or plugin is isolated.

Use `--no-profile` to inherit native CLI login/settings without applying boom's common or named configuration. It does not change accounts or log in. The native CLI may still read its own configuration.

### Codex profiles

Each directory in `codex/profiles/` is an isolated `CODEX_HOME`. Sessions and history are symlinked to a shared location so `/resume` works across profiles.

Plugin caches are also per profile. Updating native Codex does not update a boom profile. Inspect the environment you actually launch:

```bash
boom c -- plugin list --json
boom x -- plugin list --json
```

To refresh a marketplace plugin explicitly, run `boom x -- plugin add NAME@MARKETPLACE`, or `boom x PROFILE -- plugin add NAME@MARKETPLACE` for a named profile. For registered local repositories, the development mode below handles synchronization before launch. Start a new CLI session after refreshing. Claude skills-directory links read their source directly and need no reinstall.

### Local plugin development

Register the trusted source repository once:

```bash
boom plugins add ~/plugins/any-agent-skills
boom plugins list
```

Then edit the skill source and launch `boom c` or `boom x` normally. Boom invokes the repository's `scripts/sync-local-plugins.py --target claude|codex --ensure` adapter before the CLI starts. Registration authorizes executing that adapter on future launches; repositories without the adapter are rejected. The adapter returns JSON with `schema_version: 1`, `status: "ready"`, `updated: boolean`, and `version: string`.

The Any Agent Skills adapter compares source content and the actual installed cache. An unchanged startup runs no native install commands. Changed content gets an immutable snapshot and updates only the environment being launched: Claude uses `CLAUDE_CONFIG_DIR`, Codex uses the selected profile's `CODEX_HOME`, and `--no-profile` uses the native environment. Accounts, provider settings and permissions remain separate. Concurrent syncs serialize their writes; old snapshots and existing sessions are retained.

Native installers can prune previous cache versions. The adapter retains their contents and restores old resource paths after the update, including failed updates. A durable journal recovers unfinished restoration on the next launch after a hard interruption. Retained caches live under `~/.local/share/any-agent-skills/retained-cache/`, deduplicated by content; they and snapshots occupy disk space until explicitly removed.

Updates are reported on stderr, leaving stdin and native JSON stdout intact. Sync failure stops startup; the sync adapter has a two-minute deadline and cancellation terminates its owned process group. Version/help, auth/login, plugin management, MCP/app-server commands, and Codex `--ignore-user-config` calls skip synchronization. Direct native CLI launches do not pass through this hook.

```bash
boom x --no-plugin-sync -- exec "..."    # skip sync for this launch
boom plugins remove any-agent-skills     # stop auto sync; retain installed copies
```

## Commands

```
boom claude [name] [--safe|--unsafe] [--no-profile] [-- <claude args>]
boom c      [name] [...]

boom codex  [name] [--safe|--unsafe] [--no-profile] [-- <codex args>]
boom x      [name] [...]

boom plugins add <local-repository>
boom plugins list
boom plugins remove <plugin-name>
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
| `boom status --claude --official` | Query only the native Claude subscription |
| `boom status --codex --official` | Query only the native Codex ChatGPT login, using CODEX_HOME when set |
| `boom usage` | Aggregate token usage from local session files |
| `boom clean --dry-run` | Preview selected logs / .DS_Store cleanup |

Quota windows use the returned duration and display **remaining** percentages. Null/malformed values are unknown, not 100% remaining. Claude's returned `seven_day_*` buckets are shown by their provider names, without guessing model mappings. Failed quota queries return nonzero while still displaying other providers. `status` uses best-effort subscription endpoints; it does not refresh authentication, buy/reset quota, or make model calls. A custom CLAUDE_CONFIG_DIR uses that directory's credential file, without falling back to the default keychain account.

`usage` is a local token estimate, not remaining quota or cash spend. Shared Codex session paths are deduplicated before both token and file counts. Existing compact k/M/B display is retained.

`clean` excludes backup files and synchronization staging by default. Include them only with `--include-backups` / `--include-staging`, after stopping affected CLIs and checking whether backups are needed. `--yes` skips its prompt, not this responsibility. No cleanup runs at launch or during status queries.

## CLI compatibility checked 2026-09-29

Checked against Claude Code **2.1.284** and Codex CLI **0.158.0**. These are inspected versions, not requirements to upgrade. Read-only help/auth checks and fake-process tests do not certify real model availability or full sandbox isolation.

| Old or ambiguous usage | Current usage |
|---|---|
| Assuming bare `boom c` / `boom x` bypasses permissions | Native permissions now apply; explicitly use `--unsafe` only when intended |
| `boom c profile list` | Removed; use `boom c list` (and `boom x list`) |
| `boom c -p "prompt"` | `-p` before `--` selects a boom profile; print mode is `boom c --no-profile -- -p "prompt"` |
| Claude `--permission-mode default` | Local help now lists `manual`; unattended deny-on-prompt uses `dontAsk --permission-prompts none` |
| Codex `exec --full-auto` | Current parser rejects it; `--approve-for-me` is available for native automatic approval, with different semantics; explicit sandbox/approval config is preferable for scripts |
| `codex sandbox macos -- …` | Current syntax is `codex sandbox -- COMMAND…` |
| Codex `preferred_auth_method` config | Not in the current reference; boom no longer emits it; no automatic migration of existing account configs |
| Claude `--bare` to minimize a subscription call | Current help says bare does not read OAuth/keychain; use appropriate restricted settings instead of changing billing routes |

`claude --restricted`, `--tools`, `--strict-mcp-config`, `--resume SESSION_ID`; Codex `exec --json`, `--ignore-user-config`, `exec resume SESSION_ID` and `app-server` remain available in local help. `--ignore-rules` still exists but skips execpolicy rules; it is unrelated to AGENTS.md loading and is not required by boom.

Native options should follow `--` so their values cannot be mistaken for profile names. Example read-only checks:

```bash
boom c --safe --no-profile -- --version
boom x --safe --no-profile -- --version
boom c --safe --no-profile -- auth status
boom x --safe --no-profile -- login status
python3 -m unittest discover -s tests -v
```

The test suite uses a disposable HOME, fake CLIs and HTTP fixtures; it never contacts models or touches real account settings. See [CHANGE_REPORT.md](CHANGE_REPORT.md) for this update's verification and rollback details. References: [Claude CLI](https://code.claude.com/docs/en/cli-reference), [Claude settings](https://code.claude.com/docs/en/settings), [Codex config](https://learn.chatgpt.com/docs/config-file/config-reference).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `BOOM_HOME` | `~/.boom` | Root directory for all boom data |
| `BOOM_REAL_CLAUDE` | auto-detected | Path to the real `claude` binary |
| `BOOM_REAL_CODEX` | `/opt/homebrew/bin/codex` | Path to the real `codex` binary |

## License

MIT
