# context-reset

## Status: Production-ready.

## Completed
- [x] Core script (wt new-tab, PowerShell)
- [x] Dry-run tested
- [x] Live tested — works end to end
- [x] Wired into hook-runner stop module
- [x] Two-phase verification (process count + transcript activity)
- [x] Safety: verify shell PID only owns one Claude before killing
- [x] Timestamped audit log with daily rotation
- [x] Fix: detached taskkill so Python exits before tree kill (prevents "cannot terminate itself")
- [x] TODO.md target dir handled by session hook prompt ($CLAUDE_PROJECT_DIR)
- [x] .gitignore, .github/publish.json, secret-scan.yml
- [x] Test suite (scripts/test.py) — 10 tests, all passing

## Nice to have
- [ ] --timeout flag for configurable phase 2 timeout (currently hardcoded 45s)
- [ ] Linux/macOS support (currently Windows-only)
