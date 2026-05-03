#!/usr/bin/env python3
"""context_reset.py — Same-project context reset; ALWAYS closes the calling tab.

Use this when you want to drop a long context and start fresh in the same
project. The new tab launches, gets verified, then this tab is killed.

For cross-project session switching (keeping the calling tab running), use
new_session.py instead.
"""

from new_session import context_reset_main as main

if __name__ == "__main__":
    main()
