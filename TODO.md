# context-reset

## Current Status

v1.2.0 — Stable, feature-complete. 197 tests (162 + 35 task_claims). CI green on 3 OS x 2 Python.

| Platform | Tests | Verified |
|----------|-------|----------|
| Windows 11 | 162 | Live + CI |
| Windows Server 2022 | 115 | EC2 |
| Ubuntu 22.04 | 105 | EC2 |
| WSL2 | 140 | Live |
| macOS (Darwin arm64) | 140 | EC2 |

67 PRs merged. Key capabilities:
- Two scripts: `context_reset.py` (kills old tab) / `new_session.py` (keeps old tab)
- SESSION_STATE.md auto-handoff (readable transcript, 8K token cap)
- Focus monitor thread (catches WT async steals, 5/5 live pass)
- Duplicate session guard (transcript age check)
- Pre-trust workspace (no trust dialog)
- Pip-installable (`pip install git+https://github.com/grobomo/context-reset`)
- Bootstrap script for team onboarding

## Completed Milestones

See CHANGELOG.md for full history. Major milestones:
- 001-005: Core script, session state handoff, smart truncation
- 006-010: Tab UX, pre-trust, rename to new-session, chain recording
- 011-014: Split scripts, pip packaging, bootstrap, openclaw integration
- 015-016: Pre-trust full format, cross-platform (Win/Mac/Linux/WSL)
- 017-028: Launch UX fixes (phantom tabs, focus steal, WT semicolons)
- 029-031: Code review, GitHub Actions CI, cleanup
- 032: Fix Quick Start and integration docs
- 033: Fix focus steal (monitor thread) + tab multiplication (kill retry + duplicate guard)
