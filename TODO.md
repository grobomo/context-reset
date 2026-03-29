# context-reset

## Status: Production-ready. Needs live test of tab-close fix.

## Completed
- [x] Core script (wt new-tab, PowerShell)
- [x] Dry-run tested
- [x] Live tested — works end to end
- [x] Wired into hook-runner stop module
- [x] Two-phase verification (process count + transcript activity)
- [x] Safety: verify shell PID only owns one Claude before killing
- [x] Timestamped audit log with daily rotation
- [x] Fix: detached taskkill so Python exits before tree kill
- [x] Fix: find tab shell (child of WindowsTerminal) not inner Bash tool shell
- [x] Fix: chain tuple mismatch — was storing (parent_pid, child_name)
- [x] Suppress console popups (STARTUPINFO SW_HIDE + stderr DEVNULL)
- [x] --timeout flag for configurable phase 2 timeout
- [x] .gitignore, .github/publish.json, secret-scan.yml
- [x] Test suite (scripts/test.py) — 10 tests, all passing

## Needs live test
- [ ] Verify tab actually closes with new shell PID detection (dry-run confirmed PID 34972 = powershell, child of WindowsTerminal)

## Nice to have
- [ ] Linux/macOS support (currently Windows-only)
