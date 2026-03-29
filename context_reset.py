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
import json
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


def _si():
    """Return STARTUPINFO that hides console windows on Windows."""
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        return si
    return None


def get_wt_settings_path():
    """Return the path to Windows Terminal's settings.json."""
    return os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Packages", "Microsoft.WindowsTerminal_8wekyb3d8bbwe",
        "LocalState", "settings.json"
    )


def set_wt_close_on_exit(mode):
    """Set Windows Terminal's closeOnExit in profile defaults.

    Modes: "graceful" (default) - only close on exit 0, tab stays open on error
           "always"             - always close tab when process exits
           "never"              - never auto-close
    """
    path = get_wt_settings_path()
    if not os.path.exists(path):
        log(f"WARNING: Windows Terminal settings not found at {path}")
        return False
    try:
        with open(path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        defaults = settings.setdefault("profiles", {}).setdefault("defaults", {})
        old = defaults.get("closeOnExit", "graceful")
        defaults["closeOnExit"] = mode
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        log(f"Windows Terminal closeOnExit: {old} -> {mode}")
        return True
    except Exception as e:
        log(f"WARNING: failed to update WT settings: {e}")
        return False


def count_claude_processes():
    try:
        out = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq claude.exe" /NH',
            encoding='utf-8', timeout=5, startupinfo=_si(),
            stderr=subprocess.DEVNULL
        )
        return out.count('claude.exe')
    except Exception:
        return -1


def get_process_parent_and_name(pid):
    """Return (parent_pid, process_name) for a given PID, or (None, None)."""
    try:
        out = subprocess.check_output(
            f'wmic process where ProcessId={pid} get ParentProcessId,Name /value',
            encoding='utf-8', timeout=3, startupinfo=_si(),
            stderr=subprocess.DEVNULL
        ).strip()
        parts = {}
        for line in out.split('\n'):
            line = line.strip()
            if '=' in line:
                k, v = line.split('=', 1)
                parts[k] = v
        return int(parts.get('ParentProcessId', '0')), parts.get('Name', '').lower()
    except Exception:
        return None, None


def find_shell_pid():
    """Find the terminal tab's shell — the shell whose parent is a terminal host.

    Process tree: WindowsTerminal → powershell/bash (TAB SHELL) → claude → ... → python
    We want the TAB SHELL, not any inner shells from Claude's Bash tool.

    Safety: verifies the shell doesn't own multiple Claude processes.
    """
    if sys.platform != "win32":
        return os.getppid()

    shell_names = ('bash.exe', 'powershell.exe', 'pwsh.exe', 'cmd.exe')
    terminal_hosts = ('windowsterminal.exe', 'conhost.exe', 'openconsole.exe')

    # Walk up the parent chain, collecting (pid, name) for each process
    pid = os.getpid()
    chain = []  # [(this_pid, this_name), (parent_pid, parent_name), ...]
    for _ in range(20):
        parent_pid, my_name = get_process_parent_and_name(pid)
        if parent_pid is None or parent_pid == 0:
            break
        chain.append((pid, my_name))
        pid = parent_pid
    # Append the topmost reachable process
    _, top_name = get_process_parent_and_name(pid)
    if top_name:
        chain.append((pid, top_name))

    # Find the shell whose NEXT entry (parent) is a terminal host
    tab_shell = None
    for i, (cpid, name) in enumerate(chain):
        if name in shell_names and i + 1 < len(chain):
            parent_pid, parent_name = chain[i + 1]
            if parent_name in terminal_hosts:
                tab_shell = cpid
                log(f"  tab shell: PID {cpid} ({name}), parent PID {parent_pid} ({parent_name})")
                break

    if tab_shell is None:
        log("  could not identify tab shell in process chain:")
        for cpid, name in chain:
            log(f"    PID {cpid}: {name}")
        return None

    # Safety: verify this shell doesn't own multiple Claude processes
    try:
        tree_out = subprocess.check_output(
            f'wmic process where (ParentProcessId={tab_shell}) get Name /value',
            encoding='utf-8', timeout=5, startupinfo=_si(),
            stderr=subprocess.DEVNULL
        ).lower()
        claude_children = tree_out.count('claude')
        if claude_children > 1:
            log(f"SAFETY: shell PID {tab_shell} owns {claude_children} Claude processes - NOT killing")
            return None
    except Exception:
        pass

    return tab_shell


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
    parser.add_argument("--close-tab", action="store_true",
                        help="Auto-close terminal tab (sets WT closeOnExit=always temporarily)")
    parser.add_argument("--timeout", type=int, default=45, help="Phase 2 verification timeout in seconds")
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
        working = verify_claude_working(project_dir, timeout=args.timeout)
        if working:
            log("New Claude confirmed working")
            shell_pid = find_shell_pid()
            if shell_pid:
                log(f"Closing old tab (shell PID {shell_pid})")
                # With --close-tab, temporarily set WT to auto-close tabs,
                # then restore after the kill. Without it, WT shows
                # "process exited" and lets you review the conversation.
                wt_changed = False
                if args.close_tab:
                    wt_changed = set_wt_close_on_exit("always")
                log("=== Context reset complete ===")
                # Launch kill+restore as a detached process, then exit.
                # taskkill /T kills the whole tree (shell → claude → python).
                # We must exit first so taskkill doesn't fail on our own PID.
                # Build a single Python script that does everything invisibly:
                # kill the shell tree, optionally wait and restore WT settings.
                script_dir = os.path.dirname(os.path.abspath(__file__))
                if wt_changed:
                    kill_script = (
                        f'import subprocess, sys, time, os; '
                        f'sys.path.insert(0, {repr(script_dir)}); '
                        f'si = subprocess.STARTUPINFO(); '
                        f'si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; '
                        f'si.wShowWindow = 0; '
                        f'subprocess.call("taskkill /F /T /PID {shell_pid}", '
                        f'startupinfo=si, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); '
                        f'time.sleep(3); '
                        f'from context_reset import set_wt_close_on_exit; '
                        f'set_wt_close_on_exit("graceful")'
                    )
                else:
                    kill_script = (
                        f'import subprocess; '
                        f'si = subprocess.STARTUPINFO(); '
                        f'si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; '
                        f'si.wShowWindow = 0; '
                        f'subprocess.call("taskkill /F /T /PID {shell_pid}", '
                        f'startupinfo=si, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)'
                    )
                subprocess.Popen(
                    [sys.executable, '-c', kill_script],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
                    startupinfo=_si(),
                )
                sys.exit(0)
            else:
                log("WARNING: could not find shell PID, keeping old tab open")
                log("=== Context reset PARTIAL (new tab working, old tab kept) ===")
        else:
            log("WARNING: no transcript activity after 45s, keeping old tab open")
            log("=== Context reset FAILED (no activity detected) ===")


if __name__ == "__main__":
    main()
