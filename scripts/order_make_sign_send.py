#!/usr/bin/env python3
"""
One-shot: makeOrder (new swap flow) → sign → send.
Use this to avoid the ~60s expiry of makeOrder unsigned data. Run immediately after user confirms.

Supports EVM, Solana, and Tron chains. Pass --private-key-file for EVM, --private-key-file-sol for Solana,
or --private-key-file-tron for Tron. The script reads the key from the file, uses it in memory only, then discards it.
The script auto-detects chain from makeOrder response (chainId 501 = Solana, Tron chains, otherwise EVM).

Security: Private keys are NEVER passed as command-line arguments (visible in ps/history).
Instead, write the key to a unique temporary file programmatically, pass the file path,
and the script reads + deletes it. Keys are used in memory only, never printed or logged.

Example (EVM — agent writes key file programmatically, never via shell echo):
  # Python: write key to unique temp file
  import tempfile, os
  fd, pk_file = tempfile.mkstemp(prefix='.pk_', dir='/tmp')
  os.write(fd, key.encode()); os.close(fd); os.chmod(pk_file, 0o600)

  python3 scripts/order_make_sign_send.py \\
    --private-key-file "$pk_file" --from-address 0x... --to-address 0x... \\
    --order-id <from confirm> --from-chain bnb --from-contract 0x55d3... \\
    --from-symbol USDT --to-chain bnb --to-contract "" --to-symbol BNB \\
    --from-amount 1 --slippage 1.00 --market bgwevmaggregator --protocol bgwevmaggregator_v000

Example (Solana):
  python3 scripts/order_make_sign_send.py \\
    --private-key-file-sol "$pk_file" --from-address <sol_addr> --to-address <sol_addr> \\
    --order-id <from confirm> --from-chain sol --from-contract <mint> \\
    --from-symbol USDC --to-chain sol --to-contract <mint> --to-symbol USDT \\
    --from-amount 5 --slippage 0.01 --market ... --protocol ...
"""

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_SOLANA_CHAIN_ID = 501


def _is_solana_order(order_data: dict) -> bool:
    """Detect if order data contains Solana transactions."""
    for tx_item in order_data.get("txs", []):
        cid = tx_item.get("chainId") or (tx_item.get("deriveTransaction") or {}).get("chainId")
        if cid is not None and int(cid) == _SOLANA_CHAIN_ID:
            return True
        chain_name = tx_item.get("chainName", "").lower()
        if chain_name in ("sol", "solana"):
            return True
    return False


def _is_tron_order(order_data: dict) -> bool:
    """Detect if order data contains Tron transactions."""
    for tx_item in order_data.get("txs", []):
        chain = (tx_item.get("chain") or "").lower()
        if chain in ("trx", "tron"):
            return True
        if tx_item.get("transaction") and isinstance(tx_item["transaction"].get("raw_data_hex"), str):
            return True
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="makeOrder + sign + send. Supports EVM and Solana. Keys used in memory only, never output."
    )
    parser.add_argument("--private-key-file", default=None, help="Path to file containing EVM private key (hex). File is read and deleted.")
    parser.add_argument("--private-key-file-sol", default=None, help="Path to file containing Solana private key (base58 or hex). File is read and deleted.")
    parser.add_argument("--private-key-file-tron", default=None, help="Path to file containing Tron private key (hex). File is read and deleted.")
    # Legacy support (deprecated, will be removed)
    parser.add_argument("--private-key", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--private-key-sol", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--private-key-tron", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--from-address", required=True, help="Sender address")
    parser.add_argument("--to-address", required=True, help="Receiver address (usually same as from-address)")
    parser.add_argument("--order-id", required=True, help="From confirm response data.orderId")
    parser.add_argument("--from-chain", required=True)
    parser.add_argument("--from-contract", required=True)
    parser.add_argument("--from-symbol", required=True)
    parser.add_argument("--to-chain", required=True)
    parser.add_argument("--to-contract", default="")
    parser.add_argument("--to-symbol", required=True)
    parser.add_argument("--from-amount", required=True)
    parser.add_argument("--slippage", required=True)
    parser.add_argument("--market", required=True)
    parser.add_argument("--protocol", required=True)
    args = parser.parse_args()

    # Read keys from files (preferred) or legacy args
    from key_utils import read_key_file

    if args.private_key_file:
        args.private_key = read_key_file(args.private_key_file)
    if args.private_key_file_sol:
        args.private_key_sol = read_key_file(args.private_key_file_sol)
    if args.private_key_file_tron:
        args.private_key_tron = read_key_file(args.private_key_file_tron)

    if not args.private_key and not args.private_key_sol and not args.private_key_tron:
        print("Error: must provide --private-key-file (EVM), --private-key-file-sol (Solana), or --private-key-file-tron (Tron)", file=sys.stderr)
        sys.exit(1)

    from bitget_agent_api import make_order, send

    resp = make_order(
        order_id=args.order_id,
        from_chain=args.from_chain,
        from_contract=args.from_contract,
        from_symbol=args.from_symbol,
        from_address=args.from_address,
        to_chain=args.to_chain,
        to_contract=args.to_contract or "",
        to_symbol=args.to_symbol,
        to_address=args.to_address,
        from_amount=args.from_amount,
        slippage=args.slippage,
        market=args.market,
        protocol=args.protocol,
    )
    if resp.get("status") != 0 or resp.get("error_code") != 0:
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    data = resp.get("data", {})
    order_id = data.get("orderId")
    txs = data.get("txs", [])
    if not order_id or not txs:
        print("Error: no orderId or txs in makeOrder response", file=sys.stderr)
        sys.exit(1)

    # Auto-detect chain and sign
    if _is_solana_order(data):
        if not args.private_key_sol:
            print("Error: Solana order detected but --private-key-sol not provided", file=sys.stderr)
            sys.exit(1)
        from order_sign import sign_order_txs_solana
        signed = sign_order_txs_solana(data, args.private_key_sol)
    elif _is_tron_order(data):
        if not args.private_key_tron:
            print("Error: Tron order detected but --private-key-tron not provided", file=sys.stderr)
            sys.exit(1)
        from order_sign import sign_order_txs_tron
        signed = sign_order_txs_tron(data, args.private_key_tron)
    else:
        if not args.private_key:
            print("Error: EVM order detected but --private-key not provided", file=sys.stderr)
            sys.exit(1)
        from order_sign import sign_order_txs_evm
        signed = sign_order_txs_evm(data, args.private_key)

    for i, sig in enumerate(signed):
        if i < len(txs):
            txs[i]["sig"] = sig

    # Clear keys from memory
    args.private_key = None
    args.private_key_sol = None
    args.private_key_tron = None

    send_resp = send(order_id=order_id, txs=txs)
    print(json.dumps(send_resp, indent=2))
    if send_resp.get("status") != 0 or send_resp.get("error_code") != 0:
        sys.exit(1)
    print(
        f"\nOrderId: {order_id}\nCheck: python3 scripts/bitget_agent_api.py get-order-details --order-id {order_id}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
