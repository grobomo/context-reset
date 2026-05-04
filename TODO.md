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
- [x] Re-add --suppressApplicationTitle to lock tab title (user preference: folder name stays visible)

## Session State Handoff

- [x] Extract transcript context from JSONL logs (last 200 meaningful lines)
- [x] Write SESSION_STATE.md with transcript tail before launching new tab
- [x] Filter noise: stop hook feedback, skill boilerplate, request interrupts, tool results
- [x] Aggregate streaming user input chars into single messages
- [x] Auto-add SESSION_STATE.md to target project's .gitignore
- [x] Update build_prompt to tell new session to read SESSION_STATE.md first
- [x] Replace em-dash with ASCII in prompt (PowerShell encoding safety)
- [x] Tests for extraction, filtering, and state writing (41 total)

## Noise Filtering

- [x] T001 Fixed: raw JSONL tail from end of file instead of filtered/interpreted transcript (PR #2)

## Hook Runner Scoping (done this session, lives in ~/.claude/hooks/)

- [x] Shared load-modules.js for global + project-scoped module discovery
- [x] All 4 runners updated (pretooluse, posttooluse, stop, sessionstart)
- [x] use-workers.js scoped to hackathon26 only
- [x] archive/ folder ignored by loader

## Readable Session State (003)

- [x] T001: Parse JSONL into readable conversation text (tail-read efficiently, cap at 8K tokens)
- [x] T002: Create reusable jsonl_parser.py module in chat-export skill
- [x] T003: Update tests for new extract_session_context format (60 tests passing)
- [x] T004: Update SESSION_STATE.md format (no more raw JSONL in code fence)
- [x] T005: Move inline `import re` to top-level

## Review

- [x] Read SESSION_STATE.md after next context reset and verify it's readable, useful, and within token budget
  - Result: 31K chars (~7.7K tokens), clean conversation format, fully readable in one shot

## Code Cleanup (003)

- [x] T007: Move csv, ctypes, io imports to top-level (PR #6)

## Smart Truncation (004)

- [x] T001: Keep first + last turns when truncating, drop the middle (most recent context is most valuable)

## Hardening (005)

- [x] T001: Fix smart truncation overlap — duplicate turns when head/tail regions intersect (PR #8)
- [x] T002: Update README with current behavior (readable format, 65 tests, smart truncation)

## Quick Start Guide (006)

- [x] T001: Tab UX improvements — no focus steal, folder name title, suppressApplicationTitle
- [x] T002: Add task_claims.py tests (35 tests)
- [x] T003: Commit task_claims.py with tests
- [x] T004: Tested Notification start hook — DOES NOT WORK. Hook stderr is captured by Claude Code, not passed to terminal. OSC sequence shows as text `]0;context-reset` in output. Removed hook. Tab color is the persistent project identifier; `wt --title` sets initial title before Claude takes over.
- [x] T005: Removed PostToolUse reassertion — would kill Claude's green status icon. Tab color identifies project instead.

## Pre-trust workspace (015)

Skip the "do you trust this folder?" dialog on first launch in new directories.
Claude Code stores trust state in `~/.claude/projects/<slug>/`. Pre-creating that
directory before launching the interactive session bypasses the dialog.

- [x] T001: Add `ensure_workspace_trusted()` to new_session.py — pre-creates projects dir. Also fixed `get_project_logs_dir` slug encoding to match Claude Code (regex `[^a-zA-Z0-9-]` instead of only replacing `\/:.`)
- [x] T002: Add tests for ensure_workspace_trusted and fixed slug encoding (68 total, merged in PR #15)
- [x] T003: Fix pretrust — mkdir alone doesn't work, use `claude -p` to create real trust state (didn't work either)
- [x] T004: Fix pretrust v2 — trust is stored in `~/.claude.json` projects[path].hasTrustDialogAccepted, write it directly (PR #17 merged)
- [x] T005: Verified — pretrust-test tab launched WITHOUT trust dialog. Feature works end-to-end.
- [x] T006: Parent trust walk — check parent dirs before writing per-project entries, update CLAUDE.md docs (70 tests)
- [x] T007: Add `--stop` flag to new_session.py — kills current tab without launching a new one (PR #19)

## Rename: context-reset → new-session (007)

The name "context-reset" confuses Claude into thinking this is only for resetting context in the current project. It's actually for opening a new Claude Code session in ANY project (same or different). Rename to make the purpose clear.

- [x] T001: Create `new_session.py` (copy of `context_reset.py` with updated docstring/naming)
- [x] T002: Update stop-message.txt to reference `new_session.py` instead of `context_reset.py`
- [x] T003: Add explicit "switch project" usage example to stop-message.txt
- [x] T004: Update all hook module references (auto-continue.js, cwd-drift-detector.js)
- [x] T005: Keep `context_reset.py` as backward-compat alias (re-exports all names from new_session.py)
- [x] T006: Update README.md, CLAUDE.md, and project rules with new naming

## Session Chain Recording (008)

Record old→new session transitions so chat-export can stitch context-reset jumps.
Branch: `001-T001-add-chain-recording` (already created).

- [x] T001: Modify `verify_claude_working()` to return new JSONL path instead of True/False (PR #20)
- [x] T002: Add `record_session_chain(project_dir, old_jsonl, new_jsonl)` function (PR #20)
- [x] T003: Call chain recording in `main()` after successful verify (PR #20)
- [x] T004: Add tests for record_session_chain (12 new tests, 82 total passing) (PR #20)

## Filter Boilerplate (009)

- [x] T001: Filter hook/system boilerplate from SESSION_STATE.md transcript (PR #21)

## Pretrust Full Format (010)

- [x] T001: Write all 10 native fields in ensure_workspace_trusted (PR #22)

## Pip Packaging for Team Distribution (012)

- [x] T001: Create pyproject.toml with CLI entry points (`new-session`, `context-reset`) (PR #24)
- [x] T002: Add Quick Start section to README (pip install + stop hook JSON snippet) (PR #24)
- [x] T003: Fresh venv install from GitHub URL verified

## Bootstrap Script for Team Onboarding (013)

- [x] T001: PowerShell bootstrap.ps1 — checks prereqs, installs Claude Code + context-reset, configures stop hook (PR #25)
- [x] T002: configure_hook.py — BOM-free JSON writes, works in constrained language mode (PR #25)
- [x] T003: Idempotent — second run skips already-installed components and existing hooks

## Simplify openclaw-checkin.py (014)

Reduce friction for Claude Code to report status to OpenClaw.

- [x] T001: Make --fire-and-forget the default, add --wait flag to opt out
- [x] T002: Auto-detect project from CLAUDE_PROJECT_DIR env var (no --project needed)
- [x] T003: Add positional arg interface: `openclaw-checkin done "brief summary"` as shorthand
- [x] T004: Auto-detect task ID from TODO.md "in-progress" items if --task not given
- [x] T005: Update stop-message.txt with simplified syntax
- [x] T006: Test all changes (all CLI + unit tests pass, 96 existing tests pass)
- [x] T007: Copy updated files to ~/.claude/scripts/ and ~/.claude/hooks/run-modules/Stop/

## Split Reset vs New Session (011)

Two scripts, two behaviors, no ambiguity:
- `context_reset.py` — same-project reset. ALWAYS closes calling tab.
- `new_session.py` — cross-project session. NEVER closes calling tab.

- [x] T001: context_reset.py — remove preserve-tab flag file check, always set close_old_tab=True (PR #31)
- [x] T002: new_session.py — always set close_old_tab=False, ignore preserve-tab flag (PR #31)
- [x] T003: Remove backward-compat alias (context_reset.py should NOT call new_session.py anymore) (PR #31)
- [x] T004: Update tests for new behaviors (PR #31)
- [x] T005: Update CLAUDE.md and README with the two-script model (PR #31)

## Cross-Platform Support (016)

Full Mac, WSL, and Linux support for the entire Claude Code management system — not just new_session.py (which already has basic cross-platform), but openclaw-checkin.py, stop-message.txt paths, and the overall workflow.

Goal: share this system with others who aren't on Windows Terminal.

- [x] T001: Audit all scripts for Windows-only assumptions. Results:
  - `new_session.py`: Already well-structured with `IS_WIN`/`IS_MAC` guards. All Windows code (tasklist, wmic, PowerShell, STARTUPINFO, taskkill, closeOnExit, wt) is properly gated. Unix branches exist for process mgmt, tab launch, and kill.
  - Gaps: (a) `_has_command()` uses `which` — should use `shutil.which()` (stdlib, works everywhere). (b) macOS `osascript` branch untested, no tab color, no prompt-file safety. (c) Linux only supports `gnome-terminal`, falls back to bare `bash -c &` (no tab). (d) No tab auto-close on Linux (process dies but terminal tab stays). (e) `_restore_tab_focus()` is Windows-only (no-op on Mac/Linux).
  - `openclaw-checkin.py`: Line 41 hardcodes `/home/ubu/.openclaw/workspace/...` (WSL-specific TRACKER_PATH). Rest is portable.
  - `configure_hook.py`: Fully portable (uses `~` expansion, no platform-specific code).
  - `task_claims.py`: Fully portable (IS_WIN guards for msvcrt/fcntl locking, ctypes for PID check).
  - `scripts/test.py`: Tests branch on IS_WIN for launch cmd assertions. Works on both platforms.
- [x] T002: openclaw-checkin.py — make TRACKER_PATH portable via `Path.home()` + `OPENCLAW_TRACKER` env var (PR #44)
- [x] T003: Replace `_has_command()` `which` subprocess with `shutil.which()` (stdlib, cross-platform) (PR #44)
- [x] T004: WSL support — detect WSL via /proc/version, route through wt.exe + wsl.exe, prompt-file approach, wslpath conversion (PR #49, 126 tests)
- [x] T005: Mac support — prompt-file approach for osascript, tab title via escape sequence (PR #50, 134 tests)
- [x] T006: Linux support — prompt-file, tmux new-window fallback, tab title via escape + args (PR #51, 149 tests)
- [x] T007: Auto-detect platform already done via IS_WIN/IS_MAC branching throughout codebase
- [x] T008: EC2 test — macOS (mac-ztsa-test mac2.metal, Darwin arm64, Python 3.9.6). 140/140 tests pass. Dry-run confirms osascript + Terminal.app + prompt-file. SSH key provisioned via SSM (PR #58)
- [x] T009: EC2 test — Ubuntu 22.04 (ctx-reset-ubuntu t3.medium). 105/105 tests pass. Dry-run confirms gnome-terminal launch, Unix process tree walker (PR #47)
- [x] T010: EC2 test — Windows Server 2022 (i-0abb3cce24d38d068 t3.medium). 115/115 tests pass. SSM provisioning, SFTP sync, PowerShell-compatible commands (PR #48)
- [x] T011: WSL E2E test — 140/140 pass in WSL, IS_WSL detection verified, wt.exe + wslpath routing correct (PR #54)
- [x] T012: Update README with cross-platform platform table, WSL docs, prompt-file note, test counts (PR #52)
- [x] T013: Fix pip entry points (context-reset now injects --close-old-tab), bump to v1.1.0, add classifiers (PR #53)

## Launch UX Fixes (017)

- [x] T001: Fix phantom tab — use list-based Popen (shell=False) on Windows to avoid cmd.exe quote mangling that spawns extra tabs (PR #31)
- [x] T002: Fix focus steal — increase initial delay from 0.3s to 0.8s so check runs AFTER WT's async focus steal (~0.5s), add stability confirmation (PR #31)
- [x] T003: Pull PR #31 into main working tree — fixes were merged to GitHub but never deployed locally (all 3 bugs were running old code)
- [x] T004: Remove CREATE_NO_WINDOW from wt.exe Popen (PR #32)
- [x] T005: WT subcommand chaining (new-tab ; focus-tab --previous) for no focus steal (PR #32)
- [x] T006: Fix worktree over-resolution — subdirectories inside worktrees (7661a66)

## Dir Exists + Phantom Tab v2 (019)

- [x] T001: Add os.path.isdir() check before launch (PR #33)
- [x] T002: Remove WT subcommand chaining (`;` in Popen args) — caused phantom tabs (PR #34)

## Fix close-tab killing wrong session (021)

- [x] T001: `wt close-tab` closes ACTIVE tab, not the dead one — reverted to closeOnExit=always (PR #37)

## Merge scripts (022)

- [x] T001: context_reset.py reduced to 10-line wrapper, delegates to new_session.py --close-old-tab (PR #38)

## Remove stale focus-tab code (023)

- [x] T001: Remove `; focus-tab --previous` from build_launch_cmd and undefined `_refocus_previous_tab()` (PR #39)

## Bug: set_wt_close_on_exit undefined (024)

- [x] T001: `set_wt_close_on_exit` called but never defined. Added `get_wt_settings_path()` and `set_wt_close_on_exit()` back (lost during PR #38 merge).

## Fix WT semicolon splitting (025)

- [x] T001: Prompts containing `;` (e.g. `return null;`) caused WT error 0x80070002. Fix: write prompt to `.claude-next-prompt` file, use `-EncodedCommand` (Base64 UTF-16LE) so no special chars reach WT's parser (PR #42).

## Fix focus steal + phantom autoclose (026)

- [x] T001: Replace OS-level SetForegroundWindow with `wt focus-tab --previous` for proper tab focus restore (PR #43)
- [x] T002: Reduce closeOnExit=always window from 1.5s to 0.2s to prevent phantom tab closures (PR #43)

## Atomic focus restore (027)

- [x] T001: Replace background thread focus-tab with atomic WT chaining (`new-tab ... ; focus-tab --previous`). Zero visible tab flash. Remove `_restore_tab_focus()` and `threading` import (PR #46).

## Remove dead openclaw-checkin (028)

- [x] T001: Remove `scripts/openclaw-checkin.py` (archived), openclaw section from stop-message.txt, references from CLAUDE.md and README (PR #45).

## Code Review (029)

- [x] T001: Full code review of new_session.py, context_reset.py, task_claims.py, README.md
  - Code is solid: well-structured platform branching, proper safety checks, clean two-phase verification
  - Found README issues: non-existent `--no-close` flag, outdated test counts (PR #56)

## GitHub Actions CI (030)

- [x] T001: Add CI workflow — 3 OS x 2 Python versions matrix (PR #57)
  - Fixed: test "contains prompt" failing on macOS/Linux (prompt-file approach)
  - Fixed: `license = "MIT"` incompatible with Python 3.8 setuptools
  - All 7 jobs green: ubuntu/windows/macos x 3.8/3.12 + secret scan

## Session 2026-05-04c handoff

PRs #56-#57 merged. CI is live — every PR now runs tests on 3 OS x 2 Python.
T008 done — 140/140 on macOS EC2. Milestone 016 (cross-platform) is 100% complete.
All platforms verified live: Windows 11, Windows Server 2022, Ubuntu 22.04, WSL2, macOS Darwin arm64.
T603 added to hook-runner: user correction detector meta-hook.
PR #58 merged. CI green across all 7 jobs.

## Session 2026-05-04a handoff

PRs merged: #48-#55 (8 PRs).
- #48: Windows EC2 115/115 tests pass (SSM provisioning, SFTP sync)
- #49: WSL wt.exe routing (IS_WSL detection, wslpath)
- #50: macOS prompt-file + tab title
- #51: Linux tmux fallback
- #52: README cross-platform docs
- #53: pip entry point fix + v1.1.0
- #54: WSL E2E test 140/140
- #55: User Guide + Admin Reference (L3) HTML reports
