# Two-Layer State Handoff

Context resets preserve continuity via two complementary layers:

- **TODO.md (manual)**: Claude updates task status and next steps before resetting. Curated, concise, can miss things.
- **SESSION_STATE.md (automated)**: `context_reset.py` takes the last 200 raw JSONL lines from the transcript (from end of file). Includes everything — tool use, tool results, loops, errors. Auto-gitignored.

New sessions read SESSION_STATE.md first (what actually happened), then TODO.md (what to do next). Both layers are intentional — don't remove either one.
