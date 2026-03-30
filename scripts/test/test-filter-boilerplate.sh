#!/usr/bin/env bash
# Test that boilerplate prompts are filtered from transcript tail
set -euo pipefail
cd "$(dirname "$0")/../.."
python -c "
import json, tempfile, os, sys
sys.path.insert(0, '.')
from context_reset import extract_session_context, get_project_logs_dir, get_newest_jsonl

# Create a fake JSONL transcript with boilerplate + real content
lines = []

# Boilerplate: context reset prompt (should be filtered)
lines.append(json.dumps({'message': {'role': 'user', 'content': [{'type': 'text', 'text': 'Context was reset. Do not ask what to do. Pick up where the last session left off.'}]}}))

# Boilerplate: session start hook (should be filtered)
lines.append(json.dumps({'message': {'role': 'user', 'content': [{'type': 'text', 'text': 'SESSION START INSTRUCTIONS: Check TODO.md in \$CLAUDE_PROJECT_DIR for pending tasks.'}]}}))

# Real content (should be kept)
lines.append(json.dumps({'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Working on the CF template now.'}]}}))
lines.append(json.dumps({'message': {'role': 'user', 'content': [{'type': 'text', 'text': 'Add the S3 bucket policy too.'}]}}))
lines.append(json.dumps({'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Done, added the bucket policy.'}]}}))

# Write to a temp project dir mimicking the logs structure
with tempfile.TemporaryDirectory() as tmpdir:
    # Create fake project
    proj = os.path.join(tmpdir, 'testproj')
    os.makedirs(proj)

    # Compute logs dir the same way context_reset does
    slug = os.path.abspath(proj).replace(os.sep, '-').replace(':', '-')
    if slug.startswith('-'):
        slug = slug[1:]
    import pathlib
    logs_dir = os.path.join(pathlib.Path.home(), '.claude', 'projects', slug)
    os.makedirs(logs_dir, exist_ok=True)

    jsonl_path = os.path.join(logs_dir, 'test-session.jsonl')
    with open(jsonl_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    # Extract context
    result = extract_session_context(proj)

    # Cleanup
    os.remove(jsonl_path)
    try:
        os.rmdir(logs_dir)
    except:
        pass

    # Verify boilerplate is filtered
    assert 'Context was reset' not in result, f'Context reset prompt leaked through: {result}'
    assert 'SESSION START INSTRUCTIONS' not in result, f'Session start hook leaked through: {result}'

    # Verify real content is kept
    assert 'Working on the CF template' in result, f'Real assistant content missing: {result}'
    assert 'Add the S3 bucket policy' in result, f'Real user content missing: {result}'
    assert 'Done, added the bucket policy' in result, f'Real assistant content missing: {result}'

    print('PASS: boilerplate filtered, real content preserved')
"
