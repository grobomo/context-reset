#!/usr/bin/env python3
"""
context-reset: Autonomous Claude context reset.

Called by Claude when context gets heavy:
    python context_reset.py --project-dir /path/to/project

Opens a new Windows Terminal tab in the same window with fresh Claude.
No human interaction needed. Tab ordering shifts but stays in same window.
"""

import argparse
import subprocess
import os
import sys


def build_prompt(project_dir):
    todo = os.path.join(project_dir, "TODO.md")
    if os.path.exists(todo):
        return (
            "Context was reset. Read TODO.md and continue working. "
            "Do not ask what to do. Pick up where the last session left off."
        )
    return (
        "Context was reset. Check TODO.md, CLAUDE.md, or git log for state. "
        "Continue working."
    )


def main():
    parser = argparse.ArgumentParser(description="Autonomous Claude context reset")
    parser.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    prompt = args.prompt or build_prompt(project_dir)

    if sys.platform == "win32":
        escaped = prompt.replace('"', '`"')
        cmd = f'wt new-tab --startingDirectory "{project_dir}" powershell -NoExit -Command "claude \'{escaped}\'"'
    else:
        cmd = f'bash -c \'cd "{project_dir}" && claude "{prompt}"\''

    if args.dry_run:
        print(f"Command: {cmd}")
        return

    subprocess.Popen(cmd, shell=True)
    print(f"[context-reset] New Claude tab launched in {project_dir}")


if __name__ == "__main__":
    main()
