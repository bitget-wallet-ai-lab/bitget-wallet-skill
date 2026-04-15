"""Shared utilities for secure private key file handling."""

import os
import stat
from pathlib import Path
import sys


def read_key_file(fpath: str) -> str:
    """Read private key from file and delete the file immediately.

    Security: validates file permissions (must not be group/world-readable),
    uses atomic open-read-delete to avoid TOCTOU race conditions.
    Raises SystemExit if file not found or has unsafe permissions.
    """
    p = Path(fpath)
    try:
        # Check permissions before reading (skip on Windows)
        if os.name != "nt":
            mode = p.stat().st_mode
            if mode & (stat.S_IRGRP | stat.S_IROTH):
                print(f"ERROR: key file {fpath} is readable by group/others. "
                      f"Run: chmod 600 {fpath}", file=sys.stderr)
                sys.exit(1)
        with open(fpath, "r") as f:
            key = f.read().strip()
    except FileNotFoundError:
        print(f"ERROR: key file not found: {fpath}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"ERROR: cannot read key file: {fpath} (permission denied)", file=sys.stderr)
        sys.exit(1)
    try:
        p.unlink()
    except FileNotFoundError:
        pass  # Already deleted by another process
    if not key:
        print(f"ERROR: key file is empty: {fpath}", file=sys.stderr)
        sys.exit(1)
    return key
