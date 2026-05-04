# Changelog

## v1.2.0 (2026-05-04)

Focus steal and tab multiplication fixes. 67 PRs merged total.

### Bug Fixes (033)
- **Focus steal**: Background monitor thread polls for 5s, catches every WT async focus steal (1-3 per launch). Live verified 5/5 PASS. (PRs #63, #66)
- **Tab multiplication**: taskkill now captures stderr, retries once, verifies PID death via `os.kill(pid, 0)`. No more silent exit code 128/255 failures. (PR #63)
- **Duplicate guard**: Pre-launch check — transcript age <10s = active session, refuses to spawn. Skipped in context-reset mode (own transcript is always fresh). (PRs #64, #67)
- **Live focus test**: `scripts/test_focus_live.py` — launches notepad, opens WT tab, verifies notepad keeps focus. Repeatable verification.

### Documentation (032)
- Fixed broken Quick Start — was a Stop hook (fires every stop, blocks 15-45s). Now: CLAUDE.md instruction + hook-runner integration.
- README: Option A (hook-runner) + Option B (standalone) + auto-continue loop ASCII diagram.
- Updated User Guide and Admin Reference HTML reports.

### Cleanup (031)
- Archived 7 stale worktree directories, pruned 19 local + 29 remote branches.
- Removed 3,316 lines of accidentally git-tracked worktree files.

## v1.1.0 (2026-05-04)

Cross-platform support. 55 PRs merged total.

### Cross-Platform (016)
- WSL: detect via /proc/version, route through wt.exe + wsl.exe, wslpath conversion (PR #49)
- macOS: osascript + Terminal.app, prompt-file approach, tab title via escape sequence (PR #50)
- Linux: gnome-terminal + tmux new-window fallback, prompt-file (PR #51)
- EC2 verified: macOS arm64 140/140, Ubuntu 105/105, Windows Server 115/115, WSL 140/140

### GitHub Actions CI (030)
- 3 OS x 2 Python versions matrix (ubuntu/windows/macos x 3.8/3.12 + secret scan)

### Code Review (029)
- Full review: well-structured platform branching, proper safety checks
- Fixed README: removed non-existent `--no-close` flag, updated test counts

### Launch UX Fixes (017-028)
- Phantom tab fix: list-based Popen (shell=False) avoids cmd.exe quote mangling
- WT semicolon splitting: prompt written to `.claude-next-prompt` file, `-EncodedCommand` (Base64 UTF-16LE)
- Atomic focus restore: `new-tab ... ; focus-tab --previous` WT chaining
- closeOnExit=always for reliable tab cleanup
- Dir exists check before launch

## v1.0.0 (2026-04-18)

Initial release with pip packaging.

### Core
- Two scripts: `context_reset.py` (kills old tab) / `new_session.py` (keeps old tab)
- Two-phase verification: process count + transcript file activity
- Safety: verify shell PID owns one Claude before killing
- Detached taskkill so Python exits before tree kill
- Per-project tab colors (10-color earth-tone palette)
- Timestamped audit log with daily rotation + 7-day retention

### Session State Handoff
- Readable conversation format from JSONL transcript (8K token cap)
- Smart truncation: keep first + last turns, drop middle
- Noise filtering: hook boilerplate, system messages, streaming chars
- Session chain recording for chat-export stitching

### Pre-trust Workspace (015)
- Writes trust state to `~/.claude.json` — no trust dialog on first launch
- Parent directory trust walk (trusted parent covers children)

### Packaging (012-013)
- `pyproject.toml` with CLI entry points (`new-session`, `context-reset`)
- PowerShell bootstrap.ps1 for team onboarding
- `configure_hook.py` for BOM-free JSON hook config
