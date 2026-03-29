# context-reset

## Status: Core script done. Uses `wt new-tab` for same-window new tab.

## How it works
1. Claude saves state to TODO.md
2. Claude runs: `python context_reset.py --project-dir <dir>`
3. Script opens new Windows Terminal tab with fresh Claude in same window
4. New Claude reads TODO.md and continues autonomously

## Limitation
- No WT API to query/target existing tabs (MS feature request #19818 open)
- New tab appears at end, not replacing current tab
- OSC 9;9 escape sequences can set tab titles but can't target tabs

## Completed
- [x] Built context_reset.py (wt new-tab approach)
- [x] Dry-run tested
- [x] Wired into hook-runner stop module instructions
- [x] Research: WT tab API doesn't exist yet
