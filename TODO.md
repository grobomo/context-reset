# context-reset

Python wrapper that lets Claude Code reset its own context and continue working.

## Problem
Claude can't run /compact or /clear programmatically. Context fills up, performance degrades, and the stop hook tells Claude to keep working but it can't clear its own context.

## Solution
A wrapper script Claude can call via Bash that:
1. Writes current state to TODO.md (Claude does this before calling the wrapper)
2. Kills the current Claude Code process
3. Starts a new Claude session with `claude -p --continue "Read TODO.md and continue"`
4. New session has fresh context but picks up the task list

## Research
- `claude -p` / `--print`: headless mode, non-interactive
- `--continue`: continues most recent conversation
- `--resume <session_id>`: continues specific conversation
- `--output-format json|text|stream-json`: output control
- CLAUDE.md is read at start of every conversation (persistent context)

## Tasks
- [ ] Build `context_reset.py` — the wrapper script
- [ ] Handle graceful shutdown of current Claude process
- [ ] Pass project directory so new session starts in right place
- [ ] Test: Claude calls wrapper, new session reads TODO.md, continues
- [ ] Add as a Bash-callable tool in stop hook instructions
- [ ] Consider: should this be an MCP tool via mcp-manager instead?
