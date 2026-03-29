# context-reset

Autonomous context reset for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). When a session's context window fills up, this script seamlessly transfers work to a fresh Claude instance in a new terminal tab — no human intervention needed.

## How it works

1. Opens a new terminal tab/window with `claude` pointed at your project
2. Waits for the new Claude process to start (process count check)
3. Verifies the new session is working (transcript file activity)
4. Kills the old tab's shell process tree

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
# Basic — resets in current project directory
python context_reset.py

# Specify project
python context_reset.py --project-dir /path/to/project

# Auto-close the old tab (default: tab stays open for review)
python context_reset.py --close-tab

# Custom prompt for the new session
python context_reset.py --prompt "Fix the failing tests"

# Preview without executing
python context_reset.py --dry-run

# Keep old tab open (new tab only)
python context_reset.py --no-close

# Custom verification timeout (default: 45s)
python context_reset.py --timeout 60
```

## Tab identification

Each new tab gets:

- **Title**: The first unchecked `- [ ]` item from `TODO.md`, so you can see what each Claude is working on. Falls back to the project directory name.
- **Color**: A persistent per-project color from a 10-color palette. All tabs for the same project share the same color. Colors are stored in `~/.claude/context-reset/color-map.json` and auto-rotate through unused slots.

## Integration with Claude Code hooks

Add to a [stop hook](https://docs.anthropic.com/en/docs/claude-code/hooks) module to let Claude trigger resets autonomously when context gets heavy:

```
python C:/path/to/context-reset/context_reset.py --project-dir $CLAUDE_PROJECT_DIR
```

The script reads `$CLAUDE_PROJECT_DIR` by default, so from a hook you can simply:

```
python C:/path/to/context-reset/context_reset.py
```

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
context_reset.py          # Main script
scripts/test.py           # Test suite
~/.claude/context-reset/  # Runtime data (logs, color map)
```
