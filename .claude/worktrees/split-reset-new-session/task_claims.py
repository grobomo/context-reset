#!/usr/bin/env python3
"""
Task Claims: Multi-tab work negotiation for Claude Code.

Prevents duplicate effort when multiple Claude tabs work on the same project.
Each tab claims a task atomically before starting. Other tabs skip claimed tasks.

Usage from Claude hooks/scripts:
    python task_claims.py claim T034 --session $SESSION_ID --project-dir /path
    python task_claims.py release T034 --session $SESSION_ID --project-dir /path
    python task_claims.py next --session $SESSION_ID --project-dir /path
    python task_claims.py status --project-dir /path
    python task_claims.py stats --project-dir /path

Claims stored in: ~/.claude/task-claims/{project-key}.json
Uses OS-level file locking for atomicity (msvcrt on Windows, fcntl on Unix).
Dead sessions auto-released via PID check.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

IS_WIN = sys.platform == "win32"
CLAIMS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "task-claims")
# Activity log for productivity tracking
ACTIVITY_LOG = os.path.join(os.path.expanduser("~"), ".claude", "task-claims", "activity.jsonl")


def _project_key(project_dir):
    """Convert project path to a safe filename key."""
    return os.path.abspath(project_dir).replace(os.sep, "-").replace(":", "").strip("-")


def _claims_file(project_dir):
    os.makedirs(CLAIMS_DIR, exist_ok=True)
    return os.path.join(CLAIMS_DIR, f"{_project_key(project_dir)}.json")


def _lock_file(project_dir):
    return _claims_file(project_dir) + ".lock"


def _acquire_lock(project_dir):
    """Acquire OS-level exclusive lock. Returns (file_handle, lock_path)."""
    lock_path = _lock_file(project_dir)
    fh = open(lock_path, "w")
    try:
        if IS_WIN:
            import msvcrt
            # Retry up to 3 seconds (non-blocking lock)
            for _ in range(30):
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    return fh, lock_path
                except IOError:
                    time.sleep(0.1)
            raise IOError("Lock timeout after 3s")
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX)  # Blocking on Unix
            return fh, lock_path
    except Exception:
        fh.close()
        raise


def _release_lock(fh, lock_path):
    """Release OS-level lock."""
    try:
        if IS_WIN:
            import msvcrt
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        fh.close()
    except Exception:
        pass
    try:
        os.remove(lock_path)
    except Exception:
        pass


def _read_claims(project_dir):
    """Read claims file. Returns dict of task_id -> claim_info."""
    path = _claims_file(project_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _write_claims(project_dir, claims):
    """Write claims file atomically."""
    path = _claims_file(project_dir)
    with open(path, "w") as f:
        json.dump(claims, f, indent=2)


def _is_pid_alive(pid):
    """Check if a process is still running."""
    try:
        if IS_WIN:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ProcessLookupError):
        return False


def _is_session_alive(claim):
    """Check if the claiming session is still active (via PID or session file)."""
    pid = claim.get("pid")
    if pid and _is_pid_alive(pid):
        return True
    # Also check if session transcript exists and was modified recently (within 10 min)
    session_id = claim.get("session", "")
    if session_id:
        # Look for active .jsonl in the project's claude folder
        projects_dir = os.path.join(os.path.expanduser("~"), ".claude", "projects")
        if os.path.isdir(projects_dir):
            for folder in os.listdir(projects_dir):
                jsonl_path = os.path.join(projects_dir, folder, f"{session_id}.jsonl")
                if os.path.exists(jsonl_path):
                    age = time.time() - os.path.getmtime(jsonl_path)
                    return age < 600  # Active if modified in last 10 min
    return False


def _cleanup_dead(claims):
    """Remove claims from dead sessions. Returns cleaned claims + list of released task IDs."""
    released = []
    alive = {}
    for task_id, claim in claims.items():
        if _is_session_alive(claim):
            alive[task_id] = claim
        else:
            released.append(task_id)
    return alive, released


def _log_activity(event, task_id, session_id, project_dir, extra=None):
    """Append to activity JSONL for productivity tracking."""
    os.makedirs(CLAIMS_DIR, exist_ok=True)
    entry = {
        "ts": datetime.now().isoformat(),
        "event": event,
        "task": task_id,
        "session": session_id[:12] if session_id else None,
        "project": os.path.basename(project_dir),
        "pid": os.getpid(),
    }
    if extra:
        entry.update(extra)
    try:
        with open(ACTIVITY_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _parse_todo(project_dir):
    """Parse TODO.md for unchecked task items. Returns list of task IDs."""
    todo_path = os.path.join(project_dir, "TODO.md")
    if not os.path.exists(todo_path):
        return []
    tasks = []
    with open(todo_path, "r") as f:
        for line in f:
            # Match unchecked items like "- [ ] T034 ..." or "- [ ] T029: ..."
            m = re.match(r'\s*-\s*\[\s*\]\s*(T\d+)', line)
            if m:
                tasks.append(m.group(1))
    return tasks


# ============ Commands ============


def cmd_claim(task_id, session_id, project_dir, pid=None):
    """Claim a task. Returns True if claimed, False if already taken."""
    fh, lock_path = _acquire_lock(project_dir)
    try:
        claims = _read_claims(project_dir)
        claims, released = _cleanup_dead(claims)
        for r in released:
            _log_activity("auto_release", r, "", project_dir, {"reason": "dead_session"})

        if task_id in claims:
            owner = claims[task_id]
            print(json.dumps({"claimed": False, "owner": owner.get("session", "unknown")[:12],
                               "reason": "already_claimed"}))
            return False

        claims[task_id] = {
            "session": session_id,
            "pid": pid or os.getppid(),
            "claimed_at": datetime.now().isoformat(),
        }
        _write_claims(project_dir, claims)
        _log_activity("claim", task_id, session_id, project_dir)
        print(json.dumps({"claimed": True, "task": task_id}))
        return True
    finally:
        _release_lock(fh, lock_path)


def cmd_release(task_id, session_id, project_dir, status="completed"):
    """Release a task claim."""
    fh, lock_path = _acquire_lock(project_dir)
    try:
        claims = _read_claims(project_dir)
        if task_id in claims:
            claim = claims.pop(task_id)
            _write_claims(project_dir, claims)
            _log_activity("release", task_id, session_id, project_dir, {"status": status})
            print(json.dumps({"released": True, "task": task_id, "status": status}))
            return True
        else:
            print(json.dumps({"released": False, "reason": "not_claimed"}))
            return False
    finally:
        _release_lock(fh, lock_path)


def cmd_next(session_id, project_dir, pid=None):
    """Find and claim the next available unchecked task from TODO.md."""
    todo_tasks = _parse_todo(project_dir)
    if not todo_tasks:
        print(json.dumps({"next": None, "reason": "no_unchecked_tasks"}))
        return None

    fh, lock_path = _acquire_lock(project_dir)
    try:
        claims = _read_claims(project_dir)
        claims, released = _cleanup_dead(claims)
        for r in released:
            _log_activity("auto_release", r, "", project_dir, {"reason": "dead_session"})

        # Find first unchecked task not claimed by another session
        for task_id in todo_tasks:
            if task_id not in claims:
                # Claim it
                claims[task_id] = {
                    "session": session_id,
                    "pid": pid or os.getppid(),
                    "claimed_at": datetime.now().isoformat(),
                }
                _write_claims(project_dir, claims)
                _log_activity("claim", task_id, session_id, project_dir, {"via": "next"})
                print(json.dumps({"next": task_id, "claimed": True}))
                return task_id
            elif claims[task_id].get("session") == session_id:
                # Already claimed by this session
                print(json.dumps({"next": task_id, "claimed": True, "already_mine": True}))
                return task_id

        # All tasks claimed by other sessions
        print(json.dumps({"next": None, "reason": "all_claimed",
                           "claimed_tasks": {k: v.get("session", "?")[:12] for k, v in claims.items()}}))
        return None
    finally:
        _release_lock(fh, lock_path)


def cmd_status(project_dir):
    """Show current claims and available tasks."""
    fh, lock_path = _acquire_lock(project_dir)
    try:
        claims = _read_claims(project_dir)
        claims, released = _cleanup_dead(claims)
        if released:
            _write_claims(project_dir, claims)
        todo_tasks = _parse_todo(project_dir)
    finally:
        _release_lock(fh, lock_path)

    result = {
        "project": os.path.basename(project_dir),
        "unchecked_tasks": todo_tasks,
        "claims": {},
        "available": [],
        "released_dead": released,
    }
    for task_id in todo_tasks:
        if task_id in claims:
            c = claims[task_id]
            result["claims"][task_id] = {
                "session": c.get("session", "?")[:12],
                "pid": c.get("pid"),
                "alive": _is_pid_alive(c.get("pid", 0)),
                "since": c.get("claimed_at", "?"),
            }
        else:
            result["available"].append(task_id)
    print(json.dumps(result, indent=2))


def cmd_stats(project_dir):
    """Productivity stats from activity log."""
    if not os.path.exists(ACTIVITY_LOG):
        print(json.dumps({"error": "no activity log yet"}))
        return

    project_name = os.path.basename(project_dir)
    sessions = {}  # session -> {claims: [], releases: [], first_seen, last_seen}
    total_claims = 0
    total_releases = 0
    auto_releases = 0

    with open(ACTIVITY_LOG, "r") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            if entry.get("project") != project_name:
                continue

            session = entry.get("session", "unknown")
            event = entry.get("event", "")
            ts = entry.get("ts", "")

            if session not in sessions:
                sessions[session] = {"claims": [], "releases": [], "first_seen": ts, "last_seen": ts}
            sessions[session]["last_seen"] = ts

            if event == "claim":
                sessions[session]["claims"].append(entry.get("task"))
                total_claims += 1
            elif event == "release":
                sessions[session]["releases"].append(entry.get("task"))
                total_releases += 1
            elif event == "auto_release":
                auto_releases += 1

    result = {
        "project": project_name,
        "total_claims": total_claims,
        "total_completions": total_releases,
        "auto_released_dead": auto_releases,
        "sessions": {},
    }
    for sid, data in sessions.items():
        result["sessions"][sid] = {
            "tasks_claimed": len(data["claims"]),
            "tasks_completed": len(data["releases"]),
            "tasks": list(set(data["claims"])),
            "active_period": f"{data['first_seen']} → {data['last_seen']}",
        }

    # Overlap detection: did multiple sessions claim the same task?
    task_sessions = {}
    for sid, data in sessions.items():
        for task in data["claims"]:
            task_sessions.setdefault(task, []).append(sid)
    overlaps = {t: sids for t, sids in task_sessions.items() if len(sids) > 1}
    if overlaps:
        result["duplicate_work"] = overlaps

    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Multi-tab task negotiation")
    sub = parser.add_subparsers(dest="command", required=True)

    p_claim = sub.add_parser("claim", help="Claim a task")
    p_claim.add_argument("task_id")
    p_claim.add_argument("--session", required=True)
    p_claim.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    p_claim.add_argument("--pid", type=int, default=None)

    p_release = sub.add_parser("release", help="Release a task")
    p_release.add_argument("task_id")
    p_release.add_argument("--session", required=True)
    p_release.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    p_release.add_argument("--status", default="completed")

    p_next = sub.add_parser("next", help="Claim next available task")
    p_next.add_argument("--session", required=True)
    p_next.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    p_next.add_argument("--pid", type=int, default=None)

    p_status = sub.add_parser("status", help="Show claims status")
    p_status.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

    p_stats = sub.add_parser("stats", help="Productivity stats")
    p_stats.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

    args = parser.parse_args()

    if args.command == "claim":
        cmd_claim(args.task_id, args.session, args.project_dir, args.pid)
    elif args.command == "release":
        cmd_release(args.task_id, args.session, args.project_dir, args.status)
    elif args.command == "next":
        cmd_next(args.session, args.project_dir, args.pid)
    elif args.command == "status":
        cmd_status(args.project_dir)
    elif args.command == "stats":
        cmd_stats(args.project_dir)


if __name__ == "__main__":
    main()
