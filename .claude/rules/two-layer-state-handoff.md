# Two-Layer State Handoff

Context resets preserve continuity via two complementary layers:

- **TODO.md (manual)**: Claude updates task status and next steps before resetting. Curated, concise, can miss things.
- **SESSION_STATE.md (automated)**: `new_session.py` reads the last ~500 JSONL lines (efficient reverse-read) and parses them into clean readable conversation text — user messages, Claude responses, tool use summaries, hook firings, context boundaries. Capped at ~8K tokens so the next session can read it without hitting limits. Auto-gitignored.

New sessions read SESSION_STATE.md first (what actually happened), then TODO.md (what to do next). Both layers are intentional — don't remove either one.
