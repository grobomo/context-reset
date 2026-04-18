# context-reset (new-session)

Launch a new Claude Code session in any project. When a session's context window fills up, this script seamlessly transfers work to a fresh Claude instance in a new terminal tab — no human intervention needed. Also supports switching to a different project entirely.

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
        "command": "new-session --project-dir $CLAUDE_PROJECT_DIR"
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
6. Kills the old tab's shell process tree

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
# Basic — new session in current project (context reset)
python new_session.py --project-dir /path/to/project

# Switch to a different project
python new_session.py --project-dir /path/to/other/project

# Auto-close the old tab (default: tab stays open for review)
python new_session.py --close-tab

# Custom prompt for the new session
python new_session.py --prompt "Fix the failing tests"

# Preview without executing
python new_session.py --dry-run

# Keep old tab open (new tab only)
python new_session.py --no-close

# Custom verification timeout (default: 45s)
python new_session.py --timeout 60
```

> **Note:** `context_reset.py` still works as a backward-compatible alias.

## Tab identification

Each new tab gets:

- **Title**: Set to the project folder name via `wt --title` on tab creation. Claude Code overwrites with its status icon during the session (this is desirable -- shows working/idle state).
- **Color**: A persistent per-project color from a 10-color palette. All tabs for the same project share the same color. Colors are stored in `~/.claude/context-reset/color-map.json` and auto-rotate through unused slots. This is the primary project identifier.
- **Focus**: New tabs don't steal focus -- the script saves and restores the foreground window (Windows).

## Integration with Claude Code hooks

Add to a [stop hook](https://docs.anthropic.com/en/docs/claude-code/hooks) in `~/.claude/settings.json` to let Claude trigger resets autonomously when context gets heavy:

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "new-session --project-dir $CLAUDE_PROJECT_DIR"
      }
    ]
  }
}
```

The script reads `$CLAUDE_PROJECT_DIR` by default, so from a hook you can simply use `new-session`.

If you prefer to run from source instead of pip install:

```
python /path/to/context-reset/new_session.py --project-dir $CLAUDE_PROJECT_DIR
```

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

By default, the old tab stays open after the shell is killed — Windows Terminal's `closeOnExit: "graceful"` setting keeps it so you can scroll back and review the conversation.

Use `--close-tab` to auto-close: temporarily sets `closeOnExit=always`, kills the shell, then a detached process restores `closeOnExit=graceful` after 3 seconds.

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
new_session.py            # Main script — session launcher and state handoff
context_reset.py          # Backward-compat alias (imports new_session.py)
task_claims.py            # Multi-tab task negotiation with OS-level file locks
scripts/test.py           # Tests for new_session (62 tests)
scripts/test_task_claims.py  # Tests for task_claims (35 tests)
~/.claude/context-reset/  # Runtime data (logs, color map)
SESSION_STATE.md          # Auto-generated in target project (gitignored)
```
