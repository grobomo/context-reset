# context-reset

## Status: Working. Needs edge case handling.

## Edge cases to fix
- [ ] Write TODO.md to --project-dir (target), not cwd (which may be different)
- [ ] Close old tab after verifying new Claude is running
- [ ] Detect if new Claude process is active (not idle/crashed)

## How it works
1. Claude saves state to TODO.md
2. Claude runs: `python context_reset.py --project-dir <dir>`
3. Script opens new Windows Terminal tab with fresh Claude
4. New Claude reads TODO.md and continues autonomously

## Completed
- [x] Core script (wt new-tab, PowerShell)
- [x] Dry-run tested
- [x] Live tested — works end to end
- [x] Wired into hook-runner stop module
