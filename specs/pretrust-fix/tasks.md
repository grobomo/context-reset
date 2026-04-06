# Pre-trust Fix Tasks

## Phase 1: Fix (COMPLETED via PR #17 — different approach)

- [x] T001 Write `hasTrustDialogAccepted` directly to `~/.claude.json` (simpler than writing all 9 fields)
- [x] T002 Tests updated in `scripts/test.py` (68 passing)
- [x] T003 N/A — approach changed to minimal write

## Phase 2: Verify (COMPLETED)

- [x] T004 Verified: pretrust-test tab launched without trust dialog

**Checkpoint**: `python scripts/test.py` passes, new session launches without trust dialog

## Phase 3: Parent Trust Walk

- [x] T006 Add parent directory trust walk to `ensure_workspace_trusted()` — skip write if any parent is trusted
- [x] T007 Update CLAUDE.md docs and test count (70 tests)

**Checkpoint**: `bash scripts/test/test-T006-parent-trust.sh` exits 0
