#!/usr/bin/env python3
"""Tests for task_claims.py -- run with: python scripts/test_task_claims.py"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import task_claims

PASS = 0
FAIL = 0


def test(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def capture_stdout(fn, *args, **kwargs):
    """Capture printed JSON output from a command function."""
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = fn(*args, **kwargs)
    output = buf.getvalue().strip()
    try:
        parsed = json.loads(output) if output else {}
    except json.JSONDecodeError:
        parsed = {}
    return result, parsed


# ============ _project_key ============
print("\n=== _project_key ===")
key = task_claims._project_key(os.path.join(os.path.expanduser("~"), "my-project"))
test("produces string key", isinstance(key, str))
test("no colons", ":" not in key)


# ============ _parse_todo ============
print("\n=== _parse_todo ===")
with tempfile.TemporaryDirectory() as d:
    # No TODO.md
    tasks = task_claims._parse_todo(d)
    test("no TODO.md returns empty", tasks == [])

    # TODO.md with mixed items
    with open(os.path.join(d, "TODO.md"), "w") as f:
        f.write("# Tasks\n\n")
        f.write("- [x] T001: Done task\n")
        f.write("- [ ] T002: Open task\n")
        f.write("- [ ] T003: Another open\n")
        f.write("- [x] T004: Also done\n")
    tasks = task_claims._parse_todo(d)
    test("finds unchecked tasks", tasks == ["T002", "T003"])
    test("skips checked tasks", "T001" not in tasks and "T004" not in tasks)


# ============ claim / release ============
print("\n=== claim / release ===")
with tempfile.TemporaryDirectory() as d:
    # Override claims dir to temp
    orig_dir = task_claims.CLAIMS_DIR
    orig_log = task_claims.ACTIVITY_LOG
    task_claims.CLAIMS_DIR = os.path.join(d, "claims")
    task_claims.ACTIVITY_LOG = os.path.join(d, "claims", "activity.jsonl")

    # Claim a task
    ok, out = capture_stdout(task_claims.cmd_claim, "T001", "session-aaa", d, pid=os.getpid())
    test("claim succeeds", ok is True)
    test("claim output says claimed", out.get("claimed") is True)

    # Claim same task again from different session
    ok2, out2 = capture_stdout(task_claims.cmd_claim, "T001", "session-bbb", d, pid=os.getpid())
    test("duplicate claim fails", ok2 is False)
    test("shows already claimed", out2.get("reason") == "already_claimed")

    # Claim different task from same session
    ok3, out3 = capture_stdout(task_claims.cmd_claim, "T002", "session-aaa", d, pid=os.getpid())
    test("different task claim succeeds", ok3 is True)

    # Release T001
    rel, rout = capture_stdout(task_claims.cmd_release, "T001", "session-aaa", d)
    test("release succeeds", rel is True)
    test("release output", rout.get("released") is True)

    # Release non-existent
    rel2, rout2 = capture_stdout(task_claims.cmd_release, "T099", "session-aaa", d)
    test("release non-existent fails", rel2 is False)

    # Now T001 should be claimable again
    ok4, out4 = capture_stdout(task_claims.cmd_claim, "T001", "session-bbb", d, pid=os.getpid())
    test("re-claim after release succeeds", ok4 is True)

    task_claims.CLAIMS_DIR = orig_dir
    task_claims.ACTIVITY_LOG = orig_log


# ============ cmd_next ============
print("\n=== cmd_next ===")
with tempfile.TemporaryDirectory() as d:
    orig_dir = task_claims.CLAIMS_DIR
    orig_log = task_claims.ACTIVITY_LOG
    task_claims.CLAIMS_DIR = os.path.join(d, "claims")
    task_claims.ACTIVITY_LOG = os.path.join(d, "claims", "activity.jsonl")

    # No TODO.md
    nxt, nout = capture_stdout(task_claims.cmd_next, "session-aaa", d, pid=os.getpid())
    test("no TODO -> next is None", nxt is None)

    # Create TODO.md
    with open(os.path.join(d, "TODO.md"), "w") as f:
        f.write("- [ ] T001: First task\n")
        f.write("- [ ] T002: Second task\n")
        f.write("- [ ] T003: Third task\n")

    # First next should get T001
    nxt1, nout1 = capture_stdout(task_claims.cmd_next, "session-aaa", d, pid=os.getpid())
    test("next gets T001", nxt1 == "T001")
    test("next claims it", nout1.get("claimed") is True)

    # Same session calling next again should get same task (already_mine)
    nxt1b, nout1b = capture_stdout(task_claims.cmd_next, "session-aaa", d, pid=os.getpid())
    test("same session gets same task", nxt1b == "T001")
    test("already_mine flag", nout1b.get("already_mine") is True)

    # Different session should get T002
    nxt2, nout2 = capture_stdout(task_claims.cmd_next, "session-bbb", d, pid=os.getpid())
    test("second session gets T002", nxt2 == "T002")

    # Third session gets T003
    nxt3, nout3 = capture_stdout(task_claims.cmd_next, "session-ccc", d, pid=os.getpid())
    test("third session gets T003", nxt3 == "T003")

    # Fourth session - all claimed
    nxt4, nout4 = capture_stdout(task_claims.cmd_next, "session-ddd", d, pid=os.getpid())
    test("fourth session gets None (all claimed)", nxt4 is None)
    test("reason is all_claimed", nout4.get("reason") == "all_claimed")

    task_claims.CLAIMS_DIR = orig_dir
    task_claims.ACTIVITY_LOG = orig_log


# ============ cmd_status ============
print("\n=== cmd_status ===")
with tempfile.TemporaryDirectory() as d:
    orig_dir = task_claims.CLAIMS_DIR
    orig_log = task_claims.ACTIVITY_LOG
    task_claims.CLAIMS_DIR = os.path.join(d, "claims")
    task_claims.ACTIVITY_LOG = os.path.join(d, "claims", "activity.jsonl")

    with open(os.path.join(d, "TODO.md"), "w") as f:
        f.write("- [ ] T001: Task one\n")
        f.write("- [ ] T002: Task two\n")

    # Claim T001
    capture_stdout(task_claims.cmd_claim, "T001", "session-aaa", d, pid=os.getpid())

    _, status = capture_stdout(task_claims.cmd_status, d)
    test("status shows project name", status.get("project") == os.path.basename(d))
    test("status shows unchecked tasks", status.get("unchecked_tasks") == ["T001", "T002"])
    test("status shows T001 claimed", "T001" in status.get("claims", {}))
    test("status shows T002 available", "T002" in status.get("available", []))

    task_claims.CLAIMS_DIR = orig_dir
    task_claims.ACTIVITY_LOG = orig_log


# ============ _is_pid_alive ============
print("\n=== _is_pid_alive ===")
test("own pid is alive", task_claims._is_pid_alive(os.getpid()) is True)
test("bogus pid is dead", task_claims._is_pid_alive(99999999) is False)


# ============ dead session cleanup ============
print("\n=== dead session cleanup ===")
with tempfile.TemporaryDirectory() as d:
    orig_dir = task_claims.CLAIMS_DIR
    orig_log = task_claims.ACTIVITY_LOG
    task_claims.CLAIMS_DIR = os.path.join(d, "claims")
    task_claims.ACTIVITY_LOG = os.path.join(d, "claims", "activity.jsonl")

    # Write a claim with a dead PID directly
    os.makedirs(os.path.join(d, "claims"), exist_ok=True)
    claims_file = task_claims._claims_file(d)
    with open(claims_file, "w") as f:
        json.dump({"T001": {"session": "dead-session", "pid": 99999999, "claimed_at": "2025-01-01T00:00:00"}}, f)

    # Status should auto-clean the dead claim
    _, status = capture_stdout(task_claims.cmd_status, d)
    test("dead claim auto-released", "T001" not in status.get("claims", {}))
    test("dead release logged", len(status.get("released_dead", [])) > 0)

    task_claims.CLAIMS_DIR = orig_dir
    task_claims.ACTIVITY_LOG = orig_log


# ============ activity log ============
print("\n=== activity log ===")
with tempfile.TemporaryDirectory() as d:
    orig_dir = task_claims.CLAIMS_DIR
    orig_log = task_claims.ACTIVITY_LOG
    task_claims.CLAIMS_DIR = os.path.join(d, "claims")
    task_claims.ACTIVITY_LOG = os.path.join(d, "claims", "activity.jsonl")

    capture_stdout(task_claims.cmd_claim, "T001", "session-aaa", d, pid=os.getpid())
    capture_stdout(task_claims.cmd_release, "T001", "session-aaa", d)

    test("activity log created", os.path.exists(task_claims.ACTIVITY_LOG))
    with open(task_claims.ACTIVITY_LOG) as f:
        lines = [json.loads(l) for l in f if l.strip()]
    test("activity has claim event", any(e["event"] == "claim" for e in lines))
    test("activity has release event", any(e["event"] == "release" for e in lines))
    test("activity entries have timestamps", all("ts" in e for e in lines))

    task_claims.CLAIMS_DIR = orig_dir
    task_claims.ACTIVITY_LOG = orig_log


# ============ Results ============
print(f"\n{'=' * 40}")
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL > 0 else 0)
