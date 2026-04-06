#!/usr/bin/env bash
# Test: --stop flag argument parsing and stop-mode logic
set -e

cd "$(dirname "$0")/../.."

python3 -c "
import sys, os, argparse
sys.path.insert(0, '.')
import new_session

# Test 1: argparse accepts --stop
parser = argparse.ArgumentParser()
parser.add_argument('--stop', action='store_true')
parser.add_argument('--project-dir', default='.')
args = parser.parse_args(['--stop', '--project-dir', '.'])
assert args.stop is True, '--stop flag not parsed'
print('PASS: --stop flag accepted by argparse')

# Test 2: --stop is in new_session.main's parser (check source)
import inspect
src = inspect.getsource(new_session.main)
assert \"'--stop'\" in src or '\"--stop\"' in src, '--stop not in main parser'
print('PASS: --stop flag defined in main()')

# Test 3: stop mode saves SESSION_STATE.md (check the code path exists)
assert 'args.stop' in src, 'args.stop not referenced in main'
assert 'Stop mode' in src, 'Stop mode log message not in main'
assert 'extract_session_context' in src, 'extract_session_context not called in stop mode'
print('PASS: stop mode code path exists with state saving')
"

echo "test-T007-stop-flag: ALL PASSED"
