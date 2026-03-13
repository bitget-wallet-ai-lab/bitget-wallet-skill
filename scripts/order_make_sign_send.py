#!/usr/bin/env python3
"""
One-shot: makeOrder (new swap flow) → sign → send.
Use this to avoid the ~60s expiry of makeOrder unsigned data. Run immediately after user confirms.

Security: --private-key is used only in memory for signing; never printed or logged.
The agent retrieves the private key from secure storage (e.g. 1Password) and passes it here.

Example:
  python3 scripts/order_make_sign_send.py \\
    --private-key "$EVM_KEY" --from-address 0x... --to-address 0x... \\
    --order-id <from confirm> --from-chain bnb --from-contract 0x55d398326f99059fF775485246999027B3197955 \\
    --from-symbol USDT --to-chain bnb --to-contract "" --to-symbol BNB \\
    --from-amount 1 --slippage 1.00 --market bgwevmaggregator --protocol bgwevmaggregator_v000
"""

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="makeOrder + sign + send. Private key used in memory only, never output."
    )
    parser.add_argument("--private-key", required=True, help="EVM private key (hex, from secure storage)")
    parser.add_argument("--from-address", required=True, help="EVM address for from")
    parser.add_argument("--to-address", required=True, help="EVM address for to (usually same as from-address)")
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

    private_key = args.private_key

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

    from order_sign import sign_order_txs_evm

    signed = sign_order_txs_evm(data, private_key)
    for i, sig in enumerate(signed):
        if i < len(txs):
            txs[i]["sig"] = sig

    # Clear private key from memory
    private_key = None
    del args

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
