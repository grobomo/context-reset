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

## Tab close behavior

By default, killing the shell exits with code 1. Windows Terminal's `closeOnExit: "graceful"`
(default) keeps the tab open so you can review the conversation.

Use `--close-tab` to auto-close: temporarily sets WT `closeOnExit=always`, kills the shell,
then a detached process restores `closeOnExit=graceful` after ~3 seconds.

To permanently change: edit Windows Terminal settings → Profiles → Defaults → set
`"closeOnExit": "always"`. Revert to `"graceful"` to get the review-before-close behavior back.

## Needs live test
- [ ] Verify tab closes with --close-tab flag
- [ ] Verify tab stays open (reviewable) without --close-tab

## Nice to have
- [ ] Linux/macOS support (currently Windows-only)
