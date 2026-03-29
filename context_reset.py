#!/usr/bin/env python3
"""
context-reset: Reset Claude context, continue in same terminal tab.

Called by Claude when context gets heavy:
    python context_reset.py --project-dir /path/to/project

Flow:
1. Copies resume command to clipboard
2. Kills current Claude process
3. Tab returns to shell prompt
4. User pastes (Ctrl+V Enter) to resume in same tab
"""

import argparse
import subprocess
import os
import sys
import signal


def copy_to_clipboard(text):
    """Copy text to OS clipboard."""
    if sys.platform == "win32":
        subprocess.run(['clip'], input=text.encode(), check=True)
    elif sys.platform == "darwin":
        subprocess.run(['pbcopy'], input=text.encode(), check=True)
    else:
        subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode(), check=True)


def find_claude_pid():
    """Walk up process tree to find Claude."""
    pid = os.getpid()
    if sys.platform == "win32":
        for _ in range(10):
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
                    f'wmic process where ProcessId={pid} get CommandLine /value',
                    encoding='utf-8', timeout=3
                ).strip()
                if 'claude' in name_out.lower():
                    return pid
            except Exception:
                break
    return os.getppid()


def main():
    parser = argparse.ArgumentParser(description="Reset Claude context")
    parser.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    parser.add_argument("--prompt", default="Read TODO.md and continue working. Do not ask what to do.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Build the resume command
    cmd = f'cd "{args.project_dir}" && claude "{args.prompt}"'

    if args.dry_run:
        print(f"Would copy to clipboard: {cmd}")
        print(f"Would kill PID: {find_claude_pid()}")
        return

    # Copy resume command to clipboard
    copy_to_clipboard(cmd)

    claude_pid = find_claude_pid()
    print(f"\n[context-reset] Resume command copied to clipboard.")
    print(f"[context-reset] After Claude exits, paste (Ctrl+V) and press Enter.")
    print(f"[context-reset] Killing Claude (PID {claude_pid})...\n")

    # Kill current Claude
    if sys.platform == "win32":
        os.system(f'taskkill /F /T /PID {claude_pid}')
    else:
        os.kill(claude_pid, signal.SIGTERM)


if __name__ == "__main__":
    main()
