# boom launch and local plugin updates

## Behavior

- Preserve native CLI permission defaults. Explicit `--unsafe` retains the previous bypass behavior; `--safe` remains compatible.
- Use private temporary Claude settings without overwriting global user settings. Official profiles preserve native authentication and user plugin discovery while masking inherited provider credentials. Respect `CLAUDE_CONFIG_DIR` and clean temporary files after errors or handled cancellation.
- Register trusted local repositories with `boom plugins add`. Run their sync adapters before launch in the selected Claude or Codex environment. Preserve native stdin/stdout, bound sync execution, stop startup on failure, and support `--no-plugin-sync`.
- Keep quota results unknown when fields are missing or invalid, display returned window durations, and deduplicate shared session usage.
- Protect backup and staging files during default cleanup, handle unusual filenames, and reject invalid profile names.
- Find Codex through an explicit override, PATH, then known installation locations.
- New subscription profiles retain general preferences while resetting provider/model selection and API login restrictions. Existing profiles are not migrated.
- Edit API configuration by TOML statement scope, preserving other providers, nested settings, comments and multiline values. Inline provider tables are rejected without rewriting the configuration.
- Remove the old Claude profile after a successful rename, and count Codex cached input tokens once.

## Verification

- Bash syntax and Git whitespace checks pass.
- The offline suite covers launch isolation, plugin synchronization, PATH discovery, subscription routing, TOML editing, profile renaming, and cached token totals. Three opt-in native CLI checks cover plugin discovery and configuration loading.
- Native checks use Claude Code 2.1.296 and Codex CLI 0.162.1 with isolated homes and synthetic authentication. They exercise plugin discovery, auth status and the edited configuration without model requests or real account credentials.
- Real model execution, full interactive terminal behavior, and Intel/Linux hosts are outside these checks.

Run the offline suite with Python 3.11+:

```bash
python3 -m unittest discover -s tests -v
```

To include the isolated native Claude and Codex checks:

```bash
BOOM_TEST_REAL_CLAUDE="$(command -v claude)" \
BOOM_TEST_REAL_CODEX="$(command -v codex)" \
python3 -m unittest discover -s tests -v
```

## Upgrade and rollback

Start a new CLI session after updating installed plugins. Existing sessions retain their loaded context. Local synchronization requires a repository-provided adapter and registration; direct native CLI launches do not run the boom hook.

To roll back the launcher, restore the previous committed `boom` file and reinstall it if using a copied installation. Plugin registrations and installed caches live outside the source repository; manage them separately using `boom plugins remove` and native plugin commands. Restoring an older launcher may also restore its previous permission and settings behavior.
