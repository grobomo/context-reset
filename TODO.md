# context-reset

## Status: Core script built. Needs testing.

## How it works
1. Claude saves state to TODO.md
2. Claude runs: `python context_reset.py --project-dir <dir>`
3. Script spawns new Claude in a new terminal window with fresh context
4. Script kills current Claude process
5. New Claude reads TODO.md and continues working

## Tasks
- [ ] Test: dry-run to verify PID detection works
- [ ] Test: actual reset (save TODO, run script, verify new window opens)
- [ ] Test on Windows (cmd /c start) and Git Bash

## Completed
- [x] Research: found Continuous-Claude-v3, ralph, boucle approaches
- [x] Built context_reset.py (kill current, spawn fresh in new terminal)
- [x] Wired into hook-runner stop module instructions
