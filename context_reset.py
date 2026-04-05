#!/usr/bin/env python3
"""Backward-compat alias: context_reset.py -> new_session.py

All logic lives in new_session.py. This file exists so existing hooks
and scripts that reference context_reset.py continue to work.

Re-exports everything (including _private names) so `import context_reset`
is a full drop-in for `import new_session`.
"""

import new_session as _ns

# Re-export ALL names from new_session (including _private ones)
# so tests and hooks that do `context_reset._tail_lines` still work.
for _name in dir(_ns):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_ns, _name)

# Also make `from context_reset import X` work for any name
def __getattr__(name):
    return getattr(_ns, name)

if __name__ == "__main__":
    _ns.main()
