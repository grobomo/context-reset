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
    prompt = context_reset.build_prompt(d)
    test("no session logs -> fallback prompt", "Context was reset" in prompt and "TODO.md" in prompt)
    # With a fake JSONL log, build_prompt should write SESSION_STATE.md and reference it
    fake_project = os.path.join(d, "sp")
    os.makedirs(fake_project)
    logs_slug = os.path.abspath(fake_project).replace("\\", "-").replace("/", "-").replace(":", "-")
    if logs_slug.startswith("-"):
        logs_slug = logs_slug[1:]
    fake_logs = os.path.join(d, "dotclaude", "projects", logs_slug)
    os.makedirs(fake_logs)
    with open(os.path.join(fake_logs, "session.jsonl"), "w") as f:
        f.write('{"message":{"role":"assistant","content":[{"type":"text","text":"working on feature X"}]}}\n')
    orig_fn = context_reset.get_project_logs_dir
    context_reset.get_project_logs_dir = lambda proj: fake_logs
    prompt2 = context_reset.build_prompt(fake_project)
    test("with session logs -> references SESSION_STATE.md", "SESSION_STATE.md" in prompt2)
    test("writes SESSION_STATE.md file", os.path.exists(os.path.join(fake_project, "SESSION_STATE.md")))
    context_reset.get_project_logs_dir = orig_fn

# --- extract_session_context ---
print("\n=== extract_session_context ===")
with tempfile.TemporaryDirectory() as d:
    # No logs -> empty
    test("no logs -> empty string", context_reset.extract_session_context(d) == "")

    # With fake logs
    fake_project = os.path.join(d, "proj")
    os.makedirs(fake_project)
    logs_slug = os.path.abspath(fake_project).replace("\\", "-").replace("/", "-").replace(":", "-")
    if logs_slug.startswith("-"):
        logs_slug = logs_slug[1:]
    fake_logs = os.path.join(d, "dotclaude", "projects", logs_slug)
    os.makedirs(fake_logs)
    import json as _json
    entries = [
        {"message": {"role": "assistant", "content": [{"type": "text", "text": "I will fix the bug"}]}},
        {"message": {"role": "user", "content": [{"type": "text", "text": "looks good"}]}},
        {"message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}]}},
        {"type": "progress", "data": {"type": "hook_progress"}},
        {"message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
        {"message": {"role": "assistant", "content": [{"type": "text", "text": "Done fixing"}]}},
    ]
    with open(os.path.join(fake_logs, "session.jsonl"), "w") as f:
        for e in entries:
            f.write(_json.dumps(e) + "\n")
    orig_fn2 = context_reset.get_project_logs_dir
    context_reset.get_project_logs_dir = lambda proj: fake_logs
    ctx = context_reset.extract_session_context(fake_project)
    test("extracts assistant text", "[assistant] I will fix the bug" in ctx)
    test("extracts user text", "[user] looks good" in ctx)
    test("skips tool_use blocks", "tool_use" not in ctx and "Bash" not in ctx)
    test("skips tool_result blocks", "tool_result" not in ctx)
    test("skips progress entries", "hook_progress" not in ctx)
    test("includes final assistant text", "[assistant] Done fixing" in ctx)

    # Test max_lines truncation
    ctx_short = context_reset.extract_session_context(fake_project, max_lines=1)
    test("max_lines=1 returns only last line", ctx_short.count("\n") == 0 and "Done fixing" in ctx_short)

    # Test noise filtering
    noise_entries = [
        {"message": {"role": "user", "content": [{"type": "text", "text": "real user message"}]}},
        {"message": {"role": "user", "content": [{"type": "text", "text": "Stop hook feedback:\nDO NOT STOP..."}]}},
        {"message": {"role": "user", "content": [{"type": "text", "text": "Base directory for this skill: ~/.claude/skills/foo\n# Skill docs..."}]}},
        {"message": {"role": "user", "content": [{"type": "text", "text": "[Request interrupted by user]"}]}},
        {"message": {"role": "assistant", "content": [{"type": "text", "text": "final answer"}]}},
    ]
    with open(os.path.join(fake_logs, "session.jsonl"), "w") as f:
        for e in noise_entries:
            f.write(_json.dumps(e) + "\n")
    ctx_filtered = context_reset.extract_session_context(fake_project)
    test("filters stop hook feedback", "Stop hook feedback" not in ctx_filtered)
    test("filters skill boilerplate", "Base directory for this skill" not in ctx_filtered)
    test("filters request interrupted", "[Request interrupted" not in ctx_filtered)
    test("keeps real user messages", "real user message" in ctx_filtered)
    test("keeps assistant messages through filter", "final answer" in ctx_filtered)
    context_reset.get_project_logs_dir = orig_fn2

# --- get_first_todo ---
print("\n=== get_first_todo ===")
with tempfile.TemporaryDirectory() as d:
    test("no TODO.md -> None", context_reset.get_first_todo(d) is None)
    with open(os.path.join(d, "TODO.md"), "w") as f:
        f.write("# tasks\n- [x] Done item\n- [ ] First open item\n- [ ] Second open\n")
    test("finds first unchecked item", context_reset.get_first_todo(d) == "First open item")
    with open(os.path.join(d, "TODO.md"), "w") as f:
        f.write("# tasks\n- [x] All done\n")
    test("all checked -> None", context_reset.get_first_todo(d) is None)
    with open(os.path.join(d, "TODO.md"), "w") as f:
        f.write("- [ ] " + "A" * 60 + "\n")
    result = context_reset.get_first_todo(d)
    test("long item truncated to 50", result is not None and len(result) <= 50 and result.endswith("..."))

# --- get_tab_color ---
print("\n=== get_tab_color ===")
with tempfile.TemporaryDirectory() as d:
    # Temporarily override color map file to avoid polluting real one
    orig = context_reset.COLOR_MAP_FILE
    context_reset.COLOR_MAP_FILE = os.path.join(d, "color-map.json")
    pa = os.path.join(d, "project-a")
    pb = os.path.join(d, "project-b")
    os.makedirs(pa); os.makedirs(pb)
    c1 = context_reset.get_tab_color(pa)
    test("returns hex color", c1.startswith("#") and len(c1) == 7)
    c2 = context_reset.get_tab_color(pb)
    test("different projects get different colors", c1 != c2)
    c1_again = context_reset.get_tab_color(pa)
    test("same project gets same color", c1 == c1_again)
    context_reset.COLOR_MAP_FILE = orig

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

# --- verify_claude_working ---
print("\n=== verify_claude_working ===")
with tempfile.TemporaryDirectory() as d:
    # Mock: create a fake project logs dir with matching slug
    fake_project = os.path.join(d, "fake-project")
    os.makedirs(fake_project)
    logs_slug = os.path.abspath(fake_project).replace("\\", "-").replace("/", "-").replace(":", "-")
    if logs_slug.startswith("-"):
        logs_slug = logs_slug[1:]
    fake_logs = os.path.join(d, "dotclaude", "projects", logs_slug)
    os.makedirs(fake_logs)

    # Patch get_project_logs_dir to return our fake dir
    orig_fn = context_reset.get_project_logs_dir
    context_reset.get_project_logs_dir = lambda proj: fake_logs

    # Write baseline file
    baseline = os.path.join(fake_logs, "session-old.jsonl")
    with open(baseline, "w") as fh:
        fh.write('{"type":"init"}\n')

    # Simulate: new file appears after 1s (use a thread)
    import threading
    def write_new_file():
        time.sleep(1)
        with open(os.path.join(fake_logs, "session-new.jsonl"), "w") as fh:
            fh.write('{"type":"init"}\n{"type":"assistant"}\n')
    t = threading.Thread(target=write_new_file)
    t.start()
    result = context_reset.verify_claude_working(fake_project, timeout=5)
    t.join()
    test("detects new transcript file", result is True)

    # Simulate: no new activity within timeout
    result2 = context_reset.verify_claude_working(fake_project, timeout=2)
    test("times out when no new activity", result2 is False)

    # Simulate: existing file grows
    existing = os.path.join(fake_logs, "session-grow.jsonl")
    # Remove old files so this is the newest
    for f in os.listdir(fake_logs):
        os.remove(os.path.join(fake_logs, f))
    with open(existing, "w") as fh:
        fh.write('{"type":"init"}\n')
    time.sleep(0.05)

    def grow_file():
        time.sleep(1)
        with open(existing, "a") as fh:
            fh.write('{"type":"assistant","message":"hello"}\n')
    t2 = threading.Thread(target=grow_file)
    t2.start()
    result3 = context_reset.verify_claude_working(fake_project, timeout=5)
    t2.join()
    test("detects transcript growth", result3 is True)

    context_reset.get_project_logs_dir = orig_fn

# --- build_launch_cmd ---
print("\n=== build_launch_cmd ===")
with tempfile.TemporaryDirectory() as d:
    cmd = context_reset.build_launch_cmd(d, "test prompt", "my title", "#2D5F2D")
    if context_reset.IS_WIN:
        test("contains wt new-tab", "wt new-tab" in cmd)
        test("contains tab title", "my title" in cmd)
        test("contains tab color", "#2D5F2D" in cmd)
        test("contains project dir", d in cmd)
        test("contains prompt", "test prompt" in cmd)
        # Test single-quote escaping in prompt
        cmd2 = context_reset.build_launch_cmd(d, "it's a test", "title", "#000000")
        test("escapes single quotes for PowerShell", "it''s a test" in cmd2)
        # Test title sanitization (quotes stripped)
        cmd3 = context_reset.build_launch_cmd(d, "p", 'title "with" quotes', "#000000")
        test("strips quotes from title", '"with"' not in cmd3 and "title with quotes" in cmd3)
    elif context_reset.IS_MAC:
        test("contains osascript", "osascript" in cmd)
        test("contains prompt", "test prompt" in cmd)
    else:
        test("contains claude command", "claude" in cmd)
        test("contains prompt", "test prompt" in cmd)

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
