# context-reset / new-session

Two scripts for Claude Code session management:

| Script | Purpose | Old tab |
|--------|---------|---------|
| `context_reset.py` | Same-project reset (context full) | **Always killed** |
| `new_session.py` | New session (same or different project) | **Never killed** |

When a session's context window fills up, `context_reset.py` seamlessly transfers work to a fresh Claude instance in a new terminal tab — no human intervention needed. `new_session.py` opens a new session while keeping the current one running.

## Quick start

```bash
# 1. Install (Python 3.8+, no other dependencies)
pip install git+https://github.com/grobomo/context-reset

# 2. Add a stop hook to ~/.claude/settings.json
```

Add this to your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "context-reset --project-dir $CLAUDE_PROJECT_DIR"
      }
    ]
  }
}
```

That's it. Claude will automatically reset to a fresh session when context gets heavy, carrying over TODO.md and a readable summary of the conversation.

If you already have stop hooks, just add the entry to your existing `Stop` array.

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
| macOS | Terminal.app | `osascript` | No | No | `SIGTERM` to process group |
| Linux | gnome-terminal | `gnome-terminal --tab` | No | Yes | `SIGTERM` to process group |
| Linux (fallback) | any | background process | No | No | `SIGTERM` to process group |

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
- **Focus**: New tabs don't steal focus — a background thread with ALT-key trick retries focus restoration for 3s to outlast WT's async focus steal (Windows).

## Integration with Claude Code hooks

Add to a [stop hook](https://docs.anthropic.com/en/docs/claude-code/hooks) in `~/.claude/settings.json` to let Claude trigger resets autonomously when context gets heavy:

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "context-reset --project-dir $CLAUDE_PROJECT_DIR"
      }
    ]
  }
}
```

The script reads `$CLAUDE_PROJECT_DIR` by default, so from a hook you can simply use `context-reset`.

If you prefer to run from source instead of pip install:

```
python /path/to/context-reset/context_reset.py --project-dir $CLAUDE_PROJECT_DIR
```

### The full auto-continue loop

The real power is combining `new_session.py` with hook-runner's `auto-continue.js` stop module. The flow:

1. Claude Code finishes a task (or tries to stop)
2. **auto-continue.js** fires as a stop hook → returns `{decision: "block"}` with the text from `stop-message.txt`
3. `stop-message.txt` tells Claude: "DO NOT STOP. Check TODO.md, do the next task."
4. Claude keeps working through TODO.md tasks in a loop
5. When context gets long, Claude saves state to TODO.md and runs `context_reset.py` itself
6. A fresh session picks up where it left off via SESSION_STATE.md + TODO.md

This creates a fully autonomous coding agent that works through a task list without human intervention.

### Calling from external systems (scripts, cron)

When launching Claude Code from outside a terminal (e.g. from an AI agent, cron job, or automation script):

```bash
python3 new_session.py \
  --project-dir /path/to/project \
  --prompt "Your task description here" \
  --no-close
```

**Important:**
- **No permission flags needed.** Don't add `--dangerously-skip-permissions`, `--permission-mode`, or `--print`. The script launches plain `claude` and the workspace is pre-trusted automatically via `~/.claude.json`.
- **`--print` mode breaks the loop.** It runs one-shot and exits, bypassing the stop-hook/auto-continue system. Claude can't loop through TODO.md tasks.
- Use `--no-close` when the caller doesn't have a tab to close (headless, agent-spawned, etc.).
- The launched Claude session is fully autonomous — auto-continue handles task looping, context-reset handles fresh starts.

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

- Python 3.8+
- Claude Code CLI (`claude`) in PATH
- **Windows**: Windows Terminal (ships with Windows 11, available for Windows 10)
- **macOS**: Terminal.app (default) or iTerm2
- **Linux**: gnome-terminal recommended; falls back to background process

## Tests

```bash
python scripts/test.py
```

## Files

```
new_session.py            # Shared functions + new-session launcher (never closes old tab)
context_reset.py          # Same-project reset (always closes old tab)
task_claims.py            # Multi-tab task negotiation with OS-level file locks
scripts/test.py           # Tests (108 tests)
scripts/test_task_claims.py  # Tests for task_claims (35 tests)
~/.claude/context-reset/  # Runtime data (logs, color map)
SESSION_STATE.md          # Auto-generated in target project (gitignored)
```
