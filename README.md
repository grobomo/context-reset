# context-reset / new-session

Two scripts for Claude Code session management:

| Script | Purpose | Old tab |
|--------|---------|---------|
| `context_reset.py` | Same-project reset (context full) | **Always killed** |
| `new_session.py` | New session (same or different project) | **Never killed** |

When a session's context window fills up, `context_reset.py` seamlessly transfers work to a fresh Claude instance in a new terminal tab — no human intervention needed. `new_session.py` opens a new session while keeping the current one running.

## Quick start

```bash
# Install (Python 3.8+, no other dependencies)
pip install git+https://github.com/grobomo/context-reset
# Works on Windows, WSL, macOS, and Linux.
```

Then tell Claude how to use it. Add to your project's `CLAUDE.md`:

```markdown
## Context Reset
When context gets long, save your progress to TODO.md and run:
  context-reset --project-dir $CLAUDE_PROJECT_DIR
```

This gives Claude a manual reset button. For **fully autonomous** operation (Claude loops through tasks and resets itself when context fills up), see [Integration with Claude Code hooks](#integration-with-claude-code-hooks) below.

> **Why not a Stop hook?** You might think to wire `context-reset` as a Stop hook, but that's wrong — Stop hooks fire on *every* stop (not just context-full), `context-reset` outputs no `{decision: "block"}` JSON, and it blocks for 15-45s during verification. The correct architecture uses a separate auto-continue hook that blocks stops and tells Claude to keep working. Claude then calls `context-reset` itself when it decides context is full.

## How it works

1. Reads the last 500 JSONL lines from the transcript (efficient reverse-read, no full file load)
2. Parses them into readable conversation text and writes `SESSION_STATE.md` (~8K tokens, smart-truncated)
3. Opens a new terminal tab/window with `claude` pointed at your project
4. Waits for the new Claude process to start (process count check)
5. Verifies the new session is working (transcript file activity)
6. Kills the old tab's shell process tree (`context_reset.py` only; `new_session.py` preserves it)

If any step fails, the old tab is preserved. Nothing is lost.

## Platform support

| Platform | Terminal | Tab launch | Tab color | Tab title | Kill method |
|----------|----------|-----------|-----------|-----------|-------------|
| Windows | Windows Terminal | `wt new-tab` | Yes | Yes | `taskkill /F /T` (detached) |
| WSL | Windows Terminal | `wt.exe new-tab` via WSL interop | Yes | Yes | `SIGTERM` to process group |
| macOS | Terminal.app | `osascript` | No | Yes | `SIGTERM` to process group |
| Linux | gnome-terminal | `gnome-terminal --tab` | No | Yes | `SIGTERM` to process group |
| Linux | tmux | `tmux new-window` | No | Yes | `SIGTERM` to process group |
| Linux (fallback) | any | background `bash -c &` | No | Yes | `SIGTERM` to process group |

All platforms use the **prompt-file** approach: the prompt is written to `.claude-next-prompt` and read by the new session's shell command. This avoids quote escaping issues across all terminal types.

## Usage

```bash
# Context reset — same project, kills old tab
python context_reset.py --project-dir /path/to/project
context-reset --project-dir /path/to/project  # pip CLI entry point

# New session — same or different project, keeps old tab
python new_session.py --project-dir /path/to/project
python new_session.py --project-dir /current --target-project /other

# Kill current tab without launching a new one
python context_reset.py --stop

# Custom prompt for the new session
python new_session.py --prompt "Fix the failing tests"

# Preview without executing
python context_reset.py --dry-run
python new_session.py --dry-run

# Custom verification timeout (default: 45s)
python context_reset.py --timeout 60
```

## Tab identification

Each new tab gets:

- **Title**: Set to the project folder name via `wt --title` on tab creation. Claude Code overwrites with its status icon during the session (this is desirable -- shows working/idle state).
- **Color**: A persistent per-project color from a 10-color palette. All tabs for the same project share the same color. Colors are stored in `~/.claude/context-reset/color-map.json` and auto-rotate through unused slots. This is the primary project identifier.
- **Focus**: On Windows/WSL, `focus-tab --previous` is chained atomically with `new-tab` in a single `wt` call — no visible tab flash.

## Integration with Claude Code hooks

The auto-continue loop is what makes context-reset powerful — Claude works through a task list autonomously and resets itself when context fills up. There are two ways to set this up.

### Option A: With hook-runner (recommended)

[hook-runner](https://github.com/grobomo/hook-runner) is a modular hook system for Claude Code. It manages all your hooks as `.js` files in folders — no manual `settings.json` editing. context-reset's auto-continue module ships with hook-runner.

```bash
# 1. Install hook-runner (enables starter workflow with safe defaults)
npx grobomo/hook-runner --yes

# 2. Install context-reset
pip install git+https://github.com/grobomo/context-reset
```

hook-runner's `starter` workflow includes the `auto-continue.js` Stop module, which:
- Blocks every stop with `{decision: "block"}`
- Reads `stop-message.txt` and feeds it to Claude as the block reason
- Claude sees "DO NOT STOP. Check TODO.md, do the next one."
- When context fills up, Claude runs `context-reset` itself

The message file (`modules/Stop/stop-message.txt`) is separate from the code so you can customize what Claude does on each stop without touching JavaScript:

```
DO NOT STOP. DO NOT SUMMARIZE. DO NOT LIST OPTIONS. Follow this order:

1) Check TODO.md — if tasks remain, do the next one NOW.
2) Scan logs for incomplete tangents — do them.
3) TEST what you built.
4) Organize, optimize, secure the project.
5) Zoom out: what real-world value comes next? Write tasks, then EXECUTE.

If context is getting long, save state to TODO.md, then run context-reset:
  context-reset --project-dir $CLAUDE_PROJECT_DIR
```

**Why hook-runner?** Beyond auto-continue, hook-runner gives you 48+ modules in the `starter` workflow: force-push protection, destructive git guards, secret scanning, commit quality checks, and session logging. The `shtd` workflow adds 113 modules for full spec-first development discipline. All modules are plain `.js` files you can read, edit, or disable individually.

### Option B: Standalone (no hook-runner)

If you prefer not to install hook-runner, create a minimal Stop hook with a separate message file.

**1. Create the message file** at `~/.claude/stop-message.txt`:

```
DO NOT STOP. Check TODO.md for pending tasks and do the next one.
If context is getting long, save state to TODO.md, then run:
  context-reset --project-dir $CLAUDE_PROJECT_DIR
```

**2. Create the hook script** at `~/.claude/hooks/auto-continue.js`:

```javascript
"use strict";
var fs = require("fs");
var path = require("path");

module.exports = function() {
  var msgPath = path.join(
    process.env.HOME || process.env.USERPROFILE || "",
    ".claude", "stop-message.txt"
  );
  var message;
  try {
    message = fs.readFileSync(msgPath, "utf-8").trim();
  } catch (e) {
    message = "DO NOT STOP. Check TODO.md for pending tasks and do the next one.";
  }
  return { decision: "block", reason: message };
};
```

**3. Wire it in** `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/hooks/auto-continue.js",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

> **Key design choice:** The message text is always in a separate file, never hardcoded in the hook script. This lets you iterate on the prompt without touching code, and prevents accidental changes when editing JavaScript. The message file is a user-authored artifact — treat it like a prompt template.

### The auto-continue loop

With either option, the full autonomous loop works like this:

```
┌─────────────────────────────────────────────────────────┐
│  1. Claude works on TODO.md tasks                       │
│  2. Claude tries to stop                                │
│  3. Stop hook blocks: "DO NOT STOP. Do the next task."  │
│  4. Claude continues working                            │
│  5. Context fills up                                    │
│  6. Claude saves state to TODO.md                       │
│  7. Claude runs: context-reset --project-dir $DIR       │
│  8. context-reset saves SESSION_STATE.md                │
│  9. context-reset opens fresh tab with new Claude       │
│ 10. New session reads SESSION_STATE.md + TODO.md        │
│ 11. Back to step 1                                      │
└─────────────────────────────────────────────────────────┘
```

This creates a fully autonomous coding agent that works through a task list across unlimited context windows, with no human intervention.

### Calling from external systems (scripts, cron)

Launch a Claude session from outside a terminal:

```bash
python3 new_session.py \
  --project-dir /path/to/project \
  --prompt "Your task description here"
```

**Important:**
- **No permission flags needed.** The script launches plain `claude` and pre-trusts the workspace automatically via `~/.claude.json`.
- **Don't use `--print` mode.** It runs one-shot and exits, bypassing the stop-hook/auto-continue loop.
- `new_session.py` preserves the old tab by default. Use `context_reset.py` or `--close-old-tab` to kill it.

## Session continuity

Context resets use two layers to preserve continuity:

- **SESSION_STATE.md** (automated): The script reads the last 500 JSONL lines from the transcript (efficient reverse-read), parses them into clean readable conversation text — user messages, Claude responses, tool use summaries, hook firings, and context boundaries. Capped at ~8K tokens with smart truncation (keeps first ~25% + last ~75%, drops the middle). Written to the project dir before launching the new tab. Auto-added to `.gitignore`.
- **TODO.md** (manual): The stop hook tells Claude to update TODO.md with curated task status before resetting.

The new session reads `SESSION_STATE.md` first (what actually happened), then `TODO.md` (what to do next).

## Safety

- **Two-phase verification**: Won't kill the old tab until the new Claude is confirmed working
- **Shell PID detection**: Walks the process tree to find the correct terminal tab shell, not inner shells from Claude's Bash tool
- **Multi-Claude guard**: Refuses to kill a shell that owns multiple Claude processes
- **Audit logging**: Every reset is logged to `~/.claude/context-reset/YYYY-MM-DD.log` (7-day retention)

## Tab close behavior

`context_reset.py` always kills the old tab after the new session is verified working. On Windows Terminal, the tab stays visible after the shell is killed (`closeOnExit: "graceful"`), so you can still scroll back and review.

`new_session.py` never kills the old tab — both sessions run side by side.

## Requirements

- Python 3.8+ (stdlib only, no pip dependencies)
- Claude Code CLI (`claude`) in PATH
- **Windows**: Windows Terminal (ships with Windows 11, available for Windows 10)
- **WSL**: Windows Terminal accessible via `wt.exe` (auto-detected via `/proc/version`)
- **macOS**: Terminal.app (default)
- **Linux**: gnome-terminal or tmux recommended; falls back to background `bash -c &`

## Tests

```bash
python scripts/test.py           # 162 tests (all platforms via mocks)
python scripts/test_task_claims.py  # 35 tests for task_claims

# Cross-platform EC2 tests
scripts/ec2-test.sh ubuntu       # Run tests on Ubuntu EC2
scripts/ec2-test.sh windows      # Run tests on Windows EC2
scripts/ec2-test.sh macos        # Run tests on macOS EC2 (mac2.metal)
```

Verified on: Windows 11 (162/162), Windows Server 2022 (115/115), WSL2 Ubuntu (140/140), Ubuntu 22.04 (105/105), macOS Darwin arm64 (140/140).

## Files

```
new_session.py            # Shared functions + new-session launcher (never closes old tab)
context_reset.py          # Same-project reset (always closes old tab)
task_claims.py            # Multi-tab task negotiation with OS-level file locks
scripts/test.py           # Tests (162 tests)
scripts/test_task_claims.py  # Tests for task_claims (35 tests)
scripts/test_focus_live.py # Live focus-steal verification (Windows only)
scripts/ec2-test.sh       # Cross-platform EC2 test runner (ubuntu/windows/macos)
~/.claude/context-reset/  # Runtime data (logs, color map)
SESSION_STATE.md          # Auto-generated in target project (gitignored)
```
