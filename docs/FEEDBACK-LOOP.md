# Claude Code → OpenClaw Feedback Loop

Documents the full architecture for how Claude Code sessions report status back to OpenClaw.

---

## Overview

When Claude Code finishes a context reset (or sends a manual status update), it fires a
stop hook that flows through a chain of components to update both the local tab tracker
and the OpenClaw main session.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Windows (Claude Code, hook runner)                                     │
│                                                                         │
│  Claude Code session ends / stop hook fires                             │
│       │                                                                 │
│       ▼                                                                 │
│  openclaw-checkin.js    (Stop hook module, Windows-side JS shim)        │
│  C:\Users\joelg\.claude\hooks\run-modules\Stop\openclaw-checkin.js     │
│       │                                                                 │
│       │  spawns: wsl -e bash -c "python3 <path> --status done ..."     │
│       │  env: CLAUDE_PROJECT_DIR set by hook runner                    │
│       ▼                                                                 │
│  openclaw-checkin.py   (WSL/Linux Python — runs in WSL context)        │
│  /mnt/c/Users/joelg/.claude/scripts/openclaw-checkin.py               │
│  (mirror of context-reset/scripts/openclaw-checkin.py)                 │
│       │                                                                 │
│       ├──[1] tracker update (FAST — local file, no network) ─────────► │
│       │      /home/ubu/.openclaw/workspace/scripts/claude-tabs/        │
│       │      tracker.json                                               │
│       │      • appends to checkins[]                                    │
│       │      • updates last_checkin                                     │
│       │      • if status==done: sets status=completed + summary         │
│       │      • atomic write (tmp → rename)                              │
│       │                                                                 │
│       ├──[2] comms log (FAST — local append) ───────────────────────► │
│       │      ~/.openclaw/comms/claude-code.jsonl                        │
│       │      • every checkin logged with ts, status, latency, result   │
│       │                                                                 │
│       └──[3] OpenClaw chat API (SLOW — may timeout) ──────────────── ► │
│              http://localhost:18789/v1/chat/completions                  │
│              • fire-and-forget (5s timeout)                             │
│              • LLM round-trip is slow; timeouts are expected/OK         │
│              • useful for real-time notifications when it works         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  OpenClaw monitor side (Linux/WSL)                                     │
│                                                                         │
│  claude-tab-monitor cron  (every 30 minutes)                           │
│       │                                                                 │
│       │  reads                                                          │
│       ▼                                                                 │
│  tracker.json  ◄──── updated by openclaw-checkin.py [1]               │
│  /home/ubu/.openclaw/workspace/scripts/claude-tabs/tracker.json        │
│       │                                                                 │
│       ▼                                                                 │
│  manage-claude-code.py  (monitor subcommand)                           │
│  /home/ubu/.openclaw/workspace/scripts/claude-tabs/manage-claude-code.py│
│       │                                                                 │
│       ▼                                                                 │
│  Reports stalls, deaths, completions to main OpenClaw session / Slack  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Locations

| Component | Path |
|-----------|------|
| Stop hook module (JS, Windows) | `C:\Users\joelg\.claude\hooks\run-modules\Stop\openclaw-checkin.js` |
| Checkin script (Python, WSL canonical) | `/mnt/c/Users/joelg/.claude/scripts/openclaw-checkin.py` |
| Checkin script (Python, source repo) | `/mnt/c/Users/joelg/Documents/ProjectsCL1/_grobomo/context-reset/scripts/openclaw-checkin.py` |
| Comms log (JSONL audit trail) | `~/.openclaw/comms/claude-code.jsonl` |
| Tab tracker | `/home/ubu/.openclaw/workspace/scripts/claude-tabs/tracker.json` |
| Tab manager | `/home/ubu/.openclaw/workspace/scripts/claude-tabs/manage-claude-code.py` |

> **Note:** The `.claude/scripts/` copy and the context-reset `scripts/` copy are identical files.
> When updating `openclaw-checkin.py`, sync both with `cp`.

---

## Data Flow — Step by Step

1. **Claude Code session ends** (or checkin is called manually mid-session)
2. **`openclaw-checkin.js`** spawns a WSL process: `wsl -e bash -c "python3 <path> --status done --detail 'Session stop event' --project <name> --fire-and-forget"`
   - `CLAUDE_PROJECT_DIR` env var is set by the hook runner (Windows path)
   - Project name is `path.basename(CLAUDE_PROJECT_DIR)`, sanitized
3. **`openclaw-checkin.py`** resolves project name from `--project` flag (or fallback: `basename(CLAUDE_PROJECT_DIR)`)
4. **`_update_tracker()`**: Reads `tracker.json`, finds the first `active` tab whose `project_name` matches (case-insensitive substring), appends a checkin entry, updates `last_checkin`. If `status == "done"`, marks tab `completed` with `completed_at` and `summary`. Writes atomically (`.tmp` → `os.replace()`). Wrapped in `try/except` — never raises.
5. **`_log_comms()`**: Appends a JSONL entry to `~/.openclaw/comms/claude-code.jsonl` (ts, dir, type, message, result, latency_ms)
6. **`send_to_openclaw()`**: POSTs to the OpenClaw chat API with `fire_and_forget=True` (5s timeout). Timeouts are expected and OK — tracker is already updated.
7. **claude-tab-monitor cron** (every 30 min): reads `tracker.json` via `manage-claude-code.py monitor`, checks `last_checkin` recency, detects stalled/dead/completed tabs, reports to main OpenClaw session.

---

## The Bug (Fixed 2026-04-27)

### Root Cause

Before the fix, `openclaw-checkin.py` only:
- Wrote to the comms log  
- POSTed to the OpenClaw chat API (which always timed out at 5s — LLM round-trip is slow)

It **never wrote to `tracker.json`**.

`manage-claude-code.py` and the monitor cron **only read `tracker.json`** — they never parsed
the comms log or chat API responses.

Result: 32 checkins in `comms/claude-code.jsonl`, all with `"result": "timeout"`. Zero updates
to `tracker.json`. `last_checkin` was `null` for every active tab. The two sides were completely
disconnected.

### Fix Applied

1. **Added `_update_tracker(status, detail, project)`** to `openclaw-checkin.py`:
   - Called from `main()` **before** the OpenClaw API POST (tracker always updated, even on API timeout)
   - Finds matching tab by `project_name` (case-insensitive substring match, skips non-active tabs)
   - Appends to `checkins[]`, updates `last_checkin`, optionally marks `completed`
   - Atomic write (`.tmp` → `os.replace()`) — safe on POSIX/WSL
   - Wrapped in `try/except` — never breaks the checkin flow

2. **Added `--fire-and-forget` to argparse** (hidden, accepted but ignored):
   - `openclaw-checkin.js` was passing `--fire-and-forget` which caused `argparse` errors
   - Added as a no-op flag for backwards compatibility

3. **Synced both script copies**: context-reset `scripts/` → `.claude/scripts/`

---

## Testing

```bash
# Simulate a checkin from a project that has an active tab in tracker.json
CLAUDE_PROJECT_DIR=/home/ubu/.openclaw/workspace \
  python3 /mnt/c/Users/joelg/Documents/ProjectsCL1/_grobomo/context-reset/scripts/openclaw-checkin.py \
  progress "test checkin" --quiet

# Verify tracker.json was updated:
jq '.tabs[] | select(.project_name == "workspace") | {last_checkin, checkins: (.checkins | length)}' \
  /home/ubu/.openclaw/workspace/scripts/claude-tabs/tracker.json

# Expected: last_checkin is a recent ISO timestamp, checkins count > 0

# Test --fire-and-forget compat flag (accepted, no error):
CLAUDE_PROJECT_DIR=/home/ubu/.openclaw/workspace \
  python3 /mnt/c/Users/joelg/Documents/ProjectsCL1/_grobomo/context-reset/scripts/openclaw-checkin.py \
  --status done --detail "test done" --project workspace --fire-and-forget
# Expected: tab status changes to "completed" in tracker.json
```

---

## Notes

- The `--quiet` flag suppresses stdout/stderr output but does **not** suppress tracker writes
- The `--wait` flag waits up to 120s for the OpenClaw API reply; default is fire-and-forget (5s)
- Tracker writes succeed even when the OpenClaw API is completely unreachable
- Only **active** tabs are updated by checkins (completed/archived tabs are skipped)
- The comms log is append-only — it's an audit trail, not the source of truth for tab state
