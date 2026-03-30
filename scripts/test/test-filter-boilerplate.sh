#!/usr/bin/env bash
# Test that raw JSONL tail reads from end of file, not beginning
set -euo pipefail
cd "$(dirname "$0")/../.."
python -c "
import json, tempfile, os, sys
sys.path.insert(0, '.')
from context_reset import extract_session_context, get_project_logs_dir

# Create 500 JSONL entries, extract last 200, verify we get end not beginning
with tempfile.TemporaryDirectory() as tmpdir:
    proj = os.path.join(tmpdir, 'testproj')
    os.makedirs(proj)

    slug = os.path.abspath(proj).replace(os.sep, '-').replace(':', '-')
    if slug.startswith('-'):
        slug = slug[1:]
    import pathlib
    logs_dir = os.path.join(pathlib.Path.home(), '.claude', 'projects', slug)
    os.makedirs(logs_dir, exist_ok=True)

    jsonl_path = os.path.join(logs_dir, 'test-session.jsonl')
    with open(jsonl_path, 'w') as f:
        for i in range(500):
            f.write(json.dumps({'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': f'msg-{i}'}]}}) + '\n')

    result = extract_session_context(proj, max_lines=200)

    os.remove(jsonl_path)
    try:
        os.rmdir(logs_dir)
    except:
        pass

    lines = [l for l in result.split('\n') if l.strip()]
    assert len(lines) == 200, f'Expected 200 lines, got {len(lines)}'
    assert 'msg-0' not in result, f'Beginning of file leaked into tail'
    assert 'msg-299' not in result, f'Entry before tail window leaked in'
    assert 'msg-300' in lines[0], f'Tail should start at msg-300, got: {lines[0][:80]}'
    assert 'msg-499' in lines[-1], f'Tail should end at msg-499, got: {lines[-1][:80]}'

    print('PASS: raw JSONL tail reads last 200 lines from end of file')
"
