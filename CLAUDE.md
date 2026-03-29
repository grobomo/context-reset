# context-reset

Autonomous Claude Code context reset. When context gets heavy, launches a fresh Claude session in a new terminal tab, verifies it's working, then kills the old tab.

## Architecture

Single file: `context_reset.py`. No dependencies beyond Python stdlib.

- **Phase 1**: Launch new terminal tab with `claude '<prompt>'`
- **Phase 1b**: Wait for new Claude process (process count check, 15s timeout)
- **Phase 2**: Verify new session is active (transcript file growth, configurable timeout)
- **Kill**: Close old tab's shell process tree (detached subprocess on Windows, SIGTERM on Unix)

## Integration

Called by hook-runner's `auto-continue.js` stop module:
```
python C:/Users/joelg/Documents/ProjectsCL1/context-reset/context_reset.py --project-dir $CLAUDE_PROJECT_DIR
```

The prompt tells the new session to read SESSION_STATE.md (transcript context) and TODO.md.

## Key Design Decisions

- **Two-phase verification**: Process count alone is unreliable (multiple Claude instances). Transcript file activity confirms the new session is actually working.
- **Detached kill on Windows**: `taskkill /T` would kill us too, so the kill runs in a detached Python subprocess.
- **Tab colors**: Persistent per-project colors from a 10-color earth-tone palette, stored in `~/.claude/context-reset/color-map.json`.
- **Safety**: Won't kill a shell that owns multiple Claude processes.
- **Session state handoff**: Before launching the new tab, scrapes the current session's JSONL transcript (last 200 meaningful lines), filters noise (tool results, hook feedback, skill boilerplate), and writes `SESSION_STATE.md` in the project dir. The new session reads this first for full context continuity.

## Testing

```bash
python scripts/test.py    # 36 tests
python context_reset.py --project-dir . --dry-run   # verify command without executing
```
