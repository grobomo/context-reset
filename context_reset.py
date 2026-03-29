#!/usr/bin/env python3
"""
context-reset: Autonomous Claude context reset.

Called by Claude when context gets heavy:
    python context_reset.py --project-dir /path/to/project

1. Opens new Windows Terminal tab with fresh Claude in project dir
2. Waits for new Claude process to start
3. Kills the old tab's shell process (closes old tab)
"""

import argparse
import subprocess
import os
import sys
import time


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


def count_claude_processes():
    """Count running claude processes on Windows."""
    try:
        out = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq claude.exe" /NH',
            encoding='utf-8', timeout=5
        )
        return out.count('claude.exe')
    except Exception:
        return -1


def find_shell_pid():
    """Find the shell process (bash/powershell) that owns this terminal tab."""
    pid = os.getpid()
    if sys.platform != "win32":
        return os.getppid()
    # Walk up to find bash.exe or powershell.exe
    for _ in range(15):
        try:
            out = subprocess.check_output(
                f'wmic process where ProcessId={pid} get ParentProcessId /value',
                encoding='utf-8', timeout=3
            ).strip()
            for line in out.split('\n'):
                if 'ParentProcessId' in line:
                    pid = int(line.split('=')[1].strip())
                    break
            name_out = subprocess.check_output(
                f'wmic process where ProcessId={pid} get Name /value',
                encoding='utf-8', timeout=3
            ).strip()
            name = name_out.split('=')[-1].strip().lower()
            if name in ('bash.exe', 'powershell.exe', 'pwsh.exe', 'cmd.exe'):
                return pid
        except Exception:
            break
    return None


def main():
    parser = argparse.ArgumentParser(description="Autonomous Claude context reset")
    parser.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--close-old-tab", action="store_true", default=True,
                        help="Close the old tab after new Claude starts (default: true)")
    parser.add_argument("--no-close", action="store_true", help="Don't close old tab")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    prompt = args.prompt or build_prompt(project_dir)
    close_old = args.close_old_tab and not args.no_close

    if sys.platform == "win32":
        escaped = prompt.replace('"', '`"')
        cmd = f'wt new-tab --startingDirectory "{project_dir}" powershell -NoExit -Command "claude \'{escaped}\'"'
    else:
        cmd = f'bash -c \'cd "{project_dir}" && claude "{prompt}"\''

    if args.dry_run:
        print(f"Command: {cmd}")
        print(f"Close old tab: {close_old}")
        shell_pid = find_shell_pid()
        print(f"Shell PID to kill: {shell_pid}")
        return

    # Count claude processes before spawning
    before = count_claude_processes()

    # Launch new tab
    subprocess.Popen(cmd, shell=True)
    print(f"[context-reset] New Claude tab launched in {project_dir}")

    if close_old and sys.platform == "win32":
        # Wait for new claude process to appear (up to 15s)
        print("[context-reset] Waiting for new Claude to start...")
        for i in range(15):
            time.sleep(1)
            after = count_claude_processes()
            if after > before:
                print(f"[context-reset] New Claude detected ({after} processes, was {before})")
                # Give it a moment to initialize
                time.sleep(2)
                # Kill the old tab's shell
                shell_pid = find_shell_pid()
                if shell_pid:
                    print(f"[context-reset] Closing old tab (shell PID {shell_pid})")
                    os.system(f'taskkill /F /T /PID {shell_pid}')
                return
        print("[context-reset] Warning: new Claude not detected, keeping old tab open")


if __name__ == "__main__":
    main()
