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

Dependencies: Python 3.11+ stdlib + eth_account (EVM only). Solana signing is
fully self-contained — no external packages required (pure-Python Ed25519 + base58).
"""

import argparse
import hashlib
import json
import sys


# ===========================================================================
# Pure-Python Base58 (Bitcoin alphabet)
# ===========================================================================

_B58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_MAP = {c: i for i, c in enumerate(_B58_ALPHABET)}


def b58encode(data: bytes) -> str:
    """Encode bytes to base58 string (Bitcoin alphabet)."""
    n = int.from_bytes(data, "big")
    result = []
    while n > 0:
        n, r = divmod(n, 58)
        result.append(_B58_ALPHABET[r:r + 1])
    # Leading zeros
    for byte in data:
        if byte == 0:
            result.append(b"1")
        else:
            break
    return b"".join(reversed(result)).decode()


def b58decode(s: str) -> bytes:
    """Decode base58 string to bytes."""
    n = 0
    for c in s.encode():
        n = n * 58 + _B58_MAP[c]
    # Determine byte length
    byte_length = (n.bit_length() + 7) // 8
    result = n.to_bytes(byte_length, "big") if byte_length > 0 else b""
    # Leading '1's → leading zero bytes
    leading_zeros = 0
    for c in s:
        if c == "1":
            leading_zeros += 1
        else:
            break
    return b"\x00" * leading_zeros + result


# ===========================================================================
# Pure-Python Ed25519 (RFC 8032)
# ===========================================================================

_ED25519_D = -4513249062541557337682894930092624173785641285191125241628941591882900924598840740
_ED25519_Q = 2**255 - 19
_ED25519_L = 2**252 + 27742317777372353535851937790883648493
_ED25519_I = pow(2, (_ED25519_Q - 1) // 4, _ED25519_Q)  # sqrt(-1)


def _ed_inv(x):
    return pow(x, _ED25519_Q - 2, _ED25519_Q)


def _ed_recover_x(y, sign):
    """Recover x coordinate from y and sign bit."""
    y2 = y * y
    x2 = (y2 - 1) * _ed_inv(_ED25519_D * y2 + 1)
    if x2 == 0:
        if sign:
            raise ValueError("Invalid point")
        return 0
    x = pow(x2, (_ED25519_Q + 3) // 8, _ED25519_Q)
    if (x * x - x2) % _ED25519_Q != 0:
        x = x * _ED25519_I % _ED25519_Q
    if (x * x - x2) % _ED25519_Q != 0:
        raise ValueError("Invalid point")
    if x & 1 != sign:
        x = _ED25519_Q - x
    return x


def _ed_point_from_bytes(b: bytes):
    """Decode a 32-byte compressed Edwards point."""
    y = int.from_bytes(b, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _ed_recover_x(y, sign)
    return (x, y, 1, x * y % _ED25519_Q)


def _ed_point_to_bytes(P) -> bytes:
    """Encode an Edwards point to 32 bytes."""
    zi = _ed_inv(P[2])
    x = P[0] * zi % _ED25519_Q
    y = P[1] * zi % _ED25519_Q
    bs = y.to_bytes(32, "little")
    ba = bytearray(bs)
    if x & 1:
        ba[31] |= 0x80
    return bytes(ba)


def _ed_point_add(P, Q):
    """Extended coordinates point addition."""
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _ED25519_Q
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _ED25519_Q
    C = 2 * P[3] * Q[3] * _ED25519_D % _ED25519_Q
    D = 2 * P[2] * Q[2] % _ED25519_Q
    E = B - A
    F = D - C
    G = D + C
    H = B + A
    return (E * F % _ED25519_Q, G * H % _ED25519_Q,
            F * G % _ED25519_Q, E * H % _ED25519_Q)


def _ed_scalar_mult(s, P):
    """Scalar multiplication via double-and-add."""
    Q = (0, 1, 1, 0)  # identity
    while s > 0:
        if s & 1:
            Q = _ed_point_add(Q, P)
        P = _ed_point_add(P, P)
        s >>= 1
    return Q


# Base point
_ED25519_GY = 4 * _ed_inv(5) % _ED25519_Q
_ED25519_GX = _ed_recover_x(_ED25519_GY, 0)
_ED25519_G = (_ED25519_GX, _ED25519_GY, 1, _ED25519_GX * _ED25519_GY % _ED25519_Q)


def _ed_clamp(seed_hash_left: bytes) -> int:
    """Clamp the first 32 bytes of the seed hash for scalar multiplication."""
    a = bytearray(seed_hash_left)
    a[0] &= 248
    a[31] &= 127
    a[31] |= 64
    return int.from_bytes(a, "little")


def ed25519_pubkey_from_seed(seed: bytes) -> bytes:
    """Derive Ed25519 public key from 32-byte seed."""
    h = hashlib.sha512(seed).digest()
    a = _ed_clamp(h[:32])
    A = _ed_scalar_mult(a, _ED25519_G)
    return _ed_point_to_bytes(A)


def ed25519_sign(message: bytes, seed: bytes) -> bytes:
    """Sign a message with Ed25519 (RFC 8032). seed = 32-byte private seed."""
    h = hashlib.sha512(seed).digest()
    a = _ed_clamp(h[:32])
    prefix = h[32:]

    A = _ed_scalar_mult(a, _ED25519_G)
    A_bytes = _ed_point_to_bytes(A)

    r_hash = hashlib.sha512(prefix + message).digest()
    r = int.from_bytes(r_hash, "little") % _ED25519_L

    R = _ed_scalar_mult(r, _ED25519_G)
    R_bytes = _ed_point_to_bytes(R)

    k_hash = hashlib.sha512(R_bytes + A_bytes + message).digest()
    k = int.from_bytes(k_hash, "little") % _ED25519_L

    S = (r + k * a) % _ED25519_L

    return R_bytes + S.to_bytes(32, "little")


# ===========================================================================
# Solana helpers
# ===========================================================================

def _load_sol_keypair(private_key_str: str) -> tuple[bytes, bytes]:
    """
    Load a Solana keypair from base58, hex-64-byte, or hex-32-byte seed.

    Returns: (seed_32bytes, pubkey_32bytes)
    """
    raw = private_key_str.strip()

    # Try base58 first (most common for Solana)
    try:
        key_bytes = b58decode(raw)
        if len(key_bytes) == 64:
            seed = key_bytes[:32]
            pubkey = key_bytes[32:]
            return (seed, pubkey)
        if len(key_bytes) == 32:
            pubkey = ed25519_pubkey_from_seed(key_bytes)
            return (key_bytes, pubkey)
    except Exception:
        pass

    # Try hex
    try:
        hex_clean = raw.removeprefix("0x")
        key_bytes = bytes.fromhex(hex_clean)
        if len(key_bytes) == 64:
            seed = key_bytes[:32]
            pubkey = key_bytes[32:]
            return (seed, pubkey)
        if len(key_bytes) == 32:
            pubkey = ed25519_pubkey_from_seed(key_bytes)
            return (key_bytes, pubkey)
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


def _parse_message_account_keys(message_bytes: bytes) -> tuple[int, list[str]]:
    """
    Parse a Solana transaction message to extract header and account keys.

    Handles both V0 (0x80 prefix) and Legacy formats.
    Returns: (num_required_signatures, list_of_base58_pubkeys)
    """
    offset = 0

    # V0 messages start with 0x80 (version prefix)
    if message_bytes[0] == 0x80:
        offset = 1

    # Header: 3 bytes
    num_required_signatures = message_bytes[offset]
    offset += 3  # skip num_readonly_signed, num_readonly_unsigned

    # Account keys: shortvec length, then N * 32-byte pubkeys
    num_keys, consumed = _decode_shortvec(message_bytes, offset)
    offset += consumed

    keys = []
    for _ in range(num_keys):
        key = message_bytes[offset:offset + 32]
        keys.append(b58encode(key))
        offset += 32

    return num_required_signatures, keys


def sign_solana_tx(serialized_tx_b58: str, seed: bytes, pubkey: bytes) -> str:
    """
    Partial-sign a Solana serialized transaction (base58).

    Supports VersionedTransaction (V0) and Legacy.
    Returns base58-encoded signed transaction.
    """
    tx_bytes = b58decode(serialized_tx_b58)
    our_pubkey_b58 = b58encode(pubkey)

    # Parse signature slots
    sig_count, sig_count_len = _decode_shortvec(tx_bytes, 0)
    sig_start = sig_count_len
    message_bytes = tx_bytes[sig_start + (sig_count * 64):]

    # Parse message to find account keys
    num_required, account_keys = _parse_message_account_keys(message_bytes)
    signer_keys = account_keys[:num_required]

    if our_pubkey_b58 not in signer_keys:
        raise ValueError(
            f"Wallet {our_pubkey_b58} not in required signers: {signer_keys}"
        )
    our_index = signer_keys.index(our_pubkey_b58)

    # Sign the message bytes (Ed25519)
    signature = ed25519_sign(message_bytes, seed)

    # Write signature into the correct slot
    new_tx = bytearray(tx_bytes)
    offset = sig_start + (our_index * 64)
    new_tx[offset:offset + 64] = signature

    return b58encode(bytes(new_tx))


def sign_order_txs_solana(order_data: dict, private_key_sol: str) -> list[str]:
    """
    Sign all Solana transactions in an order-create txs response.

    Args:
        order_data: The 'data' field from order-create response
        private_key_sol: Solana private key (base58 or hex)

    Returns:
        List of base58-encoded signed transactions
    """
    seed, pubkey = _load_sol_keypair(private_key_sol)
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

        signed_b58 = sign_solana_tx(serialized_tx, seed, pubkey)
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
        if chain_name in ("sol", "solana"):
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
