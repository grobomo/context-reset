#!/usr/bin/env python3
"""Tests for new_session.py -- run with: python scripts/test.py"""

import json
import os
import sys
import subprocess
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import new_session as context_reset

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
        f.write('{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"working on feature X"}]}}\n')
    orig_fn = context_reset.get_project_logs_dir
    context_reset.get_project_logs_dir = lambda proj: fake_logs
    prompt2 = context_reset.build_prompt(fake_project)
    test("with session logs -> references SESSION_STATE.md", "SESSION_STATE.md" in prompt2)
    test("writes SESSION_STATE.md file", os.path.exists(os.path.join(fake_project, "SESSION_STATE.md")))
    context_reset.get_project_logs_dir = orig_fn

# --- _tail_lines ---
print("\n=== _tail_lines ===")
with tempfile.TemporaryDirectory() as d:
    # Empty file
    empty = os.path.join(d, "empty.txt")
    with open(empty, 'w') as f:
        pass
    test("empty file -> empty list", context_reset._tail_lines(empty) == [])

    # Small file
    small = os.path.join(d, "small.txt")
    with open(small, 'w') as f:
        for i in range(10):
            f.write(f"line-{i}\n")
    result = context_reset._tail_lines(small, max_lines=5)
    test("tail 5 from 10 lines", len(result) == 5)
    test("tail starts at line 5", result[0] == "line-5")
    test("tail ends at line 9", result[-1] == "line-9")

    # Large file with small chunk_size to test multi-chunk reading
    big = os.path.join(d, "big.txt")
    with open(big, 'w') as f:
        for i in range(1000):
            f.write(f"entry-{i}\n")
    result = context_reset._tail_lines(big, max_lines=3, chunk_size=64)
    test("multi-chunk tail", len(result) == 3)
    test("multi-chunk last line", result[-1] == "entry-999")
    test("multi-chunk first line", result[0] == "entry-997")

# --- _tool_summary ---
print("\n=== _tool_summary ===")
test("Bash summary", context_reset._tool_summary("Bash", {"command": "git status"}) == "$ git status")
test("Read summary", context_reset._tool_summary("Read", {"file_path": "/a/b.py"}) == "Read -> /a/b.py")
test("Edit summary", context_reset._tool_summary("Edit", {"file_path": "/x.js"}) == "Edit -> /x.js")
test("Glob summary", context_reset._tool_summary("Glob", {"pattern": "*.py"}) == "Glob -> *.py")
test("Grep summary", context_reset._tool_summary("Grep", {"pattern": "TODO"}) == "Grep -> TODO")
test("Skill summary", context_reset._tool_summary("Skill", {"skill": "commit"}) == "Skill: commit")
test("MCP summary", context_reset._tool_summary("mcp__blueprint__click", {}) == "MCP blueprint/click")
test("unknown tool", context_reset._tool_summary("FooBar", {}) == "FooBar()")
long_cmd = "a" * 100
test("long Bash cmd truncated", len(context_reset._tool_summary("Bash", {"command": long_cmd})) <= 85)

# --- _parse_and_render_tail ---
print("\n=== _parse_and_render_tail ===")
import json as _json
entries = [
    _json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "I will fix the bug"}]}}),
    _json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "looks good"}]}}),
    _json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "git status"}}]}}),
    _json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "On branch main"}]}}),
    _json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Done fixing"}]}}),
]
ctx = context_reset._parse_and_render_tail(entries)
test("readable: includes assistant text", "I will fix the bug" in ctx)
test("readable: includes user text", "looks good" in ctx)
test("readable: includes tool summary", "$ git status" in ctx)
test("readable: includes tool result", "On branch main" in ctx)
test("readable: includes done text", "Done fixing" in ctx)
test("readable: has role headers", "--- Claude" in ctx and "--- User" in ctx)
test("readable: NOT raw JSON", not ctx.strip().startswith('{'))

# Test hooks are shown
hook_entries = [
    _json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "<system-reminder>Stop hook says: keep going</system-reminder>continue please"}]}}),
]
ctx_hook = context_reset._parse_and_render_tail(hook_entries)
test("readable: shows hooks", "[Hook]" in ctx_hook and "Stop hook" in ctx_hook)
test("readable: shows user text after hook", "continue please" in ctx_hook)

# Test char budget cap with smart truncation (keeps first + last turns)
big_entries = [
    _json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": f"message number {i} with padding " + "x" * 200}]}})
    for i in range(500)
]
ctx_capped = context_reset._parse_and_render_tail(big_entries, max_chars=5000)
test("char budget respected", len(ctx_capped) <= 6000)  # some overhead for truncation notice
test("truncation notice present", "truncated" in ctx_capped)
test("smart truncation: keeps first message", "message number 0" in ctx_capped)
test("smart truncation: keeps last message", "message number 499" in ctx_capped)
# Middle messages should be dropped
test("smart truncation: drops middle", "message number 250" not in ctx_capped)

# Test no duplicate turns when single oversized entry
single_big = [
    _json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "single msg " + "x" * 5000}]}})
]
ctx_single = context_reset._parse_and_render_tail(single_big, max_chars=100)
test("no duplicate on single oversized entry", ctx_single.count("single msg") == 1)

# Test no overlap with few entries and tight budget
few_entries = [
    _json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": f"item-{i} " + "y" * 100}]}})
    for i in range(4)
]
ctx_few = context_reset._parse_and_render_tail(few_entries, max_chars=200)
import re as _re_test
all_items = _re_test.findall(r'item-(\d+)', ctx_few)
test("no duplicates with few entries", len(all_items) == len(set(all_items)))

# Test compact boundary
boundary_entries = [
    _json.dumps({"type": "system", "subtype": "compact_boundary", "compactMetadata": {"trigger": "auto", "preTokens": 150000}}),
    _json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "After compaction"}]}}),
]
ctx_boundary = context_reset._parse_and_render_tail(boundary_entries)
test("boundary shown", "compacted" in ctx_boundary and "150,000" in ctx_boundary)

# --- _is_boilerplate_user_msg ---
print("\n=== _is_boilerplate_user_msg ===")
test("empty is boilerplate", context_reset._is_boilerplate_user_msg(""))
test("whitespace is boilerplate", context_reset._is_boilerplate_user_msg("   \n  "))
test("stop hook is boilerplate", context_reset._is_boilerplate_user_msg(
    "Stop hook feedback:\nDO NOT STOP. DO NOT SUMMARIZE. DO NOT LIST OPTIONS. Follow this order:\n1) Check TODO.md..."
))
test("self-analysis is boilerplate", context_reset._is_boilerplate_user_msg(
    "You are a self-analysis agent. A user interrupted Claude mid-response."
))
test("session start is boilerplate", context_reset._is_boilerplate_user_msg(
    "SESSION START INSTRUCTIONS: Check TODO.md in $CLAUDE_PROJECT_DIR for pending tasks."
))
test("context reset prompt is boilerplate", context_reset._is_boilerplate_user_msg(
    "Context was reset. Do not ask what to do. Pick up where the last session left off."
))
test("real user message is NOT boilerplate", not context_reset._is_boilerplate_user_msg(
    "please fix the bug in auth.py"
))
test("looks good is NOT boilerplate", not context_reset._is_boilerplate_user_msg("looks good"))

# Test boilerplate filtering in _parse_and_render_tail
boilerplate_entries = [
    _json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Stop hook feedback:\nDO NOT STOP. DO NOT SUMMARIZE. keep going"}]}}),
    _json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Continuing work"}]}}),
    _json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "real feedback here"}]}}),
]
ctx_bp = context_reset._parse_and_render_tail(boilerplate_entries)
test("boilerplate user msg filtered out", "DO NOT STOP" not in ctx_bp)
test("real user msg kept", "real feedback here" in ctx_bp)
test("assistant after boilerplate kept", "Continuing work" in ctx_bp)

# --- extract_session_context (integration) ---
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
    test_entries = [
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Working on feature X"}]}},
        {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "great"}]}},
    ]
    with open(os.path.join(fake_logs, "session.jsonl"), "w") as f:
        for e in test_entries:
            f.write(_json.dumps(e) + "\n")
    orig_fn2 = context_reset.get_project_logs_dir
    context_reset.get_project_logs_dir = lambda proj: fake_logs
    ctx = context_reset.extract_session_context(fake_project)
    test("integration: readable output", "Working on feature X" in ctx)
    test("integration: has role headers", "--- Claude" in ctx)
    test("integration: not raw JSON", not ctx.strip().startswith('{'))
    context_reset.get_project_logs_dir = orig_fn2


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

# Encoding: all non-alphanumeric-dash chars become -
with tempfile.TemporaryDirectory() as d:
    test_proj = os.path.join(d, "_my.project")
    os.makedirs(test_proj)
    slug = os.path.basename(context_reset.get_project_logs_dir(test_proj))
    test("underscores replaced with -", "_" not in slug)
    test("dots replaced with -", "." not in slug)
    test("slug preserves hyphens", "my-project" in slug)

# --- ensure_workspace_trusted ---
print("\n=== ensure_workspace_trusted ===")
with tempfile.TemporaryDirectory() as d:
    fake_proj = os.path.join(d, "fake-project")
    os.makedirs(fake_proj)
    # Temporarily point ensure_workspace_trusted at a temp config file
    fake_config = os.path.join(d, ".claude.json")
    import unittest.mock
    with unittest.mock.patch('new_session.os.path.expanduser', return_value=d):
        context_reset.ensure_workspace_trusted(fake_proj)
        # Verify trust was written
        with open(fake_config, 'r') as fh:
            config = json.load(fh)
        proj_key = os.path.abspath(fake_proj).replace("\\", "/")
        entry = config.get("projects", {}).get(proj_key, {})
        test("hasTrustDialogAccepted is True", entry.get("hasTrustDialogAccepted") is True)
        test("has allowedTools", "allowedTools" in entry)
        test("has full native format (10 fields)", len(entry) == 10)
        test("has mcpServers", "mcpServers" in entry)
        test("has hasClaudeMdExternalIncludesApproved", "hasClaudeMdExternalIncludesApproved" in entry)
        # Second call is a no-op
        context_reset.ensure_workspace_trusted(fake_proj)
        test("idempotent (no error on second call)", True)

        # Parent trust walk: trust parent, child should be skipped
        child_proj = os.path.join(fake_proj, "sub", "deep")
        os.makedirs(child_proj)
        # fake_proj is already trusted — child should inherit
        context_reset.ensure_workspace_trusted(child_proj)
        with open(fake_config, 'r') as fh:
            config2 = json.load(fh)
        child_key = os.path.abspath(child_proj).replace("\\", "/")
        test("parent trust skips child write", child_key not in config2.get("projects", {}))

        # Untrusted path (outside fake_proj) should get written
        other_proj = os.path.join(d, "other-project")
        os.makedirs(other_proj)
        context_reset.ensure_workspace_trusted(other_proj)
        with open(fake_config, 'r') as fh:
            config3 = json.load(fh)
        other_key = os.path.abspath(other_proj).replace("\\", "/")
        test("untrusted path gets written", other_key in config3.get("projects", {}))

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
    test("detects new transcript file", result is not None and "session-new.jsonl" in result)

    # Simulate: no new activity within timeout
    result2 = context_reset.verify_claude_working(fake_project, timeout=2)
    test("times out when no new activity", result2 is None)

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
    test("detects transcript growth", result3 is not None and "session-grow.jsonl" in result3)

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
        test("allows Claude status icon (no suppressApplicationTitle)", "--suppressApplicationTitle" not in cmd)
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

# --- record_session_chain ---
print("\n=== record_session_chain ===")
with tempfile.TemporaryDirectory() as d:
    fake_project = os.path.join(d, "chain-project")
    os.makedirs(fake_project)
    logs_slug = os.path.abspath(fake_project).replace("\\", "-").replace("/", "-").replace(":", "-")
    if logs_slug.startswith("-"):
        logs_slug = logs_slug[1:]
    fake_logs = os.path.join(d, "dotclaude", "projects", logs_slug)
    os.makedirs(fake_logs)

    orig_fn = context_reset.get_project_logs_dir
    context_reset.get_project_logs_dir = lambda proj: fake_logs

    # Test: writes correct JSONL record
    context_reset.record_session_chain(fake_project, "/logs/old-session.jsonl", "/logs/new-session.jsonl")
    chain_file = os.path.join(fake_logs, "session-chain.jsonl")
    test("creates session-chain.jsonl", os.path.exists(chain_file))
    with open(chain_file) as fh:
        lines = fh.readlines()
    test("writes one JSONL line", len(lines) == 1)
    record = json.loads(lines[0])
    test("old_session is basename only", record["old_session"] == "old-session.jsonl")
    test("new_session is basename only", record["new_session"] == "new-session.jsonl")
    test("has project_dir", "chain-project" in record["project_dir"])
    test("has timestamp", "T" in record["timestamp"])

    # Test: appends (doesn't overwrite)
    context_reset.record_session_chain(fake_project, "/logs/second-old.jsonl", "/logs/second-new.jsonl")
    with open(chain_file) as fh:
        lines = fh.readlines()
    test("appends second record", len(lines) == 2)
    record2 = json.loads(lines[1])
    test("second record has correct old", record2["old_session"] == "second-old.jsonl")

    # Test: handles None old_jsonl (first session in project)
    context_reset.record_session_chain(fake_project, None, "/logs/first.jsonl")
    with open(chain_file) as fh:
        lines = fh.readlines()
    test("handles None old_jsonl", len(lines) == 3)
    record3 = json.loads(lines[2])
    test("old_session is null when None", record3["old_session"] is None)
    test("new_session still recorded", record3["new_session"] == "first.jsonl")

    # Test: skips when both are None
    context_reset.record_session_chain(fake_project, None, None)
    with open(chain_file) as fh:
        lines = fh.readlines()
    test("skips when both None", len(lines) == 3)

    context_reset.get_project_logs_dir = orig_fn

# --- WSL detection ---
print("\n=== WSL detection ===")
# IS_WSL is set at import time from /proc/version. We can't change /proc/version
# in tests, but we can verify the detection logic and the downstream effects.
test("IS_WSL is a boolean", isinstance(context_reset.IS_WSL, bool))
# On Windows (where tests run), IS_WSL should be False
if context_reset.IS_WIN:
    test("IS_WSL is False on Windows", context_reset.IS_WSL is False)

# --- _get_wsl_distro ---
print("\n=== _get_wsl_distro ===")
# Default when no env var
orig_env = os.environ.pop('WSL_DISTRO_NAME', None)
test("default distro is Ubuntu", context_reset._get_wsl_distro() == "Ubuntu")
os.environ['WSL_DISTRO_NAME'] = 'Debian'
test("reads WSL_DISTRO_NAME env var", context_reset._get_wsl_distro() == "Debian")
if orig_env is not None:
    os.environ['WSL_DISTRO_NAME'] = orig_env
else:
    os.environ.pop('WSL_DISTRO_NAME', None)

# --- build_launch_cmd WSL branch ---
print("\n=== build_launch_cmd (WSL) ===")
# Temporarily pretend we're on WSL to test the WSL branch
orig_is_wsl = context_reset.IS_WSL
orig_is_win = context_reset.IS_WIN
orig_is_mac = context_reset.IS_MAC
context_reset.IS_WSL = True
context_reset.IS_WIN = False
context_reset.IS_MAC = False
os.environ['WSL_DISTRO_NAME'] = 'Ubuntu'
with tempfile.TemporaryDirectory() as d:
    cmd = context_reset.build_launch_cmd(d, "test prompt", "my title", "#2D5F2D")
    test("WSL: contains wt.exe", "wt.exe" in cmd)
    test("WSL: contains wsl.exe -d", "wsl.exe -d" in cmd)
    test("WSL: contains distro name", "Ubuntu" in cmd)
    test("WSL: contains tab title", "my title" in cmd)
    test("WSL: contains tab color", "#2D5F2D" in cmd)
    test("WSL: contains claude command", "claude" in cmd)
    test("WSL: contains prompt", "test prompt" in cmd)
    test("WSL: uses bash -lc (login shell)", "bash -lc" in cmd)
    # Test single-quote escaping
    cmd2 = context_reset.build_launch_cmd(d, "it's a test", "title", "#000000")
    test("WSL: escapes single quotes", "it'\\''s" in cmd2)
    # Test title sanitization
    cmd3 = context_reset.build_launch_cmd(d, "p", 'title "with" quotes', "#000000")
    test("WSL: strips quotes from title", '"with"' not in cmd3 and "title with quotes" in cmd3)
# Restore original platform flags
context_reset.IS_WSL = orig_is_wsl
context_reset.IS_WIN = orig_is_win
context_reset.IS_MAC = orig_is_mac
if orig_env is not None:
    os.environ['WSL_DISTRO_NAME'] = orig_env
else:
    os.environ.pop('WSL_DISTRO_NAME', None)

# --- build_launch_cmd (macOS) ---
print("\n=== build_launch_cmd (macOS) ===")
orig_is_wsl = context_reset.IS_WSL
orig_is_win = context_reset.IS_WIN
orig_is_mac = context_reset.IS_MAC
context_reset.IS_WSL = False
context_reset.IS_WIN = False
context_reset.IS_MAC = True
with tempfile.TemporaryDirectory() as d:
    cmd = context_reset.build_launch_cmd(d, "test prompt", "my title", "#2D5F2D")
    test("Mac: contains osascript", "osascript" in cmd)
    test("Mac: contains Terminal", "Terminal" in cmd)
    test("Mac: contains project dir", d.replace("\\", "/") in cmd or d in cmd)
    test("Mac: contains claude", "claude" in cmd)
    test("Mac: contains prompt", "test prompt" in cmd)
    # Test single-quote escaping
    cmd2 = context_reset.build_launch_cmd(d, "it's a test", "title", "#000000")
    test("Mac: escapes single quotes", "it'\\''s" in cmd2)
context_reset.IS_WSL = orig_is_wsl
context_reset.IS_WIN = orig_is_win
context_reset.IS_MAC = orig_is_mac

# --- build_launch_cmd (Linux with gnome-terminal) ---
print("\n=== build_launch_cmd (Linux) ===")
orig_is_wsl = context_reset.IS_WSL
orig_is_win = context_reset.IS_WIN
orig_is_mac = context_reset.IS_MAC
context_reset.IS_WSL = False
context_reset.IS_WIN = False
context_reset.IS_MAC = False
# Mock _has_command to simulate gnome-terminal available
orig_has_cmd = context_reset._has_command
context_reset._has_command = lambda name: name == 'gnome-terminal'
with tempfile.TemporaryDirectory() as d:
    cmd = context_reset.build_launch_cmd(d, "test prompt", "my title", "#2D5F2D")
    test("Linux: contains gnome-terminal", "gnome-terminal" in cmd)
    test("Linux: contains --tab", "--tab" in cmd)
    test("Linux: contains title", "my title" in cmd)
    test("Linux: contains claude", "claude" in cmd)
    test("Linux: contains prompt", "test prompt" in cmd)
    # Test single-quote escaping
    cmd2 = context_reset.build_launch_cmd(d, "it's a test", "title", "#000000")
    test("Linux: escapes single quotes", "it'\\''s" in cmd2)
# Fallback: no gnome-terminal
context_reset._has_command = lambda name: False
with tempfile.TemporaryDirectory() as d:
    cmd = context_reset.build_launch_cmd(d, "test prompt", "my title", "#2D5F2D")
    test("Linux fallback: uses bash -c", "bash -c" in cmd)
    test("Linux fallback: runs in background (&)", cmd.endswith("&"))
    test("Linux fallback: contains claude", "claude" in cmd)
context_reset._has_command = orig_has_cmd
context_reset.IS_WSL = orig_is_wsl
context_reset.IS_WIN = orig_is_win
context_reset.IS_MAC = orig_is_mac

# --- Summary ---
print(f"\n{'='*40}")
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
