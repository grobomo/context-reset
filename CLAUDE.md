# context-reset / new-session

Two scripts, two behaviors, no ambiguity:

| Script | Purpose | Old tab |
|--------|---------|---------|
| `context_reset.py` | Same-project reset (context full) | **Always killed** |
| `new_session.py` | New session (same or different project) | **Never killed** |

Both share utility functions from `new_session.py`. No dependencies beyond Python stdlib.

## Architecture

- **Pre-trust**: Checks `~/.claude.json` for workspace trust. Claude Code walks parent directories, so a trusted parent (e.g. `~/Documents/ProjectsCL1`) covers all children. Only writes a new entry if no ancestor is trusted.
- **Worktree resolution**: If `CLAUDE_PROJECT_DIR` points inside `.claude/worktrees/<name>/`, resolves to the parent project root before launching.
- **Dir check**: Verifies target directory exists before launching (prevents WT error 0x8007010b).
- **Phase 1**: Launch new terminal tab via `wt new-tab` (list-based Popen, no shell). Prompt is written to `.claude-next-prompt` file and read by PowerShell via `-EncodedCommand` (Base64 UTF-16LE) — this avoids WT's `;` command separator splitting prompts that contain code like `return null;`. Focus restored via OS-level window restore.
- **Phase 1b**: Wait for new Claude process (process count check, 15s timeout)
- **Phase 2**: Verify new session is active (transcript file growth, configurable timeout)
- **Kill** (`context_reset.py` only): Close old tab's shell process tree (detached subprocess on Windows, SIGTERM on Unix)

## Integration

### Auto-continue loop (`context_reset.py`)

Called by hook-runner's `auto-continue.js` stop module when context is full:
```
python context_reset.py --project-dir $CLAUDE_PROJECT_DIR
```

The auto-continue loop creates a fully autonomous coding agent:
1. `auto-continue.js` (stop hook) blocks Claude from stopping → feeds `stop-message.txt`
2. `stop-message.txt` says: check TODO.md, do next task, test it, then optimize
3. Between tasks, Claude calls `openclaw-checkin.py` to report status to OpenClaw
4. When context fills up, Claude runs `context_reset.py` which kills this tab and opens a fresh one
5. Fresh session reads SESSION_STATE.md + TODO.md, continues where it left off

### Cross-project sessions (`new_session.py`)

Called from OpenClaw or external automation to open a session in another project:
```bash
python new_session.py --project-dir /current/project --target-project /other/project --prompt "task"
```

The prompt tells the new session to read SESSION_STATE.md (transcript context) and TODO.md.

**Do NOT add permission flags** (`--dangerously-skip-permissions`, `--permission-mode`, `--print`). The script handles workspace trust automatically. `--print` mode breaks the auto-continue loop.

## Key Design Decisions

- **Two-phase verification**: Process count alone is unreliable (multiple Claude instances). Transcript file activity confirms the new session is actually working.
- **Detached kill on Windows**: `taskkill /T` would kill us too, so the kill runs in a detached Python subprocess.
- **Tab title**: Initial title set via `wt new-tab --title "folder-name"`. Claude Code overwrites with its status icon title during the session. OSC escape sequences from hooks don't reach the terminal (stderr is captured by Claude Code), so hook-based title setting doesn't work. Tab color is the persistent project identifier.
- **Tab colors**: Persistent per-project colors from a 10-color earth-tone palette, stored in `~/.claude/context-reset/color-map.json`.
- **Focus preservation**: Two layers: (1) `wt focus-tab --previous` restores WT tab focus, (2) background thread with ALT-key trick restores OS window focus (10 retries over 3s).
- **Safety**: Won't kill a shell that owns multiple Claude processes.
- **Session state handoff**: Before launching the new tab, reads the last ~500 JSONL lines from the transcript (efficient reverse-read, no full file load), parses them into clean readable conversation text (user messages, Claude responses, tool summaries, hook firings, boundaries), and writes `SESSION_STATE.md` capped at ~8K tokens so the next session can actually read it.

## Testing

```bash
python scripts/test.py    # 115 tests
python context_reset.py --project-dir . --dry-run   # verify reset command
python new_session.py --project-dir . --dry-run     # verify new session command
```
