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
- **Tab title**: Set to folder name via OSC escape sequence (`\033]0;name\007`) from hooks in `~/.claude/hooks/set-tab-title.sh`. Fires on session start (Notification hook) and after every tool use (PostToolUse hook) to reassert after Claude overwrites. Claude's green status icon still works since we don't use `--suppressApplicationTitle`.
- **Tab colors**: Persistent per-project colors from a 10-color earth-tone palette, stored in `~/.claude/context-reset/color-map.json`.
- **Focus preservation**: Saves/restores foreground window on Windows so the new tab doesn't steal focus.
- **Safety**: Won't kill a shell that owns multiple Claude processes.
- **Session state handoff**: Before launching the new tab, reads the last ~500 JSONL lines from the transcript (efficient reverse-read, no full file load), parses them into clean readable conversation text (user messages, Claude responses, tool summaries, hook firings, boundaries), and writes `SESSION_STATE.md` capped at ~8K tokens so the next session can actually read it.

## Testing

```bash
python scripts/test.py    # 60 tests
python context_reset.py --project-dir . --dry-run   # verify command without executing
```
