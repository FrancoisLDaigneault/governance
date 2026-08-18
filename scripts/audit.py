"""Thin wrapper - logic lives in src/governance_tools/audit.py."""

import sys

from governance_tools.audit import main

if __name__ == "__main__":
    sys.exit(main())
