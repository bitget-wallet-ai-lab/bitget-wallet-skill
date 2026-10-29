#!/usr/bin/env python3
"""
One-shot: getTransferDataV4 -> sign -> send.

Token transfer for EVM (eth/bnb/base/arbitrum/matic/morph) and Solana. Gasless
mode (gas paid from token balance) is chosen automatically by the server based
on the sender's native-coin balance — there is no client-side flag to request
or force it; the script just signs whatever the response comes back with.
Signing is done locally; the server handles broadcasting and on-chain tracking.

Signature dispatch is driven by the getTransferDataV4 response:
  - Standard self-pay EVM : sign the flat tx fields (EIP-1559 or legacy gasPrice)
  - Standard self-pay SOL : sign the raw unsigned transaction
  - EVM gasless (signDataV2) : EIP-712 typed-data signing
  - EVM gasless (signData)   : legacy gasless message signing (sign_7702_msgs)
  - SOL gasless             : sign the raw unsigned transaction

Security: Private keys are NEVER passed as CLI arguments.
Write the key to a unique temp file programmatically, pass the file path.

Example (EVM transfer — gasless/standard chosen automatically by the server):
  python3 scripts/transfer_make_sign_send.py \\
    --private-key-file /tmp/.pk_evm \\
    --chain base --contract 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \\
    --from-address 0xAbC... --to-address 0xDeF... \\
    --amount 50

Example (Solana transfer):
  python3 scripts/transfer_make_sign_send.py \\
    --private-key-file-sol /tmp/.pk_sol \\
    --chain sol --contract Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB \\
    --from-address ApPjj... --to-address 7xKXt... \\
    --amount 10
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _parse_fee_value(val) -> int:
    """
    Parse a gasPrice/maxFeePerGas/maxPriorityFeePerGas value from getTransferDataV4.
    Confirmed via a live call: these come back as a plain decimal string in native-coin
    units (e.g. "0.0000000001" BNB), NOT wei-hex like the rest of the EVM fields
    (nonce/gasLimit/chainId are plain ints or 0x-hex). A bare int(val) would raise
    ValueError on the decimal-point string. Falls back to hex/int for forward
    compatibility in case the shape changes.
    """
    if isinstance(val, str):
        if val.startswith("0x"):
            return int(val, 16)
        if "." in val:
            fval = float(val)
            return int(fval * 1e18) if 0 < fval < 1 else int(fval * 1e9)
        return int(val)
    return int(val)


def _sign_evm_standard(data: dict, private_key: str) -> str:
    """
    Sign a standard self-pay EVM transaction from the flat response data.
    Chooses EIP-1559 vs legacy by the presence of maxFeePerGas/maxPriorityFeePerGas.
    Returns signed raw tx hex (0x-prefixed).
    """
    from eth_account import Account
    acct = Account.from_key(private_key)

    to_addr = data.get("to", "")
    if to_addr and to_addr.startswith("0x"):
        from eth_utils import to_checksum_address
        to_addr = to_checksum_address(to_addr)

    raw_nonce = data.get("nonce")
    if raw_nonce is None:
        raise ValueError("Missing required field 'nonce' in EVM data")
    raw_gas = data.get("gasLimit")
    if not raw_gas:
        raise ValueError("Missing required field 'gasLimit' in EVM data")
    gas_val = int(raw_gas, 16) if isinstance(raw_gas, str) and raw_gas.startswith("0x") else int(raw_gas)
    if gas_val == 0:
        raise ValueError("gasLimit is zero — refusing to sign transaction that will certainly fail")

    raw_chain_id = data.get("chainId", 1)
    chain_id_val = int(raw_chain_id, 16) if isinstance(raw_chain_id, str) and raw_chain_id.startswith("0x") else int(raw_chain_id)

    tx_dict = {
        "to": to_addr,
        "data": data.get("data", "0x"),
        "gas": gas_val,
        "nonce": int(raw_nonce, 16) if isinstance(raw_nonce, str) and raw_nonce.startswith("0x") else int(raw_nonce),
        "chainId": chain_id_val,
    }

    value = data.get("value", "0x0")
    if isinstance(value, str) and value.startswith("0x"):
        tx_dict["value"] = int(value, 16)
    elif isinstance(value, str) and "." in value:
        # Same native-coin-decimal quirk as gasPrice below — "5" BNB, not wei.
        tx_dict["value"] = int(float(value) * 1e18)
    else:
        tx_dict["value"] = int(value)

    if data.get("maxFeePerGas") is not None or data.get("maxPriorityFeePerGas") is not None:
        tx_dict["maxFeePerGas"] = _parse_fee_value(data.get("maxFeePerGas", "0x0"))
        tx_dict["maxPriorityFeePerGas"] = _parse_fee_value(data.get("maxPriorityFeePerGas", "0x0"))
        tx_dict["type"] = 2
    else:
        tx_dict["gasPrice"] = _parse_fee_value(data.get("gasPrice", "0x0"))

    signed_tx = acct.sign_transaction(tx_dict)
    return "0x" + signed_tx.raw_transaction.hex()


def _sign_evm_gasless_legacy(data: dict, private_key: str) -> str:
    """
    Sign EVM gasless legacy message data (signData.sign_type == "sign_7702_msgs").
    Returns JSON.stringify(signedMsgs). Each msg item has a 'hash' field to sign
    with unsafe_sign_hash; the signature is written back to the item's 'sig' field.

    SECURITY NOTE (trust boundary): The hash values come from the Bitget Wallet
    backend (getTransferDataV4 response). The client validates length (32 bytes)
    but does NOT locally re-derive the EIP-7702 authorization digest. This is an
    accepted trust-server architecture — security relies on TLS integrity of the
    backend connection. If local re-derivation is needed in the future:
      auth_hash = keccak256(0x05 || rlp([chain_id, address, nonce]))
    """
    from eth_account import Account
    acct = Account.from_key(private_key)

    msgs = data.get("signData", {}).get("data", [])
    if not msgs:
        raise ValueError("gasless signData has no data to sign")

    for msg in msgs:
        msg_hash = msg.get("hash", "")
        if not msg_hash:
            raise ValueError(f"signData item missing 'hash': {msg}")
        hash_bytes = bytes.fromhex(msg_hash.replace("0x", ""))
        if len(hash_bytes) != 32:
            raise ValueError(f"Invalid hash length {len(hash_bytes)} bytes (expected 32): {msg_hash!r}")
        signed = acct.unsafe_sign_hash(hash_bytes)
        sig_hex = signed.signature.hex()
        msg["sig"] = sig_hex if sig_hex.startswith("0x") else "0x" + sig_hex

    return json.dumps(msgs)


def _infer_primary_type(types: dict) -> str:
    """
    Infer EIP-712 primaryType when the response omits it: the root type is the one
    (excluding EIP712Domain) that is never referenced as a field type by any other
    type. Raises if there isn't exactly one unambiguous root — guessing wrong here
    would sign a fund-moving EIP-712 payload under the wrong primaryType, which is
    worse than aborting the transfer.
    """
    candidates = [k for k in types if k != "EIP712Domain"]
    if not candidates:
        raise ValueError("EIP-712 typed data has no non-domain type to infer primaryType from")
    if len(candidates) == 1:
        return candidates[0]
    referenced = set()
    for type_name, fields in types.items():
        if type_name == "EIP712Domain":
            continue
        for f in fields:
            field_type = f.get("type", "").rstrip("[]")
            if field_type in types:
                referenced.add(field_type)
    roots = [c for c in candidates if c not in referenced]
    if len(roots) != 1:
        raise ValueError(
            f"Cannot unambiguously infer EIP-712 primaryType from types={list(types.keys())} "
            f"(candidate roots: {roots}); refusing to guess for a fund-moving signature"
        )
    return roots[0]


def _sign_evm_typed_data_v2(data: dict, private_key: str) -> str:
    """
    Sign EVM gasless EIP-712 typed data (signDataV2). Each item carries a
    typed-data payload under item["data"] with domain/types/message. Returns
    JSON.stringify of a list of {"domain", "message", "signature"} objects.
    """
    from eth_account import Account
    from order_sign import _normalize_eip712_domain
    acct = Account.from_key(private_key)

    items = data.get("signDataV2", [])
    if not items:
        raise ValueError("gasless signDataV2 has no data to sign")

    results = []
    for item in items:
        typed = item.get("data", {})
        domain = _normalize_eip712_domain(typed.get("domain", {}))
        types = typed.get("types", {})
        message = typed.get("message", {})
        primary_type = typed.get("primaryType") or _infer_primary_type(types)
        signed = acct.sign_typed_data(full_message={
            "types": types,
            "primaryType": primary_type,
            "domain": domain,
            "message": message,
        })
        sig_hex = signed.signature.hex()
        results.append({
            "domain": domain,
            "message": message,
            "signature": sig_hex if sig_hex.startswith("0x") else "0x" + sig_hex,
        })

    return json.dumps(results)


def _sign_solana(data: dict, private_key_sol: str) -> str:
    """
    Sign a Solana raw unsigned transaction from the flat response data.
    Tries rawTx / serializedTx / serializedTransaction in order.
    Returns base58 signed transaction.
    """
    from order_sign import sign_solana_tx, _load_sol_keypair

    raw_tx = data.get("rawTx") or data.get("serializedTx") or data.get("serializedTransaction")
    if not raw_tx:
        raise ValueError(f"Solana source has no recognized raw-tx field, got keys: {list(data.keys())}")

    seed, pubkey = _load_sol_keypair(private_key_sol)
    return sign_solana_tx(raw_tx, seed, pubkey)


def main():
    parser = argparse.ArgumentParser(
        description="Token transfer: getTransferDataV4 + sign + send. "
                    "Keys used in memory only, never output."
    )
    parser.add_argument("--private-key-file", default=None,
                        help="Path to file containing EVM private key (hex). File is read and deleted.")
    parser.add_argument("--private-key-file-sol", default=None,
                        help="Path to file containing Solana private key (base58 or hex). File is read and deleted.")
    parser.add_argument("--chain", required=True,
                        help="Chain code: eth/bnb/base/arbitrum/matic/morph/sol")
    parser.add_argument("--contract", required=True,
                        help="Token contract address; empty string '' for native token")
    parser.add_argument("--from-address", dest="from_address", required=True,
                        help="Sender address")
    parser.add_argument("--to-address", dest="to_address", required=True,
                        help="Receiver address")
    parser.add_argument("--amount", required=True,
                        help="Transfer amount, decimal string e.g. '10.5'")
    args = parser.parse_args()

    # Read keys from files
    from key_utils import read_key_file

    private_key = read_key_file(args.private_key_file) if args.private_key_file else None
    private_key_sol = read_key_file(args.private_key_file_sol) if args.private_key_file_sol else None

    if not private_key and not private_key_sol:
        print("Error: must provide --private-key-file (EVM) or --private-key-file-sol (Solana)",
              file=sys.stderr)
        sys.exit(1)

    # Import API module
    _api = importlib.import_module("bitget-wallet-agent-api")

    # Step 1: getTransferDataV4
    print(">>> Step 1: getTransferDataV4", file=sys.stderr)
    resp = _api.get_transfer_data_v4(
        chain=args.chain,
        contract=args.contract,
        from_=args.from_address,
        to=args.to_address,
        amount=args.amount,
    )

    status = resp.get("status", -1)
    if status != 0:
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    if not resp.get("_security_check_valid") or not resp.get("_security_request_check_valid") or not resp.get("_security_double_check_valid"):
        msg = resp.get("msg", "Transaction blocked: security signature verification failed.")
        print(json.dumps({"status": -1, "error_code": -10000, "msg": msg}, indent=2), file=sys.stderr)
        sys.exit(1)

    data = resp.get("data", {})
    order_id = data.get("orderId")
    if not order_id:
        print("WARNING: no orderId in getTransferDataV4 response (not required by send, continuing)",
              file=sys.stderr)

    print(f"    orderId: {order_id}", file=sys.stderr)
    print(f"    chain: {data.get('chain')}, from: {data.get('from')}, to: {data.get('to')}", file=sys.stderr)
    print(f"    amount: {data.get('amount')}, contract: {data.get('contract')}", file=sys.stderr)

    # The server auto-selects gasless vs. standard based on native-coin balance
    # (gasAccountSelected is never sent — see module docstring). Just report what it picked.
    gas_account = data.get("gasAccount")
    if gas_account and gas_account.get("selected"):
        pay_token = gas_account.get("pay", {}).get("payToken", {})
        print(f"    gasless: {pay_token.get('symbol')} "
              f"(pay: {gas_account.get('payAmount')} {pay_token.get('symbol')})",
              file=sys.stderr)
    else:
        print("    standard transfer (native gas)", file=sys.stderr)

    # Fee info
    fee = data.get("fee", {})
    if fee:
        print(f"    fee: {fee.get('fee')}, "
              f"balance: {fee.get('balance')}, enough: {fee.get('balanceForFeeEnough')}",
              file=sys.stderr)

    # estimateRevert now lives under fee.* (moved there from the old top-level
    # makeTransferOrder response) — abort before signing rather than submitting a
    # transaction already predicted to fail on-chain.
    if fee.get("estimateRevert"):
        reason = fee.get("estimateRevertReason") or "transaction predicted to fail"
        print(f"ERROR: estimateRevert=true — {reason}. Aborting.", file=sys.stderr)
        sys.exit(1)

    if data.get("hasPendingTransactionAndOverwriteNonce"):
        print("WARNING: hasPendingTransactionAndOverwriteNonce=true — the server is reusing a "
              "nonce from a still-pending transaction for this address. This transfer may not "
              "land on-chain until the pending one clears.", file=sys.stderr)

    # Step 2: Sign
    print(">>> Step 2: sign", file=sys.stderr)
    sig = None

    if gas_account and gas_account.get("selected"):
        sid = gas_account.get("pay", {}).get("sid") or gas_account.get("sid")
        if sid == "transfer_no_gas_trx":
            print("ERROR: TRX gasless not supported yet.", file=sys.stderr)
            sys.exit(1)
        elif data.get("signDataV2"):
            if not private_key:
                print("Error: EVM gasless transfer detected but --private-key-file not provided", file=sys.stderr)
                sys.exit(1)
            sig = _sign_evm_typed_data_v2(data, private_key)
            print("    signed EVM gasless (signDataV2/EIP-712)", file=sys.stderr)
        elif data.get("signData", {}).get("sign_type") == "sign_7702_msgs":
            if not private_key:
                print("Error: EVM gasless transfer detected but --private-key-file not provided", file=sys.stderr)
                sys.exit(1)
            sig = _sign_evm_gasless_legacy(data, private_key)
            print("    signed EVM gasless (signData legacy)", file=sys.stderr)
        elif data.get("chainType") == "sol" or (private_key_sol and not private_key):
            if not private_key_sol:
                print("Error: Solana gasless transfer detected but --private-key-file-sol not provided", file=sys.stderr)
                sys.exit(1)
            sig = _sign_solana(data, private_key_sol)
            print("    signed Solana gasless tx", file=sys.stderr)
        else:
            print(f"Error: unrecognized gasless signature shape for sid={sid!r}", file=sys.stderr)
            sys.exit(1)
    else:
        if data.get("chainType") == "sol" or (private_key_sol and not private_key):
            if not private_key_sol:
                print("Error: Solana transfer detected but --private-key-file-sol not provided", file=sys.stderr)
                sys.exit(1)
            sig = _sign_solana(data, private_key_sol)
            print("    signed Solana tx", file=sys.stderr)
        else:
            if not private_key:
                print("Error: EVM transfer detected but --private-key-file not provided", file=sys.stderr)
                sys.exit(1)
            sig = _sign_evm_standard(data, private_key)
            print("    signed EVM tx", file=sys.stderr)

    # Clear keys from memory
    private_key = None
    private_key_sol = None

    # Step 3: send
    print(">>> Step 3: send", file=sys.stderr)
    # gasAccount must only be sent when it was actually selected by the server;
    # a present-but-unselected gasAccount would make `send` reject a standard transfer
    # (see docs/transfer.md Error Codes: "toc_agent only supports no-gas payment or native coin payment").
    send_gas_account = gas_account if (gas_account and gas_account.get("selected")) else None
    # NOTE: data.get("to") is NOT the recipient for token transfers — confirmed via a live
    # getTransferDataV4 call, the response's top-level "to" is the on-chain tx target (the
    # token contract), while the actual recipient comes back separately as "receiver". `send`'s
    # "to" must echo the original request's recipient, so always use args.to_address here.
    submit_resp = _api.send_transfer(
        chain=data.get("chain", args.chain),
        contract=data.get("contract", args.contract),
        from_=data.get("from", args.from_address),
        to=args.to_address,
        amount=data.get("amount", args.amount),
        sig=sig,
        gas_account=send_gas_account,
    )
    print(json.dumps(submit_resp, indent=2))

    if submit_resp.get("status") != 0:
        sys.exit(1)

    submit_data = submit_resp.get("data", {})
    print(f"\nOrderId: {order_id}", file=sys.stderr)
    txid = submit_data.get("txid", "")
    if txid:
        print(f"TxID: {txid}", file=sys.stderr)
    confirm_txt = submit_data.get("txConfirmTimeTxt", "")
    if confirm_txt:
        print(f"Confirm time: {confirm_txt}", file=sys.stderr)


if __name__ == "__main__":
    main()
