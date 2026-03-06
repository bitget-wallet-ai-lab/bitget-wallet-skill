#!/usr/bin/env python3
"""
Order Mode signing helper for Bitget Wallet Skill.

Signs order-create response for both EVM and Solana chains.
- EVM signatures mode: signs API-provided EIP-712 hashes directly
- EVM txs mode: builds and signs raw transactions
- Solana txs mode: partial-sign VersionedTransaction (or Legacy fallback)

Usage:
    # EVM
    python3 scripts/order_sign.py --order-json '<json>' --private-key <hex>

    # Solana
    python3 scripts/order_sign.py --order-json '<json>' --private-key-sol <base58|hex>

    # Pipe from order-create
    python3 scripts/bitget_api.py order-create ... | python3 scripts/order_sign.py --private-key <hex>

Output: JSON array of signed strings, ready for order-submit --signed-txs
"""

import argparse
import json
import sys


# ---------------------------------------------------------------------------
# Solana helpers
# ---------------------------------------------------------------------------

def _load_sol_keypair(private_key_str: str):
    """
    Load a Solana Keypair from base58, hex-64-byte, or hex-32-byte seed.
    """
    import base58 as b58
    from solders.keypair import Keypair

    raw = private_key_str.strip()

    # Try base58 first (most common for Solana)
    try:
        key_bytes = b58.b58decode(raw)
        if len(key_bytes) == 64:
            return Keypair.from_bytes(key_bytes)
        if len(key_bytes) == 32:
            return Keypair.from_seed(key_bytes)
    except Exception:
        pass

    # Try hex
    try:
        hex_clean = raw.removeprefix("0x")
        key_bytes = bytes.fromhex(hex_clean)
        if len(key_bytes) == 64:
            return Keypair.from_bytes(key_bytes)
        if len(key_bytes) == 32:
            return Keypair.from_seed(key_bytes)
    except Exception:
        pass

    raise ValueError(
        f"Cannot parse Solana private key ({len(raw)} chars). "
        "Expected base58 or hex (32 or 64 bytes)."
    )


def _decode_shortvec(data: bytes, offset: int) -> tuple[int, int]:
    """Decode a Solana shortvec-encoded integer. Returns (value, bytes_consumed)."""
    val = 0
    shift = 0
    consumed = 0
    while True:
        b = data[offset + consumed]
        consumed += 1
        val |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return val, consumed


def sign_solana_tx(serialized_tx_b58: str, keypair) -> str:
    """
    Partial-sign a Solana serialized transaction (base58).

    Supports VersionedTransaction (V0) and Legacy.
    Returns base58-encoded signed transaction.
    """
    import base58 as b58
    from solders.transaction import VersionedTransaction

    tx_bytes = b58.b58decode(serialized_tx_b58)
    our_pubkey = str(keypair.pubkey())

    # Try VersionedTransaction first
    try:
        vtx = VersionedTransaction.from_bytes(tx_bytes)

        # Get account keys from the message
        msg = vtx.message
        account_keys = [str(k) for k in msg.account_keys]

        # Find our signer index
        num_required = msg.header.num_required_signatures
        signer_keys = account_keys[:num_required]

        if our_pubkey not in signer_keys:
            raise ValueError(
                f"Wallet {our_pubkey} not in required signers: {signer_keys}"
            )
        our_index = signer_keys.index(our_pubkey)

        # Parse raw bytes to locate signature slots and message bytes
        sig_count, sig_count_len = _decode_shortvec(tx_bytes, 0)
        sig_start = sig_count_len
        message_bytes = tx_bytes[sig_start + (sig_count * 64):]

        # Sign the message bytes (Ed25519)
        signature = keypair.sign_message(message_bytes)

        # Write signature into the correct slot
        new_tx = bytearray(tx_bytes)
        offset = sig_start + (our_index * 64)
        new_tx[offset:offset + 64] = bytes(signature)

        return b58.b58encode(bytes(new_tx)).decode()

    except Exception as e:
        # Fallback: try Legacy Transaction
        try:
            from solders.transaction import Transaction as LegacyTransaction
            legacy_tx = LegacyTransaction.from_bytes(tx_bytes)
            legacy_tx.partial_sign([keypair])
            return b58.b58encode(bytes(legacy_tx)).decode()
        except Exception:
            raise ValueError(
                f"Failed to parse as VersionedTransaction or Legacy: {e}"
            ) from e


def sign_order_txs_solana(order_data: dict, private_key_sol: str) -> list[str]:
    """
    Sign all Solana transactions in an order-create txs response.

    Args:
        order_data: The 'data' field from order-create response
        private_key_sol: Solana private key (base58 or hex)

    Returns:
        List of base58-encoded signed transactions
    """
    keypair = _load_sol_keypair(private_key_sol)
    signed_list = []

    txs = order_data.get("txs", [])
    if not txs:
        raise ValueError("No txs in order data")

    for tx_item in txs:
        # Unwrap to find the innermost dict with serializedTx
        tx_data = tx_item

        # Handle nested kind/data wrapper: {kind, data: {serializedTx}}
        if tx_data.get("kind") == "transaction" and isinstance(tx_data.get("data"), dict):
            tx_data = tx_data["data"]
        # Handle nested data wrapper without kind: {chainId, data: {serializedTx}}
        elif isinstance(tx_data.get("data"), dict) and tx_data["data"].get("serializedTx"):
            tx_data = tx_data["data"]

        # Get serializedTx
        serialized_tx = tx_data.get("serializedTx")
        if not serialized_tx:
            # Try source.serializedTransaction
            source = tx_data.get("source", {})
            serialized_tx = source.get("serializedTransaction") if isinstance(source, dict) else None
        if not serialized_tx:
            # Try top-level data field as string
            if isinstance(tx_item.get("data"), str):
                serialized_tx = tx_item["data"]

        if not serialized_tx:
            raise ValueError(
                f"Cannot find serializedTx in tx item. Keys: {list(tx_data.keys())}"
            )

        signed_b58 = sign_solana_tx(serialized_tx, keypair)
        signed_list.append(signed_b58)

    return signed_list


# ---------------------------------------------------------------------------
# EVM helpers
# ---------------------------------------------------------------------------

def sign_order_signatures(order_data: dict, private_key: str) -> list[str]:
    """
    Sign all EIP-712 hash signatures in an order-create response.

    Args:
        order_data: The 'data' field from order-create response
        private_key: Hex private key (with or without 0x prefix)

    Returns:
        List of signed hex strings (0x-prefixed)
    """
    from eth_account import Account
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


def sign_order_txs_evm(order_data: dict, private_key: str, chain_id: int = None) -> list[str]:
    """
    Sign all EVM transactions in an order-create txs response.

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


# ---------------------------------------------------------------------------
# Chain detection
# ---------------------------------------------------------------------------

def _is_solana_order(order_data: dict) -> bool:
    """Detect if order data is for Solana chain."""
    txs = order_data.get("txs", [])
    for tx_item in txs:
        # Check chainId
        chain_id = tx_item.get("chainId", "")
        if str(chain_id) == "501":
            return True
        # Check chainName
        chain_name = tx_item.get("chainName", "").lower()
        if chain_name == "sol":
            return True
        # Check for serializedTx (Solana-specific field)
        data = tx_item.get("data", {})
        if isinstance(data, dict) and data.get("serializedTx"):
            return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Sign order-create response")
    parser.add_argument("--order-json", help="Order-create response JSON string")
    parser.add_argument("--private-key", help="EVM hex private key")
    parser.add_argument("--private-key-sol", help="Solana private key (base58 or hex)")
    args = parser.parse_args()

    if args.order_json:
        response = json.loads(args.order_json)
    else:
        response = json.loads(sys.stdin.read())

    data = response.get("data", response)

    # EVM signatures mode (gasless EIP-7702)
    if "signatures" in data and data["signatures"]:
        if not args.private_key:
            print("ERROR: --private-key required for EVM signatures mode", file=sys.stderr)
            sys.exit(1)
        signed = sign_order_signatures(data, args.private_key)
        print(json.dumps(signed))
        return

    # txs mode — detect chain
    if "txs" in data and data["txs"]:
        if _is_solana_order(data):
            pk_sol = args.private_key_sol
            if not pk_sol:
                print("ERROR: --private-key-sol required for Solana txs mode", file=sys.stderr)
                sys.exit(1)
            signed = sign_order_txs_solana(data, pk_sol)
        else:
            if not args.private_key:
                print("ERROR: --private-key required for EVM txs mode", file=sys.stderr)
                sys.exit(1)
            signed = sign_order_txs_evm(data, args.private_key)
        print(json.dumps(signed))
        return

    print("ERROR: No signatures or txs in response", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
