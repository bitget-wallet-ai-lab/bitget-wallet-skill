#!/usr/bin/env python3
"""
Derive multi-chain addresses from a mnemonic file. Outputs only addresses (no mnemonic, no private keys).
Use this so the agent can store evm_address, solana_address, tron_address in conversation context.
For signing, use order_make_sign_send.py with --mnemonic-file; keys are derived in memory and never output.
"""

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_mnemonic_from_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    words = text.split()
    if len(words) not in [12, 15, 18, 21, 24]:
        print(f"Error: mnemonic must be 12/15/18/21/24 words, got {len(words)}", file=sys.stderr)
        sys.exit(1)
    return " ".join(words)


def cmd_derive_addresses(mnemonic_file: str):
    """
    Read mnemonic from file, derive EVM/Solana/Tron addresses, output only addresses as JSON.
    Mnemonic and private keys are never printed. Agent should store the output in context.
    """
    path = Path(mnemonic_file).expanduser().resolve()
    if not path.exists():
        print(f"Error: mnemonic file not found: {path}", file=sys.stderr)
        sys.exit(1)
    mnemonic = _load_mnemonic_from_file(path)
    from wallet_from_mnemonic import derive_wallets_from_mnemonic

    wallets = derive_wallets_from_mnemonic(mnemonic)
    out = {
        "evm_address": wallets["evm"]["address"],
        "solana_address": wallets.get("sol", {}).get("address", ""),
        "tron_address": wallets["tron"]["address"],
    }
    print(json.dumps(out, indent=2))


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Derive addresses from mnemonic file (outputs only addresses; no mnemonic or keys)."
    )
    parser.add_argument("--mnemonic-file", required=True, metavar="PATH", help="Path to file containing mnemonic (one line, space-separated)")
    args = parser.parse_args()
    cmd_derive_addresses(args.mnemonic_file)


if __name__ == "__main__":
    main()
