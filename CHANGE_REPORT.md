# boom launch and local plugin updates

## Behavior

- Preserve native CLI permission defaults. Explicit `--unsafe` retains the previous bypass behavior; `--safe` remains compatible.
- Use private temporary Claude settings without overwriting global user settings. Official profiles preserve native authentication and user plugin discovery while masking inherited provider credentials. Respect `CLAUDE_CONFIG_DIR` and clean temporary files after errors or handled cancellation.
- Register trusted local repositories with `boom plugins add`. Run their sync adapters before launch in the selected Claude or Codex environment. Preserve native stdin/stdout, bound sync execution, stop startup on failure, and support `--no-plugin-sync`.
- Keep quota results unknown when fields are missing or invalid, display returned window durations, and deduplicate shared session usage.
- Protect backup and staging files during default cleanup, handle unusual filenames, and reject invalid profile names.

## Verification

- Bash syntax and Git whitespace checks pass.
- 24 regression tests pass, including two opt-in native Claude checks with isolated homes. Fake CLI and HTTP fixtures cover permissions, settings, cleanup, quota parsing, usage deduplication, plugin sync and cancellation.
- Native Claude checks exercise plugin discovery and authentication status using synthetic settings. They do not make model requests or use real account credentials.
- Real model execution and full interactive terminal behavior are outside these checks.

Run the offline suite with:

```bash
python3 -m unittest discover -s tests -v
```

To include the isolated native Claude checks:

```bash
BOOM_TEST_REAL_CLAUDE="$(command -v claude)" python3 -m unittest discover -s tests -v
```

## Upgrade and rollback

Start a new CLI session after updating installed plugins. Existing sessions retain their loaded context. Local synchronization requires a repository-provided adapter and registration; direct native CLI launches do not run the boom hook.

To roll back the launcher, restore the previous committed `boom` file and reinstall it if using a copied installation. Plugin registrations and installed caches live outside the source repository; manage them separately using `boom plugins remove` and native plugin commands. Restoring an older launcher may also restore its previous permission and settings behavior.
