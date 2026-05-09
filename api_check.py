#!/usr/bin/env python3
"""API health check and retry utility for Claude Code sessions.

Detects when the Anthropic API is unreachable, polls until recovery,
and optionally respawns a stalled session via context-reset.

Usage:
    python3 api_check.py --check              # Exit 0=healthy, 1=down
    python3 api_check.py --wait               # Block until healthy
    python3 api_check.py --watch PROJECT_DIR  # Full watcher: stall + wait + respawn
"""

import argparse
import os
import socket
import subprocess
import sys
import time
from datetime import datetime

DEFAULT_HOST = "api.anthropic.com"
DEFAULT_PORT = 443
DEFAULT_PROXY_HOST = "127.0.0.1"
DEFAULT_PROXY_PORT = 4100
DEFAULT_INTERVAL = 60
DEFAULT_MAX_WAIT = 1800
DEFAULT_STALL_THRESHOLD = 120

LOG_DIR = os.path.join(os.path.expanduser("~"), ".claude", "context-reset")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[api-check] [{ts}] {msg}")
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        logfile = os.path.join(LOG_DIR, f"{today}.log")
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [api-check] {msg}\n")
    except Exception:
        pass


def check_api_health(host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=5):
    """TCP connect to API endpoint. Returns True if reachable."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, socket.error, OSError):
        return False


def diagnose(proxy_host=DEFAULT_PROXY_HOST, proxy_port=DEFAULT_PROXY_PORT,
             upstream_host=DEFAULT_HOST, upstream_port=DEFAULT_PORT, timeout=5):
    """Two-layer health check: proxy + upstream. Returns diagnosis dict.

    Returns:
        {"proxy": bool, "upstream": bool, "detail": str, "cause": str}
        cause is one of: "healthy", "proxy_down", "upstream_down", "both_down"
    """
    import urllib.request
    import json as _json

    result = {"proxy": False, "upstream": False, "detail": "", "cause": "both_down"}

    # Layer 1: Check proxy /health endpoint (returns upstream status too)
    try:
        url = f"http://{proxy_host}:{proxy_port}/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = _json.loads(resp.read().decode())
            result["proxy"] = True
            result["upstream"] = data.get("upstream") == "reachable"
            if result["upstream"]:
                result["cause"] = "healthy"
                result["detail"] = "Proxy and upstream both healthy"
            else:
                result["cause"] = "upstream_down"
                result["detail"] = f"Proxy OK, upstream unreachable (checked by proxy)"
            return result
    except Exception:
        pass

    # Proxy didn't respond — check upstream directly
    result["upstream"] = check_api_health(upstream_host, upstream_port, timeout)
    if result["upstream"]:
        result["cause"] = "proxy_down"
        result["detail"] = (f"Proxy at {proxy_host}:{proxy_port} is down, "
                            f"but {upstream_host} is reachable directly")
    else:
        result["cause"] = "both_down"
        result["detail"] = (f"Both proxy ({proxy_host}:{proxy_port}) and "
                            f"upstream ({upstream_host}) are unreachable")
    return result


def wait_for_api(interval=DEFAULT_INTERVAL, max_wait=DEFAULT_MAX_WAIT,
                 host=DEFAULT_HOST, port=DEFAULT_PORT, check_timeout=5):
    """Poll until API is healthy. Returns True if recovered, False on timeout."""
    if check_api_health(host, port, timeout=check_timeout):
        return True

    start = time.time()
    attempt = 0
    while time.time() - start < max_wait:
        attempt += 1
        elapsed = int(time.time() - start)
        log(f"API unreachable, retrying in {interval}s "
            f"(attempt {attempt}, {elapsed}s elapsed, max {max_wait}s)")
        time.sleep(interval)
        if check_api_health(host, port, timeout=check_timeout):
            log(f"API recovered after {int(time.time() - start)}s ({attempt} attempts)")
            return True

    log(f"API did not recover within {max_wait}s ({attempt} attempts)")
    return False


def _get_newest_transcript(project_dir):
    """Find the newest .jsonl transcript for a project."""
    import re
    home = os.path.expanduser("~")
    slug = re.sub(r'[^a-zA-Z0-9-]', '-', os.path.abspath(project_dir))
    logs_dir = os.path.join(home, ".claude", "projects", slug)
    if not os.path.isdir(logs_dir):
        return None
    jsonls = [f for f in os.listdir(logs_dir) if f.endswith(".jsonl")]
    if not jsonls:
        return None
    newest = max(jsonls, key=lambda f: os.path.getmtime(os.path.join(logs_dir, f)))
    return os.path.join(logs_dir, newest)


def is_session_stalled(project_dir, threshold_s=DEFAULT_STALL_THRESHOLD):
    """Check if the newest transcript hasn't grown in threshold_s seconds."""
    transcript = _get_newest_transcript(project_dir)
    if not transcript or not os.path.exists(transcript):
        return False
    age = time.time() - os.path.getmtime(transcript)
    return age > threshold_s


def watch_and_respawn(project_dir, interval=DEFAULT_INTERVAL,
                      max_wait=DEFAULT_MAX_WAIT,
                      stall_threshold=DEFAULT_STALL_THRESHOLD):
    """Full watcher: detect stall, check API, wait for recovery, respawn.

    Returns True if respawn was triggered, False on timeout or no stall.
    """
    log(f"Watching {project_dir} (stall>{stall_threshold}s, poll={interval}s, max={max_wait}s)")

    if not is_session_stalled(project_dir, stall_threshold):
        log("Session is active (not stalled), nothing to do")
        return False

    log("Session stalled, checking API health...")
    if check_api_health():
        log("API is healthy but session stalled — may be a different issue")
        return False

    log("API is down and session is stalled. Waiting for recovery...")
    recovered = wait_for_api(interval=interval, max_wait=max_wait)
    if not recovered:
        log("API did not recover within timeout. Giving up.")
        return False

    log("API recovered! Spawning fresh session via context-reset...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    reset_script = os.path.join(script_dir, "new_session.py")
    cmd = [
        sys.executable, reset_script,
        "--close-old-tab",
        "--project-dir", project_dir,
        "--reason", "api-retry: recovered after outage",
    ]
    log(f"Running: {' '.join(cmd)}")
    subprocess.Popen(cmd)
    return True


def main():
    parser = argparse.ArgumentParser(description="API health check and retry utility")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="Check API health (exit 0=up, 1=down)")
    group.add_argument("--diagnose", action="store_true",
                       help="Two-layer check: proxy + upstream (shows root cause)")
    group.add_argument("--wait", action="store_true",
                       help="Block until API is healthy")
    group.add_argument("--watch", metavar="PROJECT_DIR",
                       help="Watch project for stall + API outage, respawn on recovery")

    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help=f"Poll interval in seconds (default: {DEFAULT_INTERVAL})")
    parser.add_argument("--max-wait", type=int, default=DEFAULT_MAX_WAIT,
                        help=f"Max wait time in seconds (default: {DEFAULT_MAX_WAIT})")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"API host to check (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"API port to check (default: {DEFAULT_PORT})")
    parser.add_argument("--proxy-host", default=DEFAULT_PROXY_HOST,
                        help=f"Proxy host (default: {DEFAULT_PROXY_HOST})")
    parser.add_argument("--proxy-port", type=int, default=DEFAULT_PROXY_PORT,
                        help=f"Proxy port (default: {DEFAULT_PROXY_PORT})")
    args = parser.parse_args()

    if args.check:
        healthy = check_api_health(args.host, args.port)
        if healthy:
            log("API is healthy")
        else:
            log("API is unreachable")
        sys.exit(0 if healthy else 1)

    elif args.diagnose:
        result = diagnose(
            proxy_host=args.proxy_host, proxy_port=args.proxy_port,
            upstream_host=args.host, upstream_port=args.port,
        )
        log(f"Diagnosis: {result['cause']} — {result['detail']}")
        log(f"  Proxy ({args.proxy_host}:{args.proxy_port}): {'UP' if result['proxy'] else 'DOWN'}")
        log(f"  Upstream ({args.host}): {'UP' if result['upstream'] else 'DOWN'}")
        sys.exit(0 if result["cause"] == "healthy" else 1)

    elif args.wait:
        recovered = wait_for_api(
            interval=args.interval,
            max_wait=args.max_wait,
            host=args.host,
            port=args.port,
        )
        sys.exit(0 if recovered else 1)

    elif args.watch:
        project_dir = os.path.abspath(args.watch)
        if not os.path.isdir(project_dir):
            log(f"ERROR: directory does not exist: {project_dir}")
            sys.exit(1)
        respawned = watch_and_respawn(
            project_dir,
            interval=args.interval,
            max_wait=args.max_wait,
        )
        sys.exit(0 if respawned else 1)


if __name__ == "__main__":
    main()
