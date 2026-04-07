# Troubleshooting Notes

## Codex auth JSON exists but does not load in CCS

### Symptom

- A file exists under `C:\Users\admin\.ccs\cliproxy\auth`
- The token can still work against OpenAI APIs
- But the account does not appear in the CCS control panel or `CLIProxyAPI`
  auth list

### Root cause

- The CCS control panel is an embedded `CLIProxyAPI` management page, not a raw
  directory listing.
- `CLIProxyAPI` loads auth files by parsing JSON in Go.
- Some exported Codex auth files were saved with a UTF-8 BOM prefix
  (`EF BB BF`).
- Go's JSON parser does not accept that prefix in this path, so those auth
  files were silently skipped during load/synthesis.

### Why this was confusing

- The broken files still looked normal in editors.
- Token validity was not the problem.
- `accounts.json` in `.ccs\cliproxy` could still contain the account, while the
  runtime auth manager ignored the auth JSON itself.
- `disabled: false` was necessary, but not sufficient. A file could still fail
  to load if it started with BOM bytes.

### Confirmed behavior

- Before removing BOM: file missing from `/v0/management/auth-files`
- After removing BOM only: same file appeared in `/v0/management/auth-files`
- Some older valid files still stayed missing until they were rewritten once.
  Rewriting the same JSON content triggered the watcher `write` path and caused
  those files to appear immediately.

### Recovery

1. Scan `C:\Users\admin\.ccs\cliproxy\auth` for BOM-prefixed `codex-*.json`
   files.
2. Remove the first three bytes only when they are `EF BB BF`.
3. Refresh the CCS control panel or query `http://localhost:8317/v0/management/auth-files`.
4. If a file is still missing after BOM cleanup, rewrite the JSON file without
   changing its logical content so the runtime watcher rescans it.

### Project lesson

- Auth export must write JSON as plain UTF-8 without BOM.
- JSON readers in the project should tolerate BOM when reading older files.
- When CCS and CLIProxyAPI disagree, verify which layer is producing the list:
  raw file listing, account registry, or runtime auth manager.
- A file can be valid on disk but still absent from the runtime auth list until
  a watcher-visible write event occurs.

### Code changes made in this repo

- `src/core/storage.py`
  Now writes JSON via UTF-8 bytes with no BOM.
- `src/core/storage.py`
  Now strips UTF-8 BOM before `json.loads()` when reading JSON files.
- `tests/test_unit.py`
  Added coverage for BOM-tolerant reads and BOM-free writes.
- `src/core/storage.py`
  Now also syncs exported Codex auth files to the configured external auth directory.
- `config.yaml`
  `auth_sync.target_dir` defaults to `C:\Users\admin\.ccs\cliproxy\auth`, and a manual full sync is available via `python run_sync_auth.py`.
