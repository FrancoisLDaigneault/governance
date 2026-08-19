"""Thin wrapper - logic lives in src/governance_tools/scheduled_audit.py."""

import sys

from governance_tools.scheduled_audit import main

if __name__ == "__main__":
    sys.exit(main())
