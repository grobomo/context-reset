# Two-Layer State Handoff

Context resets preserve continuity via two complementary layers:

- **TODO.md (manual)**: Claude updates task status and next steps before resetting. Curated, concise, can miss things.
- **SESSION_STATE.md (automated)**: `context_reset.py` scrapes last 200 meaningful lines from JSONL transcript. Raw but complete. Auto-gitignored.

New sessions read SESSION_STATE.md first (what actually happened), then TODO.md (what to do next). Both layers are intentional — don't remove either one.
