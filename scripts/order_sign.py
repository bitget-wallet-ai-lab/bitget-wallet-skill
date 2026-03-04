#!/usr/bin/env python3
"""
Order Mode signing helper for Bitget Wallet Skill.

Signs order-create response signatures using the API-provided hashes.
Does NOT re-compute EIP-712 hashes — uses the hash field from API directly.

Usage:
    python3 scripts/order_sign.py --order-json '<json>' --private-key <hex>

    # Or pipe order-create output:
    python3 scripts/bitget_api.py order-create ... | python3 scripts/order_sign.py --private-key <hex>

Output: JSON array of signed hex strings, ready for order-submit --signed-txs
"""

import argparse
import json
import sys

from eth_account import Account


def sign_order_signatures(order_data: dict, private_key: str) -> list[str]:
    """
    Sign all signatures in an order-create response.

    Args:
        order_data: The 'data' field from order-create response
        private_key: Hex private key (with or without 0x prefix)

    Returns:
        List of signed hex strings (0x-prefixed)
    """
    acct = Account.from_key(private_key)
    signed_list = []

    sigs = order_data.get("signatures", [])
    if not sigs:
        raise ValueError("No signatures in order data. Is this a 'txs' mode order?")

    for item in sigs:
        api_hash = item.get("hash")
        if not api_hash:
            raise ValueError(f"Missing 'hash' field in signature item: {item}")

        hash_bytes = bytes.fromhex(api_hash[2:])
        signed = acct.unsafe_sign_hash(hash_bytes)
        sig_hex = "0x" + signed.signature.hex()
        signed_list.append(sig_hex)

    return signed_list


def sign_order_txs(order_data: dict, private_key: str, chain_id: int = None) -> list[str]:
    """
    Sign all transactions in an order-create response (non-gasless mode).

    Args:
        order_data: The 'data' field from order-create response
        private_key: Hex private key
        chain_id: Override chain ID (optional)

    Returns:
        List of signed raw transaction hex strings (0x-prefixed)
    """
    from eth_account import Account
    acct = Account.from_key(private_key)
    signed_list = []

    txs = order_data.get("txs", [])
    if not txs:
        raise ValueError("No txs in order data. Is this a 'signatures' mode order?")

    for tx_item in txs:
        tx_data = tx_item["data"]
        cid = chain_id or int(tx_item.get("chainId", 1))

        tx_dict = {
            "to": tx_data["to"],
            "data": tx_data["calldata"],
            "gas": int(tx_data["gasLimit"]),
            "nonce": int(tx_data["nonce"]),
            "chainId": cid,
        }

        # EIP-1559 vs legacy
        if tx_data.get("supportEIP1559") or tx_data.get("maxFeePerGas"):
            tx_dict["maxFeePerGas"] = int(tx_data["maxFeePerGas"])
            tx_dict["maxPriorityFeePerGas"] = int(tx_data["maxPriorityFeePerGas"])
            tx_dict["type"] = 2
        else:
            tx_dict["gasPrice"] = int(tx_data["gasPrice"])

        # Value
        value = tx_data.get("value", "0")
        if isinstance(value, str) and "." in value:
            tx_dict["value"] = int(float(value) * 1e18)
        else:
            tx_dict["value"] = int(value)

        signed_tx = acct.sign_transaction(tx_dict)
        signed_list.append("0x" + signed_tx.raw_transaction.hex())

    return signed_list


def main():
    parser = argparse.ArgumentParser(description="Sign order-create response")
    parser.add_argument("--order-json", help="Order-create response JSON string")
    parser.add_argument("--private-key", required=True, help="Hex private key")
    args = parser.parse_args()

    if args.order_json:
        response = json.loads(args.order_json)
    else:
        response = json.loads(sys.stdin.read())

    data = response.get("data", response)

    if "signatures" in data and data["signatures"]:
        signed = sign_order_signatures(data, args.private_key)
    elif "txs" in data and data["txs"]:
        signed = sign_order_txs(data, args.private_key)
    else:
        print("ERROR: No signatures or txs in response", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(signed))


if __name__ == "__main__":
    main()
