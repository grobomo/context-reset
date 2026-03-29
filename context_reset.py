#!/usr/bin/env python3
"""
context-reset: Let Claude Code reset its own context and continue working.

Usage (from Claude Code via Bash):
    python context_reset.py [--project-dir /path/to/project] [--prompt "custom resume prompt"]

Flow:
1. Claude writes state to TODO.md before calling this
2. This script spawns a NEW claude session in the same project dir
3. New session reads TODO.md and continues working
4. This script exits (and the old Claude process should be dying anyway since it ran this)
"""

import argparse
import subprocess
import os
import sys
import time


def find_project_dir():
    """Find project dir from env or cwd."""
    return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())


def build_resume_prompt(project_dir):
    """Build the prompt that tells the new Claude session what to do."""
    todo_path = os.path.join(project_dir, "TODO.md")
    if os.path.exists(todo_path):
        return (
            "Context was reset to free up space. "
            "Read TODO.md for current task state and continue working. "
            "Do not ask what to do — just pick up where the previous session left off."
        )
    return (
        "Context was reset to free up space. "
        "Check for TODO.md, CLAUDE.md, or recent git log to understand current state. "
        "Continue working on whatever was in progress."
    )


def main():
    parser = argparse.ArgumentParser(description="Reset Claude Code context and continue")
    parser.add_argument("--project-dir", default=None, help="Project directory (default: CLAUDE_PROJECT_DIR or cwd)")
    parser.add_argument("--prompt", default=None, help="Custom resume prompt")
    parser.add_argument("--continue-session", action="store_true", help="Use --continue to resume last conversation")
    parser.add_argument("--session-id", default=None, help="Resume specific session ID")
    parser.add_argument("--dry-run", action="store_true", help="Print command without executing")
    args = parser.parse_args()

    project_dir = args.project_dir or find_project_dir()
    prompt = args.prompt or build_resume_prompt(project_dir)

    # Build claude command
    cmd = ["claude", "-p", prompt]

    if args.session_id:
        cmd.extend(["--resume", args.session_id])
    elif args.continue_session:
        cmd.append("--continue")

    cmd.extend(["--allowedTools", "Edit,Write,Read,Glob,Grep,Bash,Skill"])

    if args.dry_run:
        print(f"Would run in {project_dir}:")
        print(f"  {' '.join(cmd)}")
        return

    print(f"[context-reset] Starting new Claude session in {project_dir}")
    print(f"[context-reset] Prompt: {prompt[:100]}...")

    # Small delay to let the old process finish writing
    time.sleep(1)

    # Spawn new claude process detached from current
    if sys.platform == "win32":
        # Windows: use START to detach
        subprocess.Popen(
            ["cmd", "/c", "start", "/b"] + cmd,
            cwd=project_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    else:
        # Unix: nohup + setsid
        subprocess.Popen(
            cmd,
            cwd=project_dir,
            start_new_session=True,
            stdout=open(os.devnull, "w"),
            stderr=open(os.devnull, "w"),
        )

    print("[context-reset] New session launched. This process will exit.")


if __name__ == "__main__":
    main()
