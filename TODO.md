# context-reset

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
- [x] Tab title = first unchecked TODO item (--title flag)
- [x] Per-project tab colors (10-color palette, persistent color-map.json, auto-prune)
- [x] .gitignore, .github/publish.json, secret-scan.yml
- [x] Test suite (scripts/test.py) — 17 tests, all passing
- [x] README.md with usage, integration, and safety docs
- [x] Pushed to grobomo/context-reset (public)
- [x] Linux/macOS support (process mgmt, tab launch, kill via SIGTERM)
- [x] Fix: build_prompt now tells new session to treat all `- [ ]` items as active tasks

## Hardening & Polish

- [x] Replace deprecated `wmic` calls with `tasklist`/PowerShell `Get-CimInstance` for process tree queries
- [x] Add tests for `build_launch_cmd` (pure function, easy to test on all platforms)
- [x] Add tests for `verify_claude_working` with mock transcript files
- [x] Add CLAUDE.md for project-level context (what it does, how it integrates)
- [x] Batch-query process tree in one PowerShell call instead of per-PID (reduces reset latency)
- [x] Remove --suppressApplicationTitle to preserve Claude's green activity icon in WT tabs

## Session State Handoff

- [x] Extract transcript context from JSONL logs (last 200 meaningful lines)
- [x] Write SESSION_STATE.md with transcript tail before launching new tab
- [x] Filter noise: stop hook feedback, skill boilerplate, request interrupts, tool results
- [x] Aggregate streaming user input chars into single messages
- [x] Auto-add SESSION_STATE.md to target project's .gitignore
- [x] Update build_prompt to tell new session to read SESSION_STATE.md first
- [x] Replace em-dash with ASCII in prompt (PowerShell encoding safety)
- [x] Tests for extraction, filtering, and state writing (41 total)
