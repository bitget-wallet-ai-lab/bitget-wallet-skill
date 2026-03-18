#!/usr/bin/env python3
"""
Order Mode signing helper for Bitget Wallet Skill.

Signs order-create response for both EVM and Solana chains.
- EVM signatures mode: signs API-provided EIP-712 hashes directly
- EVM txs mode: builds and signs raw transactions
- EVM RWA swap: when txs[].function is "signTypeData", signs EIP-712 typed data (1inch Order);
  signTypeData.domain.chainId may be hex string (e.g. "0x38") and is normalized to int for signing
- Tron (TRX) txs mode: SHA256(transaction.raw_data_hex) then ECDSA secp256k1; output sig is JSON
  { signature: [hex], txID, raw_data }. Recovery id 0/1; high-S form to match Tron SDK/API.
- Solana txs mode: partial-sign VersionedTransaction (or Legacy fallback)

Usage:
    # EVM
    python3 scripts/order_sign.py --order-json '<json>' --private-key <hex>

    # Tron (TRX)
    python3 scripts/order_sign.py --order-json '<json>' --private-key-tron <hex>

    # Solana
    python3 scripts/order_sign.py --order-json '<json>' --private-key-sol <base58|hex>

    # Pipe from order-create
    python3 scripts/bitget_agent_api.py order-create ... | python3 scripts/order_sign.py --private-key <hex>

Output: JSON array of signed strings, ready for order-submit --signed-txs

Dependencies: Python 3.9+ stdlib + eth_account (EVM only). Solana signing is
fully self-contained — no external packages required (pure-Python Ed25519 + base58).
"""

import argparse
import hashlib
import json
import sys

# Solana chainId — must not be signed as EVM; use sign_order_txs_solana for chainId 501
_SOLANA_CHAIN_ID = 501


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
    Uses pre-serialized transactions (serializedTx); no gas/fee conversion — Solana uses lamports and compute units.

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
        item_cid = tx_item.get("chainId") or (tx_item.get("deriveTransaction") or {}).get("chainId")
        if item_cid is not None and int(item_cid) != _SOLANA_CHAIN_ID:
            raise ValueError(
                f"Tx item has non-Solana chainId {item_cid}. Use --private-key for EVM orders."
            )
        # Also accept chain="sol" when chainId is absent (gasPayMaster mode)
        chain_field = (tx_item.get("chain") or "").lower()
        if item_cid is None and chain_field not in ("sol", "solana", ""):
            raise ValueError(
                f"Tx item has non-Solana chain '{chain_field}'. Use --private-key for EVM orders."
            )
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
            # Try source.serializedTransaction (in tx_data or deriveTransaction)
            source = tx_data.get("source") or (tx_item.get("deriveTransaction") or {}).get("source")
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


def _normalize_tx_item_for_signing(tx_item: dict) -> tuple[dict, int]:
    """
    Normalize order-create / makeOrder tx item to { to, calldata, gasLimit, nonce, gasPrice, value } and chainId.
    Supports legacy format (tx_item["data"] is dict) and new format (tx_item has deriveTransaction, data is hex string).
    Rejects Solana (chainId 501) — use sign_order_txs_solana for that.
    """
    derive = tx_item.get("deriveTransaction")
    data_raw = tx_item.get("data")
    cid = int(tx_item.get("chainId") or (derive.get("chainId") if derive else 1))
    if cid == _SOLANA_CHAIN_ID:
        raise ValueError(
            "Tx item is Solana (chainId 501). Use --private-key-sol; order should be detected as Solana."
        )

    if derive and isinstance(data_raw, str):
        # New swap flow makeOrder format: data is hex string, deriveTransaction has chain params
        d = derive
        to_addr = tx_item.get("to") or d.get("to") or ""
        # Normalize to checksum address (eth_account rejects non-checksum)
        if to_addr and to_addr.startswith("0x"):
            from eth_utils import to_checksum_address
            to_addr = to_checksum_address(to_addr)
        tx_data = {
            "to": to_addr,
            "calldata": data_raw,
            "gasLimit": str(d.get("gasLimit", tx_item.get("gasLimit", 0))),
            "nonce": int(d.get("nonce", tx_item.get("nonce", 0))),
            "gasPrice": d.get("gasPrice") or tx_item.get("gasPrice", "0"),
            "value": d.get("value") or tx_item.get("value", "0"),
            "supportEIP1559": False,
            "maxFeePerGas": None,
            "maxPriorityFeePerGas": None,
        }
        return tx_data, cid
    # Legacy order-create format: tx_item["data"] is dict
    tx_data = tx_item["data"]
    cid = int(tx_item.get("chainId", 1))
    return tx_data, cid


def _normalize_eip712_domain(domain: dict) -> dict:
    """Normalize EIP-712 domain for eth_account: chainId must be int."""
    out = dict(domain)
    cid = domain.get("chainId")
    if cid is not None:
        if isinstance(cid, str):
            out["chainId"] = int(cid, 16) if cid.startswith("0x") else int(cid)
        else:
            out["chainId"] = int(cid)
    return out


def _sign_eip712_sign_type_data(sign_type_data: dict, acct) -> str:
    """
    Sign EIP-712 typed data (RWA swap / 1inch Order style).
    sign_type_data: { domain, message, primaryType, types } from makeOrder txs[].signTypeData.
    Returns 0x-prefixed signature hex (r + s + v, 65 bytes).
    """
    domain = _normalize_eip712_domain(sign_type_data.get("domain", {}))
    full_message = {
        "types": sign_type_data.get("types", {}),
        "primaryType": sign_type_data.get("primaryType", "Order"),
        "domain": domain,
        "message": sign_type_data.get("message", {}),
    }
    signed = acct.sign_typed_data(full_message=full_message)
    sig_hex = signed.signature.hex()
    return sig_hex if sig_hex.startswith("0x") else "0x" + sig_hex


def _sign_msgs_eth_sign(msgs: list, acct) -> list[str]:
    """
    Sign gasPayMaster msgs using eth_sign.
    Each msg has: hash (bytes32 hex), signType ("eth_sign"), call[], deadline, nonce, etc.
    eth_sign = sign(keccak256("\\x19Ethereum Signed Message:\\n32" + hash_bytes))
    Returns list of signature hex strings.
    """
    sig_list = []
    for msg in msgs:
        sign_type = msg.get("signType", "")
        msg_hash = msg.get("hash", "")
        if sign_type != "eth_sign" or not msg_hash:
            raise ValueError(f"Unsupported msg signType: {sign_type!r} or missing hash")
        hash_bytes = bytes.fromhex(msg_hash.replace("0x", ""))
        # eth_sign: sign raw 32-byte hash directly (unsafe_sign_hash, no Ethereum prefix)
        signed = acct.unsafe_sign_hash(hash_bytes)
        sig_hex = signed.signature.hex()
        sig_list.append(sig_hex if sig_hex.startswith("0x") else "0x" + sig_hex)
    return sig_list


def sign_order_txs_evm(order_data: dict, private_key: str, chain_id: int = None) -> list[str]:
    """
    Sign all EVM transactions in an order-create or makeOrder txs response.
    Supports:
      1. Legacy order-create format (tx_item["data"] is dict)
      2. New makeOrder format (deriveTransaction + data hex) — raw tx signing
      3. gasPayMaster mode (msgs[] with signType "eth_sign") — hash signing for gasless
    Skips or rejects Solana tx items (chainId 501); use sign_order_txs_solana for those.
    """
    from eth_account import Account
    acct = Account.from_key(private_key)
    signed_list = []

    txs = order_data.get("txs", [])
    if not txs:
        raise ValueError("No txs in order data. Is this a 'signatures' mode order?")

    for tx_item in txs:
        item_cid = int(tx_item.get("chainId") or (tx_item.get("deriveTransaction") or {}).get("chainId") or 0)
        if item_cid == _SOLANA_CHAIN_ID:
            raise ValueError(
                "One or more tx items are Solana (chainId 501). Use --private-key-sol for Solana orders."
            )

        # RWA swap: EIP-712 signTypeData (1inch Order style)
        if tx_item.get("function") == "signTypeData":
            sign_type_data = tx_item.get("signTypeData")
            if not sign_type_data:
                raise ValueError("Tx has function signTypeData but missing signTypeData")
            sig_hex = _sign_eip712_sign_type_data(sign_type_data, acct)
            signed_list.append(sig_hex)
            continue

        # Check for gasPayMaster mode: msgs[] with eth_sign
        derive = tx_item.get("deriveTransaction") or {}
        msgs = tx_item.get("msgs") or derive.get("msgs") or []
        if msgs and any(m.get("signType") == "eth_sign" for m in msgs):
            # gasPayMaster / gasless mode: sign msg hashes instead of raw tx
            msg_sigs = _sign_msgs_eth_sign(msgs, acct)
            # Put signature into each msg's "sig" field (mutates tx_item in-place)
            for j, sig in enumerate(msg_sigs):
                msgs[j]["sig"] = sig
            # Also update deriveTransaction msgs if they exist
            derive_msgs = derive.get("msgs") or []
            for j, sig in enumerate(msg_sigs):
                if j < len(derive_msgs):
                    derive_msgs[j]["sig"] = sig
            # Return the signed json struct
            signed_list.append(json.dumps(msgs))
            continue

        tx_data, cid = _normalize_tx_item_for_signing(tx_item)
        cid = chain_id or cid

        tx_dict = {
            "to": tx_data["to"],
            "data": tx_data.get("calldata") or tx_data.get("data"),
            "gas": int(tx_data.get("gasLimit", 0)),
            "nonce": int(tx_data.get("nonce", 0)),
            "chainId": cid,
        }

        if tx_data.get("supportEIP1559") or tx_data.get("maxFeePerGas"):
            tx_dict["maxFeePerGas"] = int(tx_data["maxFeePerGas"])
            tx_dict["maxPriorityFeePerGas"] = int(tx_data["maxPriorityFeePerGas"])
            tx_dict["type"] = 2
        else:
            gp = tx_data.get("gasPrice", "0")
            if isinstance(gp, str) and "." in gp:
                # API gives gasPrice in native token (BNB/ETH, 18 decimals); convert to wei
                gpf = float(gp)
                if 0 < gpf < 1:
                    tx_dict["gasPrice"] = int(gpf * 1e18)
                else:
                    tx_dict["gasPrice"] = int(gpf * 1e9)
            else:
                tx_dict["gasPrice"] = int(gp)

        value = tx_data.get("value", "0")
        if isinstance(value, str) and "." in value:
            tx_dict["value"] = int(float(value) * 1e18)
        else:
            tx_dict["value"] = int(value)

        signed_tx = acct.sign_transaction(tx_dict)
        signed_list.append("0x" + signed_tx.raw_transaction.hex())

    return signed_list


# ---------------------------------------------------------------------------
# Tron (TRX) signing
# ---------------------------------------------------------------------------

# SECP256k1 curve order (same as Ethereum/Bitcoin); for Tron low-S canonical form
_TRON_SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def _tron_signature_to_high_s(sig_bytes: bytes) -> bytes:
    """Convert signature to high-S form if currently low-S (some Tron SDKs/APIs expect high-S)."""
    if len(sig_bytes) != 65:
        return sig_bytes
    r = sig_bytes[:32]
    s = int.from_bytes(sig_bytes[32:64], "big")
    v = sig_bytes[64]
    half_n = _TRON_SECP256K1_ORDER // 2
    if s <= half_n:
        s = _TRON_SECP256K1_ORDER - s
        if v in (27, 28):
            v = 28 if v == 27 else 27
    s_bytes = s.to_bytes(32, "big")
    return r + s_bytes + bytes([v])


def _normalize_tron_private_key(private_key: str) -> str:
    """Ensure Tron private key has 0x prefix for eth_account (same secp256k1 curve)."""
    pk = (private_key or "").strip()
    if pk.startswith("0x"):
        return pk
    return "0x" + pk


def sign_order_txs_tron(order_data: dict, private_key_tron: str) -> list[str]:
    """
    Sign all Tron transactions in an order txs response.
    Each tx has transaction.raw_data_hex (serialized raw_data), transaction.raw_data, transaction.txID.
    Signing: SHA256(raw_data_hex bytes) then ECDSA secp256k1 (same as EVM); output sig is a JSON string
    with { signature: [hex], txID, raw_data } for the send API.
    """
    from eth_account import Account
    pk = _normalize_tron_private_key(private_key_tron)
    acct = Account.from_key(pk)
    signed_list = []

    txs = order_data.get("txs", [])
    if not txs:
        raise ValueError("No txs in order data")

    for tx_item in txs:
        chain = (tx_item.get("chain") or "").lower()
        if chain not in ("trx", "tron"):
            raise ValueError(
                f"Tx chain is {chain!r}, not Tron. Use --private-key-tron only for chain trx/tron."
            )
        transaction = tx_item.get("transaction")
        if not transaction:
            raise ValueError("Tron tx missing 'transaction' (raw_data_hex, raw_data, txID)")
        raw_data_hex = transaction.get("raw_data_hex")
        raw_data = transaction.get("raw_data")
        tx_id = transaction.get("txID")
        if not raw_data_hex:
            raise ValueError("Tron transaction missing raw_data_hex")
        if raw_data is None:
            raise ValueError("Tron transaction missing raw_data")
        if not tx_id:
            raise ValueError("Tron transaction missing txID")

        raw_bytes = bytes.fromhex(raw_data_hex.replace("0x", "").strip())
        msg_hash = hashlib.sha256(raw_bytes).digest()
        signed = acct.unsafe_sign_hash(msg_hash)
        # Tron uses standard low-S form; recovery id 0/1 (eth_account gives 27/28)
        sig_bytes = bytearray(signed.signature)
        if len(sig_bytes) == 65 and sig_bytes[64] in (27, 28):
            sig_bytes[64] -= 27
        sig_hex = sig_bytes.hex()
        if sig_hex.startswith("0x"):
            sig_hex = sig_hex[2:]

        sig_obj = {
            "signature": [sig_hex],
            "txID": tx_id,
            "raw_data": raw_data,
        }
        signed_list.append(json.dumps(sig_obj))

    return signed_list


# ---------------------------------------------------------------------------
# Chain detection
# ---------------------------------------------------------------------------

def _is_tron_order(order_data: dict) -> bool:
    """Detect if order data is for Tron chain (chain trx or tron)."""
    txs = order_data.get("txs", [])
    for tx_item in txs:
        chain = (tx_item.get("chain") or "").lower()
        if chain in ("trx", "tron"):
            return True
        if tx_item.get("transaction") and isinstance(tx_item["transaction"].get("raw_data_hex"), str):
            return True
    return False


def _is_solana_order(order_data: dict) -> bool:
    """Detect if order data is for Solana chain."""
    txs = order_data.get("txs", [])
    for tx_item in txs:
        chain_id = tx_item.get("chainId") or (tx_item.get("deriveTransaction") or {}).get("chainId")
        if chain_id is not None and int(chain_id) == _SOLANA_CHAIN_ID:
            return True
        # Check chainName or chain field
        chain_name = (tx_item.get("chainName") or tx_item.get("chain") or "").lower()
        if chain_name in ("sol", "solana"):
            return True
        # Check for serializedTx (Solana-specific field) in data or source
        data = tx_item.get("data", {})
        if isinstance(data, dict) and data.get("serializedTx"):
            return True
        source = tx_item.get("source") or (tx_item.get("deriveTransaction") or {}).get("source")
        if isinstance(source, dict) and source.get("serializedTransaction"):
            return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Sign order-create response")
    parser.add_argument("--order-json", help="Order-create response JSON string")
    parser.add_argument("--private-key-file", help="Path to file containing EVM private key (hex). File is read and deleted.")
    parser.add_argument("--private-key-file-sol", help="Path to file containing Solana private key. File is read and deleted.")
    parser.add_argument("--private-key-file-tron", help="Path to file containing Tron private key. File is read and deleted.")
    # Legacy support (deprecated, will be removed)
    parser.add_argument("--private-key", help=argparse.SUPPRESS)
    parser.add_argument("--private-key-sol", help=argparse.SUPPRESS)
    parser.add_argument("--private-key-tron", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Read keys from files (preferred) — delete file immediately after reading
    from key_utils import read_key_file

    if args.private_key_file:
        args.private_key = read_key_file(args.private_key_file)
    if args.private_key_file_sol:
        args.private_key_sol = read_key_file(args.private_key_file_sol)
    if args.private_key_file_tron:
        args.private_key_tron = read_key_file(args.private_key_file_tron)

    if args.order_json:
        response = json.loads(args.order_json)
    else:
        response = json.loads(sys.stdin.read())

    # Support raw txs array as input (e.g. api/tron_sign_1.json)
    if isinstance(response, list):
        data = {"txs": response}
    else:
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
        elif _is_tron_order(data):
            pk_tron = args.private_key_tron
            if not pk_tron:
                print("ERROR: --private-key-tron required for Tron txs mode", file=sys.stderr)
                sys.exit(1)
            signed = sign_order_txs_tron(data, pk_tron)
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
