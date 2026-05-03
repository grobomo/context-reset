#!/usr/bin/env python3
"""Context reset: same-project reset that always closes the old tab.

Thin wrapper around new_session.py --close-old-tab.
For cross-project sessions (keeping old tab open), use new_session.py directly.
"""
import sys
sys.argv.insert(1, '--close-old-tab')
from new_session import main
main()
