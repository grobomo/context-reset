#!/usr/bin/env python3
"""Add the context-reset stop hook to Claude Code settings.json."""
import json
import os
import sys

settings_file = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
os.makedirs(os.path.dirname(settings_file), exist_ok=True)

hook = {"type": "command", "command": "new-session --project-dir $CLAUDE_PROJECT_DIR"}

if os.path.exists(settings_file):
    with open(settings_file, "r", encoding="utf-8-sig") as f:
        settings = json.load(f)
    stops = settings.get("hooks", {}).get("Stop", [])
    if any("new-session" in h.get("command", "") for h in stops):
        print("SKIP")
        sys.exit(0)
    settings.setdefault("hooks", {}).setdefault("Stop", []).append(hook)
    print("ADDED")
else:
    settings = {"hooks": {"Stop": [hook]}}
    print("CREATED")

with open(settings_file, "w", encoding="utf-8") as f:
    json.dump(settings, f, indent=2)
