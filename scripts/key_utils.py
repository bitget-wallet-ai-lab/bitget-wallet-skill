"""Shared utilities for secure private key file handling."""

from pathlib import Path
import sys


def read_key_file(fpath: str) -> str:
    """Read private key from file and delete the file immediately.

    Raises SystemExit if file not found. Silently ignores if file
    was already deleted (e.g. by another process).
    """
    p = Path(fpath)
    if not p.exists():
        print(f"ERROR: key file not found: {fpath}", file=sys.stderr)
        sys.exit(1)
    key = p.read_text().strip()
    try:
        p.unlink()
    except FileNotFoundError:
        pass  # Already deleted by another process
    return key
