#!/usr/bin/env python3
"""
context-reset: Autonomous Claude context reset.

Called by Claude when context gets heavy:
    python context_reset.py --project-dir /path/to/project

1. Opens new Windows Terminal tab with fresh Claude in project dir
2. Waits for new Claude process to start
3. Verifies new Claude is working (transcript activity)
4. Kills the old tab's shell process (closes old tab)

Audit log: ~/.claude/context-reset/YYYY-MM-DD.log (rotated daily)
"""

import argparse
import subprocess
import os
import sys
import time
from datetime import datetime


# ============ Logging ============

LOG_DIR = os.path.join(os.path.expanduser("~"), ".claude", "context-reset")


def log(msg):
    """Print and append to daily audit log."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(f"[context-reset] {msg}")
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        logfile = os.path.join(LOG_DIR, f"{today}.log")
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ============ Helpers ============

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

    Safety: verifies the shell doesn't own multiple Claude processes.
    """
    pid = os.getpid()
    if sys.platform != "win32":
        return os.getppid()

    shell_names = ('bash.exe', 'powershell.exe', 'pwsh.exe', 'cmd.exe')
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
                try:
                    tree_out = subprocess.check_output(
                        f'wmic process where (ParentProcessId={pid}) get Name /value',
                        encoding='utf-8', timeout=5
                    ).lower()
                    claude_children = tree_out.count('claude')
                    if claude_children > 1:
                        log(f"SAFETY: shell PID {pid} owns {claude_children} Claude processes - NOT killing")
                        return None
                except Exception:
                    pass
                return pid
        except Exception:
            break
    return None


def get_project_logs_dir(project_dir):
    home = os.path.expanduser("~")
    slug = os.path.abspath(project_dir).replace("\\", "-").replace("/", "-").replace(":", "-")
    if slug.startswith("-"):
        slug = slug[1:]
    return os.path.join(home, ".claude", "projects", slug)


def get_newest_jsonl(logs_dir):
    if not os.path.exists(logs_dir):
        return None, 0
    jsonls = [f for f in os.listdir(logs_dir) if f.endswith(".jsonl")]
    if not jsonls:
        return None, 0
    newest = max(jsonls, key=lambda f: os.path.getmtime(os.path.join(logs_dir, f)))
    fp = os.path.join(logs_dir, newest)
    return fp, os.path.getsize(fp)


def verify_claude_working(project_dir, timeout=45):
    logs_dir = get_project_logs_dir(project_dir)
    baseline_file, baseline_size = get_newest_jsonl(logs_dir)
    log(f"Phase 2: watching transcript logs in {logs_dir}")

    for i in range(timeout):
        time.sleep(1)
        current_file, current_size = get_newest_jsonl(logs_dir)

        if current_file and current_file != baseline_file:
            log(f"Verified: new session transcript detected ({os.path.basename(current_file)})")
            return True

        if current_file and current_size > baseline_size:
            log(f"Verified: transcript growing (+{current_size - baseline_size} bytes)")
            return True

    return False


# ============ Main ============

def main():
    parser = argparse.ArgumentParser(description="Autonomous Claude context reset")
    parser.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--no-close", action="store_true", help="Don't close old tab")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    prompt = args.prompt or build_prompt(project_dir)
    project_name = os.path.basename(project_dir)

    log(f"=== Context reset started for {project_name} ===")
    log(f"Project dir: {project_dir}")
    log(f"Prompt: {prompt[:80]}...")
    log(f"Close old tab: {not args.no_close}")

    if sys.platform == "win32":
        escaped = prompt.replace('"', '`"')
        cmd = f'wt new-tab --startingDirectory "{project_dir}" powershell -NoExit -Command "claude \'{escaped}\'"'
    else:
        cmd = f'bash -c \'cd "{project_dir}" && claude "{prompt}"\''

    if args.dry_run:
        log(f"DRY RUN - command: {cmd}")
        shell_pid = find_shell_pid()
        log(f"DRY RUN - shell PID to kill: {shell_pid}")
        log("=== Dry run complete ===")
        return

    # Phase 1: Launch new tab
    before = count_claude_processes()
    log(f"Phase 1: launching new tab ({before} Claude processes before)")

    subprocess.Popen(cmd, shell=True)
    log(f"New tab opened in {project_name}")

    if args.no_close:
        log("--no-close flag set, keeping old tab open")
        log("=== Context reset complete (no-close mode) ===")
        return

    if sys.platform == "win32":
        # Phase 1b: Wait for new process
        log("Phase 1b: waiting for new Claude process (up to 15s)...")
        process_detected = False
        for i in range(15):
            time.sleep(1)
            after = count_claude_processes()
            if after > before:
                log(f"New Claude process detected ({after} total, was {before})")
                process_detected = True
                break

        if not process_detected:
            log("WARNING: new Claude not detected after 15s, keeping old tab open")
            log("=== Context reset FAILED (no new process) ===")
            return

        # Phase 2: Verify working
        working = verify_claude_working(project_dir, timeout=45)
        if working:
            log("New Claude confirmed working")
            shell_pid = find_shell_pid()
            if shell_pid:
                log(f"Closing old tab (shell PID {shell_pid})")
                os.system(f'taskkill /F /T /PID {shell_pid}')
                log("Old tab closed")
                log("=== Context reset complete ===")
            else:
                log("WARNING: could not find shell PID, keeping old tab open")
                log("=== Context reset PARTIAL (new tab working, old tab kept) ===")
        else:
            log("WARNING: no transcript activity after 45s, keeping old tab open")
            log("=== Context reset FAILED (no activity detected) ===")


if __name__ == "__main__":
    main()
