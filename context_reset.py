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
    """Find the shell process that owns THIS terminal tab only.

    Walks up the process tree from our PID to find the first shell.
    Safety: verifies the shell doesn't own multiple Claude processes
    (which would mean it's a parent of multiple tabs, not just ours).
    """
    pid = os.getpid()
    if sys.platform != "win32":
        return os.getppid()

    shell_names = ('bash.exe', 'powershell.exe', 'pwsh.exe', 'cmd.exe')
    # Walk up to find the shell
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
            if name in shell_names:
                # Safety: check this shell doesn't own multiple claude processes
                try:
                    tree_out = subprocess.check_output(
                        f'wmic process where (ParentProcessId={pid}) get Name /value',
                        encoding='utf-8', timeout=5
                    ).lower()
                    claude_children = tree_out.count('claude')
                    if claude_children > 1:
                        print(f"[context-reset] SAFETY: shell PID {pid} owns {claude_children} Claude processes — NOT killing")
                        return None
                except Exception:
                    pass
                return pid
        except Exception:
            break
    return None


def get_project_logs_dir(project_dir):
    """Get the ~/.claude/projects/ folder for this project dir."""
    home = os.path.expanduser("~")
    # Claude uses path with dashes: C--Users-joelg-Documents-...
    slug = os.path.abspath(project_dir).replace("\\", "-").replace("/", "-").replace(":", "-")
    # Remove leading dash
    if slug.startswith("-"):
        slug = slug[1:]
    return os.path.join(home, ".claude", "projects", slug)


def get_newest_jsonl(logs_dir):
    """Get the newest .jsonl file and its size."""
    if not os.path.exists(logs_dir):
        return None, 0
    jsonls = [f for f in os.listdir(logs_dir) if f.endswith(".jsonl")]
    if not jsonls:
        return None, 0
    newest = max(jsonls, key=lambda f: os.path.getmtime(os.path.join(logs_dir, f)))
    fp = os.path.join(logs_dir, newest)
    return fp, os.path.getsize(fp)


def verify_claude_working(project_dir, timeout=45):
    """Wait for evidence new Claude is working by watching jsonl transcript growth."""
    logs_dir = get_project_logs_dir(project_dir)
    baseline_file, baseline_size = get_newest_jsonl(logs_dir)
    print(f"[context-reset] Watching transcript logs in {logs_dir}...")

    for i in range(timeout):
        time.sleep(1)
        current_file, current_size = get_newest_jsonl(logs_dir)

        # New jsonl file appeared (new session)
        if current_file and current_file != baseline_file:
            print(f"[context-reset] New session transcript detected: {os.path.basename(current_file)}")
            return True

        # Existing file grew (Claude is reading/writing)
        if current_file and current_size > baseline_size:
            print(f"[context-reset] Transcript growing ({current_size - baseline_size} bytes)")
            return True

    return False


def main():
    parser = argparse.ArgumentParser(description="Autonomous Claude context reset")
    parser.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--no-close", action="store_true", help="Don't close old tab")
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
        print(f"Close old tab: {not args.no_close}")
        shell_pid = find_shell_pid()
        print(f"Shell PID to kill: {shell_pid}")
        return

    # Count claude processes before spawning
    before = count_claude_processes()

    # Launch new tab
    subprocess.Popen(cmd, shell=True)
    print(f"[context-reset] New Claude tab launched in {project_dir}")

    if args.no_close:
        return

    if sys.platform == "win32":
        # Phase 1: Wait for new claude process to appear (up to 15s)
        print("[context-reset] Phase 1: Waiting for new Claude process...")
        process_detected = False
        for i in range(15):
            time.sleep(1)
            after = count_claude_processes()
            if after > before:
                print(f"[context-reset] New Claude detected ({after} processes, was {before})")
                process_detected = True
                break

        if not process_detected:
            print("[context-reset] WARNING: new Claude not detected, keeping old tab open")
            return

        # Phase 2: Wait for evidence Claude is working (transcript activity, up to 45s)
        working = verify_claude_working(project_dir, timeout=45)
        if working:
            print("[context-reset] New Claude is actively working")
            shell_pid = find_shell_pid()
            if shell_pid:
                print(f"[context-reset] Closing old tab (shell PID {shell_pid})")
                os.system(f'taskkill /F /T /PID {shell_pid}')
        else:
            print("[context-reset] WARNING: new Claude not modifying files yet, keeping old tab open")


if __name__ == "__main__":
    main()
