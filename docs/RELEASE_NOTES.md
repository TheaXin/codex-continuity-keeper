## Continuity Keeper 2.3.0 — independently install, accept and reproduce

### Included

- Full source ZIP, SHA256SUMS.txt and per-file release-manifest.json.
- Deterministic source packaging and a non-extracting integrity verifier.
- Offline isolated installation acceptance using the installed CLI, not just source imports.
- Fresh-process interruption/export/resume demonstration with a real verified artifact.
- Simulated 5% quota boundary and unknown-quota fallback checks; no account or remote-model calls.
- Nine downloadable acceptance reports: Linux/macOS/Windows × Python 3.11/3.12/3.13.
- Existing file checkpoints, Quota Guard, safe upgrade/uninstall and Windows symlink protection.

### First steps

1. Download the versioned source ZIP, SHA256SUMS.txt and release-manifest.json.
2. Verify the downloaded ZIP hash before extraction, inspect the code, then run `python scripts/acceptance.py`.
3. Run `python scripts/install.py` for the actual user-level installation.
4. Open a new local Codex session and review/trust `/hooks`.
5. Initialize the actual project. Run `python scripts/demo_recovery.py` for an isolated recovery demonstration.

See README.md, docs/INSTALL_ACCEPTANCE.md and docs/RECOVERY_DEMO.md for POSIX and Windows commands.

### Scope of evidence

This release is published only after all nine CI matrix jobs and their isolated acceptance reports succeed. A new user's actual Hooks trust, live quota-account access, and remote-model compliance still require local validation. The deterministic demo proves persistence and recovery mechanics; it does not simulate real quota exhaustion or physical power failure. Checksums provide integrity, not an independent publisher signature.
