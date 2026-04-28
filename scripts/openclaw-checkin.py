#!/usr/bin/env python3
"""Claude Code -> OpenClaw checkin API with communication logging.

Every call is logged to ~/.openclaw/comms/claude-code.jsonl with:
- timestamp, direction, message, result, latency, errors
- OpenClaw (or any tool) can query the log to verify delivery

Usage (positional shorthand -- fire-and-forget by default):
    openclaw-checkin done "PR #17, 12/12 tests pass"
    openclaw-checkin blocked "token expired"
    openclaw-checkin progress "working on parser"

Usage (flags):
    openclaw-checkin --status done --task T035 --detail "PR #17, 12/12 tests pass"
    openclaw-checkin --message "Starting work on project"
    openclaw-checkin --check-connectivity
    openclaw-checkin --wait            # Wait for OpenClaw reply (default is fire-and-forget)

Auto-detection:
    - Project name from CLAUDE_PROJECT_DIR env var
    - Task ID from TODO.md (first unchecked T### item)

Environment:
    OPENCLAW_URL     API endpoint (default: http://localhost:18789/v1/chat/completions)
    OPENCLAW_TOKEN   Auth token (default: read from ~/.openclaw/openclaw.json)
    OPENCLAW_MODEL   Model name (default: openclaw)
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

COMMS_LOG = Path.home() / ".openclaw" / "comms" / "claude-code.jsonl"
TRACKER_PATH = Path(os.environ.get(
    "OPENCLAW_TRACKER_PATH",
    str(Path.home() / ".openclaw" / "workspace" / "scripts" / "claude-tabs" / "tracker.json")
))
VALID_STATUSES = ("done", "blocked", "progress", "tests", "error")


def _update_tracker(status: str, detail: str, project: str):
    """Update tracker.json with checkin info. Never raises — silent on any error."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        project_name = os.path.basename(project.rstrip("/")) if project else ""
        if not project_name:
            return

        # Read current tracker state
        try:
            with open(TRACKER_PATH) as f:
                tracker = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return  # Can't find tracker; bail silently

        tabs = tracker.get("tabs", [])
        matched = False
        for tab in tabs:
            if tab.get("project_name") == project_name and tab.get("status") not in ("completed", "archived"):
                tab["last_checkin"] = now
                if "checkins" not in tab or not isinstance(tab["checkins"], list):
                    tab["checkins"] = []
                tab["checkins"].append({
                    "timestamp": now,
                    "status": status,
                    "detail": detail or "",
                    "task": tab.get("task_id") or tab.get("task", ""),
                })
                if status == "done":
                    tab["status"] = "completed"
                    tab["completed_at"] = now
                    tab["summary"] = detail or ""
                matched = True
                break  # Update first matching active tab only

        if not matched:
            return  # No active tab for this project; nothing to update

        # Atomic write: write to .tmp then rename
        tmp_path = TRACKER_PATH.with_suffix(".json.tmp")
        with open(tmp_path, "w") as f:
            json.dump(tracker, f, indent=2)
        tmp_path.rename(TRACKER_PATH)

    except Exception:
        pass  # Never break the checkin flow


def _log_comms(entry: dict):
    """Append a communication entry to the JSONL log."""
    entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
    try:
        COMMS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(COMMS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # logging should never break the checkin


def read_token():
    """Read gateway auth token from openclaw.json."""
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(config_path) as f:
            config = json.load(f)
        return config.get("gateway", {}).get("auth", {}).get("token", "")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return ""


def detect_task_from_todo():
    """Find first unchecked task ID from TODO.md in CLAUDE_PROJECT_DIR."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return None
    todo_path = os.path.join(project_dir, "TODO.md")
    try:
        with open(todo_path) as f:
            for line in f:
                m = re.match(r"^\s*- \[ \] (T\d+):", line)
                if m:
                    return m.group(1)
    except (FileNotFoundError, PermissionError):
        pass
    return None


def check_connectivity(url=None, token=None):
    """Test OpenClaw connectivity without sending a chat message."""
    url = url or os.environ.get(
        "OPENCLAW_URL", "http://localhost:18789/v1/chat/completions"
    )
    token = token or os.environ.get("OPENCLAW_TOKEN") or read_token()

    base_url = url.rsplit("/", 2)[0]
    models_url = f"{base_url}/v1/models"

    results = {}

    t0 = time.monotonic()
    try:
        req = urllib.request.Request(models_url)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            results["models"] = {"status": resp.status, "latency_ms": int((time.monotonic() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        results["models"] = {"status": e.code, "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        results["models"] = {"error": str(e), "latency_ms": int((time.monotonic() - t0) * 1000)}

    t0 = time.monotonic()
    body = json.dumps({
        "model": os.environ.get("OPENCLAW_MODEL", "openclaw"),
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            results["chat"] = {"status": resp.status, "latency_ms": int((time.monotonic() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        results["chat"] = {"status": e.code, "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        results["chat"] = {"error": str(e), "latency_ms": int((time.monotonic() - t0) * 1000)}

    _log_comms({"dir": "out", "type": "connectivity_check", "results": results})
    return results


def send_to_openclaw(message, url=None, token=None, model=None, timeout=120,
                     fire_and_forget=False):
    """POST a message to OpenClaw's chat API. Returns reply text or None."""
    url = url or os.environ.get(
        "OPENCLAW_URL", "http://localhost:18789/v1/chat/completions"
    )
    token = token or os.environ.get("OPENCLAW_TOKEN") or read_token()
    model = model or os.environ.get("OPENCLAW_MODEL", "openclaw")

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 512,
    }).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    log_entry = {
        "dir": "out",
        "type": "checkin",
        "message": message[:300],
    }
    t0 = time.monotonic()

    if fire_and_forget:
        try:
            urllib.request.urlopen(req, timeout=5)
            latency = int((time.monotonic() - t0) * 1000)
            log_entry.update(result="delivered", latency_ms=latency)
            _log_comms(log_entry)
            return "delivered"
        except urllib.error.HTTPError as e:
            latency = int((time.monotonic() - t0) * 1000)
            log_entry.update(result="http_error", error=f"HTTP {e.code}", latency_ms=latency)
            _log_comms(log_entry)
            return f"error: HTTP {e.code}"
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            is_timeout = "timed out" in str(e)
            log_entry.update(
                result="timeout" if is_timeout else "error",
                error=f"{type(e).__name__}: {e}",
                latency_ms=latency,
            )
            _log_comms(log_entry)
            if is_timeout:
                return "queued (gateway accepted, LLM busy)"
            return f"error: {e}"

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.monotonic() - t0) * 1000)
            result = json.loads(resp.read())
            reply = result["choices"][0]["message"]["content"].strip()
            log_entry.update(result="delivered", http_status=resp.status,
                             latency_ms=latency, reply=reply[:200])
            _log_comms(log_entry)
            return reply
    except urllib.error.HTTPError as e:
        latency = int((time.monotonic() - t0) * 1000)
        log_entry.update(result="http_error", error=f"HTTP {e.code}", latency_ms=latency)
        _log_comms(log_entry)
        print(f"OpenClaw HTTP error: {e.code}", file=sys.stderr)
        return None
    except Exception as e:
        latency = int((time.monotonic() - t0) * 1000)
        log_entry.update(result="error", error=str(e), latency_ms=latency)
        _log_comms(log_entry)
        print(f"OpenClaw error: {e}", file=sys.stderr)
        return None


def format_status(status, task, detail, project=None):
    """Format a structured status message for OpenClaw."""
    project = project or os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project:
        project = os.path.basename(project)

    parts = [f"[CLAUDE-CHECKIN] status={status}"]
    if task:
        parts.append(f"task={task}")
    if project:
        parts.append(f"project={project}")
    if detail:
        parts.append(f"detail={detail}")
    return " | ".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Report status from Claude Code to OpenClaw",
        usage="%(prog)s [status] [detail] [options]\n"
              "  %(prog)s done \"PR merged, tests pass\"\n"
              "  %(prog)s blocked \"token expired\"\n"
              "  %(prog)s --message \"free-form message\"",
    )
    parser.add_argument("positional_status", nargs="?", metavar="STATUS",
                        help=f"Status: {', '.join(VALID_STATUSES)}")
    parser.add_argument("positional_detail", nargs="?", metavar="DETAIL",
                        help="Detail string (positional shorthand)")
    parser.add_argument("--status", choices=VALID_STATUSES,
                        help="Status type (flag form)")
    parser.add_argument("--task", help="Task ID (e.g. T035). Auto-detected from TODO.md if omitted.")
    parser.add_argument("--detail", help="Details about the status (flag form)")
    parser.add_argument("--project", help="Project name (default: from CLAUDE_PROJECT_DIR)")
    parser.add_argument("--message", help="Free-form message (overrides --status)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress OpenClaw's reply output")
    parser.add_argument("--wait", "-w", action="store_true",
                        help="Wait for OpenClaw reply (default is fire-and-forget)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Request timeout in seconds (default 120, only with --wait)")
    parser.add_argument("--check-connectivity", action="store_true",
                        help="Test OpenClaw connectivity and exit")
    # Accepted but ignored — kept for backwards compatibility with openclaw-checkin.js
    parser.add_argument("--fire-and-forget", action="store_true",
                        help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.check_connectivity:
        results = check_connectivity()
        print("OpenClaw Connectivity Check:")
        for endpoint, data in results.items():
            status = data.get("status", data.get("error", "unknown"))
            latency = data.get("latency_ms", "?")
            print(f"  {endpoint}: {status} ({latency}ms)")
        models_ok = results.get("models", {}).get("status") in (200, 401)
        chat_ok = results.get("chat", {}).get("status") == 200
        if chat_ok:
            print("  Result: FULLY REACHABLE (chat API responds)")
        elif models_ok:
            print("  Result: SERVER UP, CHAT BUSY (gateway accepts but LLM not responding)")
        else:
            print("  Result: UNREACHABLE")
        sys.exit(0 if models_ok else 1)

    # Merge positional and flag-based args (positional wins if both given)
    status = args.positional_status or args.status
    detail = args.positional_detail or args.detail

    # Validate positional status
    if args.positional_status and args.positional_status not in VALID_STATUSES:
        parser.error(f"Invalid status '{args.positional_status}'. Must be one of: {', '.join(VALID_STATUSES)}")

    if not args.message and not status:
        parser.error("Either a status or --message is required")

    # Auto-detect task from TODO.md if not provided
    task = args.task or detect_task_from_todo()

    if args.message:
        message = args.message
    else:
        message = format_status(status, task, detail, args.project)

    # Update tracker.json before sending to OpenClaw (tracker write is always fast/local)
    project = args.project or os.environ.get("CLAUDE_PROJECT_DIR", "")
    if status:  # only update tracker for structured status messages
        _update_tracker(status, detail or "", project)

    fire_and_forget = not args.wait
    reply = send_to_openclaw(message, timeout=args.timeout,
                             fire_and_forget=fire_and_forget)

    if reply is None:
        print("CHECKIN FAILED: OpenClaw unreachable", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(f"OpenClaw: {reply}")

    sys.exit(0)


if __name__ == "__main__":
    main()
