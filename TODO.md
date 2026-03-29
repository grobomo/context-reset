# context-reset

## Status: Production-ready. Live tested, pushed to GitHub.

## Completed
- [x] Core script (wt new-tab, PowerShell)
- [x] Dry-run tested
- [x] Live tested — works end to end (multiple projects, 2026-03-29)
- [x] Wired into hook-runner stop module (auto-continue.js references script path)
- [x] Two-phase verification (process count + transcript activity)
- [x] Safety: verify shell PID only owns one Claude before killing
- [x] Timestamped audit log with daily rotation + 7-day retention cleanup
- [x] Fix: detached taskkill so Python exits before tree kill
- [x] Fix: find tab shell (child of WindowsTerminal) not inner Bash tool shell
- [x] Fix: chain tuple mismatch — was storing (parent_pid, child_name)
- [x] Suppress console popups (STARTUPINFO SW_HIDE + stderr DEVNULL)
- [x] Fix: kill/restore runs as invisible Python subprocess (no cmd/ping windows)
- [x] --timeout flag for configurable phase 2 timeout
- [x] --close-tab flag to auto-close terminal tab after reset
- [x] .gitignore, .github/publish.json, secret-scan.yml
- [x] Test suite (scripts/test.py) — 10 tests, all passing
- [x] Pushed to grobomo/context-reset (public)

## Tab close behavior

By default, killing the shell exits with code 1. Windows Terminal's `closeOnExit: "graceful"`
(default) keeps the tab open so you can review the conversation.

Use `--close-tab` to auto-close: temporarily sets WT `closeOnExit=always`, kills the shell,
then a detached process restores `closeOnExit=graceful` after ~3 seconds.

## Nice to have
- [ ] Linux/macOS support (currently Windows-only)
- [ ] README.md for GitHub (usage examples, integration guide)
