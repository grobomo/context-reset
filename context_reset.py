#!/usr/bin/env python3
"""
context-reset: Autonomous Claude context reset.

Called by Claude when context gets heavy:
    python context_reset.py --project-dir /path/to/project

1. Opens a new terminal tab/window with fresh Claude in the project dir
2. Waits for the new Claude process to start (process count check)
3. Verifies the new session is working (transcript file activity)
4. Kills the old tab's shell process tree (closes old tab)

Supported platforms: Windows (Windows Terminal), macOS (Terminal.app/iTerm2),
Linux (gnome-terminal, or plain background process).

Audit log: ~/.claude/context-reset/YYYY-MM-DD.log (rotated daily)
"""

import argparse
import json
import signal
import subprocess
import os
import sys
import time
from datetime import datetime


IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"


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


def cleanup_old_logs(keep_days=7):
    """Delete audit logs older than keep_days."""
    try:
        if not os.path.exists(LOG_DIR):
            return
        cutoff = time.time() - (keep_days * 86400)
        for f in os.listdir(LOG_DIR):
            if f.endswith(".log"):
                fp = os.path.join(LOG_DIR, f)
                if os.path.getmtime(fp) < cutoff:
                    os.remove(fp)
    except Exception:
        pass


# ============ Tab Colors ============

# Dark earth tones — distinct but easy on the eyes
TAB_COLORS = [
    "#2D5F2D",  # forest green
    "#1B3A5C",  # navy blue
    "#6B4226",  # brown
    "#4A4A4A",  # charcoal gray
    "#5B3A6B",  # plum
    "#2E4A4A",  # dark teal
    "#7A5C3A",  # tan/khaki
    "#3D2B1F",  # espresso
    "#4A6741",  # olive
    "#4B3621",  # dark brown
]

COLOR_MAP_FILE = os.path.join(LOG_DIR, "color-map.json")


def get_tab_color(project_dir):
    """Return a persistent hex color for this project, rotating through the palette."""
    project_key = os.path.abspath(project_dir)
    color_map = {}
    try:
        if os.path.exists(COLOR_MAP_FILE):
            with open(COLOR_MAP_FILE, 'r', encoding='utf-8') as f:
                color_map = json.load(f)
    except Exception:
        pass

    # Prune entries for directories that no longer exist
    color_map = {k: v for k, v in color_map.items() if os.path.isdir(k)}

    # Already assigned
    if project_key in color_map:
        return color_map[project_key]

    # Find first unused color
    used = set(color_map.values())
    for color in TAB_COLORS:
        if color not in used:
            color_map[project_key] = color
            break
    else:
        # All colors used — cycle based on count
        color_map[project_key] = TAB_COLORS[len(color_map) % len(TAB_COLORS)]

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(COLOR_MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(color_map, f, indent=2)
    except Exception:
        pass

    return color_map[project_key]


# ============ Helpers ============

def get_first_todo(project_dir):
    """Return the first unchecked TODO item text, or None."""
    todo = os.path.join(project_dir, "TODO.md")
    if not os.path.exists(todo):
        return None
    try:
        with open(todo, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith("- [ ]"):
                    text = line[5:].strip()
                    if len(text) > 50:
                        text = text[:47] + "..."
                    return text
    except Exception:
        pass
    return None


def build_prompt(project_dir):
    todo = os.path.join(project_dir, "TODO.md")
    if os.path.exists(todo):
        return (
            "Context was reset. Read TODO.md and continue working. "
            "Do not ask what to do. Pick up where the last session left off. "
            "Any unchecked todo item is an active task regardless of "
            "what section or header it falls under."
        )
    return (
        "Context was reset. Check TODO.md, CLAUDE.md, or git log for state. "
        "Continue working."
    )


def _si():
    """Return STARTUPINFO that hides console windows on Windows."""
    if IS_WIN:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        return si
    return None


# ============ Windows Terminal Helpers ============

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


# ============ Platform: Process Management ============

def count_claude_processes():
    """Count running claude processes."""
    if IS_WIN:
        try:
            out = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq claude.exe" /NH',
                encoding='utf-8', timeout=5, startupinfo=_si(),
                stderr=subprocess.DEVNULL
            )
            return out.count('claude.exe')
        except Exception:
            return -1
    else:
        try:
            out = subprocess.check_output(
                ['pgrep', '-c', '-x', 'claude'],
                encoding='utf-8', timeout=5,
                stderr=subprocess.DEVNULL
            )
            return int(out.strip())
        except subprocess.CalledProcessError:
            return 0
        except Exception:
            return -1


def _load_process_table():
    """Load full process table as {pid: (parent_pid, name)} dict. One subprocess call."""
    table = {}
    if IS_WIN:
        try:
            out = subprocess.check_output(
                ['powershell', '-NoProfile', '-Command',
                 'Get-CimInstance Win32_Process | '
                 'ForEach-Object { "$($_.ProcessId)|$($_.ParentProcessId)|$($_.Name)" }'],
                encoding='utf-8', timeout=10, startupinfo=_si(),
                stderr=subprocess.DEVNULL
            )
            for line in out.strip().splitlines():
                parts = line.strip().split('|', 2)
                if len(parts) == 3:
                    try:
                        table[int(parts[0])] = (int(parts[1]), parts[2].lower())
                    except ValueError:
                        pass
        except Exception:
            pass
    else:
        try:
            out = subprocess.check_output(
                ['ps', '-eo', 'pid=,ppid=,comm='],
                encoding='utf-8', timeout=5,
                stderr=subprocess.DEVNULL
            )
            for line in out.strip().splitlines():
                parts = line.split(None, 2)
                if len(parts) >= 3:
                    try:
                        table[int(parts[0])] = (int(parts[1]), os.path.basename(parts[2]).lower())
                    except ValueError:
                        pass
        except Exception:
            pass
    return table


# Module-level cache, populated on first use
_process_table = None


def get_process_parent_and_name(pid):
    """Return (parent_pid, process_name) for a given PID, or (None, None)."""
    global _process_table
    if _process_table is None:
        _process_table = _load_process_table()
    entry = _process_table.get(pid)
    if entry:
        return entry
    return None, None


def find_shell_pid():
    """Find the terminal tab's shell PID.

    On Windows: walks the process tree to find the shell whose parent is a
    terminal host (WindowsTerminal, conhost, etc.).

    On Unix: walks up to find the shell whose parent is a terminal emulator
    or init/launchd (PID 1), which is the tab's root shell.

    Safety: verifies the shell doesn't own multiple Claude processes.
    """
    global _process_table
    _process_table = None  # Force fresh snapshot
    if IS_WIN:
        return _find_shell_pid_windows()
    else:
        return _find_shell_pid_unix()


def _find_shell_pid_windows():
    shell_names = ('bash.exe', 'powershell.exe', 'pwsh.exe', 'cmd.exe')
    terminal_hosts = ('windowsterminal.exe', 'conhost.exe', 'openconsole.exe')

    pid = os.getpid()
    chain = []
    for _ in range(20):
        parent_pid, my_name = get_process_parent_and_name(pid)
        if parent_pid is None or parent_pid == 0:
            break
        chain.append((pid, my_name))
        pid = parent_pid
    _, top_name = get_process_parent_and_name(pid)
    if top_name:
        chain.append((pid, top_name))

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
    claude_children = sum(
        1 for (ppid, name) in _process_table.values()
        if ppid == tab_shell and 'claude' in name
    )
    if claude_children > 1:
        log(f"SAFETY: shell PID {tab_shell} owns {claude_children} Claude processes - NOT killing")
        return None

    return tab_shell


def _find_shell_pid_unix():
    shell_names = ('bash', 'zsh', 'fish', 'sh', 'dash')
    terminal_hosts = (
        'gnome-terminal-', 'gnome-terminal', 'konsole', 'xfce4-terminal',
        'terminal', 'iterm2', 'alacritty', 'kitty', 'wezterm', 'tmux',
        'screen', 'login', 'sshd', 'init', 'launchd', 'systemd',
    )

    pid = os.getpid()
    chain = []
    for _ in range(20):
        parent_pid, my_name = get_process_parent_and_name(pid)
        if parent_pid is None or parent_pid == 0:
            break
        chain.append((pid, my_name))
        pid = parent_pid
    _, top_name = get_process_parent_and_name(pid)
    if top_name:
        chain.append((pid, top_name))

    tab_shell = None
    for i, (cpid, name) in enumerate(chain):
        if name in shell_names and i + 1 < len(chain):
            _, parent_name = chain[i + 1]
            if any(parent_name.startswith(t) for t in terminal_hosts) or chain[i + 1][0] == 1:
                tab_shell = cpid
                log(f"  tab shell: PID {cpid} ({name}), parent {chain[i + 1]}")
                break

    if tab_shell is None:
        log("  could not identify tab shell in process chain:")
        for cpid, name in chain:
            log(f"    PID {cpid}: {name}")
        return None

    # Safety: verify this shell doesn't own multiple Claude processes
    claude_children = sum(
        1 for (ppid, name) in _process_table.values()
        if ppid == tab_shell and name == 'claude'
    )
    if claude_children > 1:
        log(f"SAFETY: shell PID {tab_shell} owns {claude_children} Claude processes - NOT killing")
        return None

    return tab_shell


# ============ Platform: Tab Launch ============

def build_launch_cmd(project_dir, prompt, tab_title, tab_color):
    """Build the command to open a new terminal tab with claude."""
    if IS_WIN:
        # PowerShell single-quote escaping: double the single quotes
        ps_escaped = prompt.replace("'", "''")
        # Also sanitize tab title (could contain quotes from TODO.md)
        safe_title = tab_title.replace('"', '').replace("'", "")
        return (
            f'wt new-tab --title "{safe_title}" '
            f'--tabColor "{tab_color}" '
            f'--startingDirectory "{project_dir}" '
            f"powershell -NoExit -Command \"claude '{ps_escaped}'\""
        )
    elif IS_MAC:
        escaped = prompt.replace("'", "'\\''")
        return (
            f"""osascript -e 'tell application "Terminal" to do script """
            f""""cd \\"{project_dir}\\" && claude \\'{escaped}\\'"'"""
        )
    else:
        escaped = prompt.replace("'", "'\\''")
        # Try gnome-terminal first, fall back to background process
        if _has_command('gnome-terminal'):
            return (
                f"gnome-terminal --tab --title '{tab_title}' "
                f"-- bash -c 'cd \"{project_dir}\" && claude '\"'\"'{escaped}'\"'\"''"
            )
        else:
            return f"bash -c 'cd \"{project_dir}\" && claude '\"'\"'{escaped}'\"'\"'' &"


def _has_command(name):
    """Check if a command exists on PATH."""
    try:
        subprocess.check_output(['which', name], stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


# ============ Platform: Kill Old Tab ============

def kill_old_tab(shell_pid, close_tab=False):
    """Kill the old tab's shell process tree.

    On Windows: launches a detached Python subprocess to taskkill the tree,
    because taskkill /T would kill us too. Optionally toggles WT closeOnExit.

    On Unix: sends SIGTERM to the shell's process group.
    """
    if IS_WIN:
        _kill_old_tab_windows(shell_pid, close_tab)
    else:
        _kill_old_tab_unix(shell_pid)


def _kill_old_tab_windows(shell_pid, close_tab):
    wt_changed = False
    if close_tab:
        wt_changed = set_wt_close_on_exit("always")
    log("=== Context reset complete ===")

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


def _kill_old_tab_unix(shell_pid):
    log("=== Context reset complete ===")
    try:
        os.killpg(os.getpgid(shell_pid), signal.SIGTERM)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Fall back to killing just the shell
        try:
            os.kill(shell_pid, signal.SIGTERM)
        except Exception:
            pass
    sys.exit(0)


# ============ Transcript Verification ============

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
                        help="Auto-close terminal tab (Windows: sets WT closeOnExit=always temporarily)")
    parser.add_argument("--timeout", type=int, default=45, help="Phase 2 verification timeout in seconds")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cleanup_old_logs()

    project_dir = os.path.abspath(args.project_dir)
    prompt = args.prompt or build_prompt(project_dir)
    project_name = os.path.basename(project_dir)

    log(f"=== Context reset started for {project_name} ===")
    log(f"Project dir: {project_dir}")
    log(f"Platform: {sys.platform}")
    log(f"Prompt: {prompt[:80]}...")
    log(f"Close old tab: {not args.no_close}")

    # Tab title: first unchecked TODO item, or project name as fallback
    first_todo = get_first_todo(project_dir)
    tab_title = first_todo or project_name
    tab_color = get_tab_color(project_dir)
    log(f"Tab: title='{tab_title}', color={tab_color}")

    cmd = build_launch_cmd(project_dir, prompt, tab_title, tab_color)

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
            kill_old_tab(shell_pid, close_tab=args.close_tab)
        else:
            log("WARNING: could not find shell PID, keeping old tab open")
            log("=== Context reset PARTIAL (new tab working, old tab kept) ===")
    else:
        log(f"WARNING: no transcript activity after {args.timeout}s, keeping old tab open")
        log("=== Context reset FAILED (no activity detected) ===")


if __name__ == "__main__":
    main()
