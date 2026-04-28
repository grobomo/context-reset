# context-reset (new-session)

Launch a new Claude Code session in any project. Context reset (same project) or project switch (different project). Launches a fresh Claude session in a new terminal tab, verifies it's working, then kills the old tab.

## Architecture

Main file: `new_session.py`. No dependencies beyond Python stdlib.
`context_reset.py` is a backward-compat alias that re-exports everything from `new_session.py`.

- **Pre-trust**: Checks `~/.claude.json` for workspace trust. Claude Code walks parent directories, so a trusted parent (e.g. `~/Documents/ProjectsCL1`) covers all children. Only writes a new entry if no ancestor is trusted.
- **Phase 1**: Launch new terminal tab with `claude '<prompt>'`
- **Phase 1b**: Wait for new Claude process (process count check, 15s timeout)
- **Phase 2**: Verify new session is active (transcript file growth, configurable timeout)
- **Kill**: Close old tab's shell process tree (detached subprocess on Windows, SIGTERM on Unix/WSL)
- **WSL detection**: Auto-detects WSL2 via `/proc/version`, launches tabs via `wt.exe` interop, uses `claude.exe` if native `claude` isn't installed. Recognizes WSL process names (`relay`, `sessionleader`) in the process tree.

## Integration

Called by hook-runner's `auto-continue.js` stop module:
```
python C:/Users/joelg/Documents/ProjectsCL1/context-reset/new_session.py --project-dir $CLAUDE_PROJECT_DIR
```

The prompt tells the new session to read SESSION_STATE.md (transcript context) and TODO.md.

### The auto-continue loop

The system creates a fully autonomous coding agent:
1. `auto-continue.js` (stop hook) blocks Claude from stopping → feeds `stop-message.txt`
2. `stop-message.txt` says: check TODO.md, do next task, test it, then optimize
3. Between tasks, Claude calls `openclaw-checkin.py` to report status to OpenClaw
4. When context fills up, Claude runs `context_reset.py` which kills this tab and opens a fresh one
5. Fresh session reads SESSION_STATE.md + TODO.md, continues where it left off

### Calling from external systems

When launching from OpenClaw or any external automation:
```bash
python3 new_session.py --project-dir /path/to/project --prompt "task" --no-close
```

**Do NOT add permission flags** (`--dangerously-skip-permissions`, `--permission-mode`, `--print`). The script handles workspace trust automatically. `--print` mode breaks the auto-continue loop.

## Key Design Decisions

- **Two-phase verification**: Process count alone is unreliable (multiple Claude instances). Transcript file activity confirms the new session is actually working.
- **Detached kill on Windows**: `taskkill /T` would kill us too, so the kill runs in a detached Python subprocess.
- **Tab title**: Initial title set via `wt new-tab --title "folder-name"`. Claude Code overwrites with its status icon title during the session. OSC escape sequences from hooks don't reach the terminal (stderr is captured by Claude Code), so hook-based title setting doesn't work. Tab color is the persistent project identifier.
- **Tab colors**: Persistent per-project colors from a 10-color earth-tone palette, stored in `~/.claude/context-reset/color-map.json`.
- **Focus preservation**: Saves/restores foreground window on Windows so the new tab doesn't steal focus.
- **Safety**: Won't kill a shell that owns multiple Claude processes.
- **Session state handoff**: Before launching the new tab, reads the last ~500 JSONL lines from the transcript (efficient reverse-read, no full file load), parses them into clean readable conversation text (user messages, Claude responses, tool summaries, hook firings, boundaries), and writes `SESSION_STATE.md` capped at ~8K tokens so the next session can actually read it.

## Testing

```bash
python scripts/test.py    # 110 tests
python new_session.py --project-dir . --dry-run   # verify command without executing
```
