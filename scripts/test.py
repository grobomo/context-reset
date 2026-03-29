#!/usr/bin/env python3
"""Tests for context_reset.py -- run with: python scripts/test.py"""

import os
import sys
import subprocess
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import context_reset

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


# --- build_prompt ---
print("\n=== build_prompt ===")
with tempfile.TemporaryDirectory() as d:
    test("no TODO.md -> generic prompt", "Check TODO.md" in context_reset.build_prompt(d))
    with open(os.path.join(d, "TODO.md"), "w") as f:
        f.write("# tasks\n")
    test("with TODO.md -> continue prompt", "continue working" in context_reset.build_prompt(d).lower())

# --- get_project_logs_dir ---
print("\n=== get_project_logs_dir ===")
logs_dir = context_reset.get_project_logs_dir("C:/Users/test/project")
test("logs dir is under .claude/projects", ".claude" in logs_dir and "projects" in logs_dir)
test("no colons in slug", ":" not in os.path.basename(logs_dir))

# --- get_newest_jsonl ---
print("\n=== get_newest_jsonl ===")
with tempfile.TemporaryDirectory() as d:
    f, s = context_reset.get_newest_jsonl(d)
    test("empty dir -> None", f is None and s == 0)

    with open(os.path.join(d, "old.jsonl"), "w") as fh:
        fh.write("line1\n")
    time.sleep(0.05)
    with open(os.path.join(d, "new.jsonl"), "w") as fh:
        fh.write("line1\nline2\n")

    f, s = context_reset.get_newest_jsonl(d)
    test("finds newest jsonl", f is not None and "new.jsonl" in f)
    test("returns file size", s > 0)

# --- count_claude_processes ---
print("\n=== count_claude_processes ===")
count = context_reset.count_claude_processes()
test("returns integer", isinstance(count, int))

# --- dry-run ---
print("\n=== dry-run mode ===")
with tempfile.TemporaryDirectory() as d:
    result = subprocess.run(
        [sys.executable, "context_reset.py", "--project-dir", d, "--dry-run"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    test("dry-run exits 0", result.returncode == 0)
    test("dry-run prints command", "DRY RUN" in result.stdout)

# --- Summary ---
print(f"\n{'='*40}")
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
