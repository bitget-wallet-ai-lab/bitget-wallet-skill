#!/usr/bin/env python3
"""
One-shot: makeTransferOrder -> sign -> submitTransferOrder.

Gasless token transfer for EVM (eth/bnb/base/arbitrum/matic/morph) and Solana.
Signing is done locally; the server handles broadcasting and on-chain tracking.

Supports all source.type modes:
  - evm_legacy     : BNB Chain legacy gasPrice tx
  - evm_1559       : EIP-1559 (ETH/Base/Arbitrum/Polygon/Morph)
  - evm_7702       : EIP-7702 gasless (auth + call message signing)
  - evm_morph_altfee: Morph type-0x7f AltFee (NOT handled here; use altFeeSource externally)
  - sol_raw         : Solana full unsigned transaction
  - sol_partial     : Solana partial-signed (feePayer already signed)

Security: Private keys are NEVER passed as CLI arguments.
Write the key to a unique temp file programmatically, pass the file path.

Example (EVM gasless transfer):
  python3 scripts/transfer_make_sign_send.py \\
    --private-key-file /tmp/.pk_evm \\
    --chain base --contract 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \\
    --from-address 0xAbC... --to-address 0xDeF... \\
    --amount 50 --gasless

Example (Solana gasless transfer):
  python3 scripts/transfer_make_sign_send.py \\
    --private-key-file-sol /tmp/.pk_sol \\
    --chain sol --contract Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB \\
    --from-address ApPjj... --to-address 7xKXt... \\
    --amount 10 --gasless
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


def _sign_evm_standard(source: dict, private_key: str) -> str:
    """
    Sign evm_legacy or evm_1559 source data. Returns signed raw tx hex (0x-prefixed).
    """
    from eth_account import Account
    acct = Account.from_key(private_key)

    evm = source.get("evm", {})
    to_addr = evm.get("to", "")
    if to_addr and to_addr.startswith("0x"):
        from eth_utils import to_checksum_address
        to_addr = to_checksum_address(to_addr)

    tx_dict = {
        "to": to_addr,
        "data": evm.get("data", "0x"),
        "gas": int(evm.get("gasLimit", "0x0"), 16) if isinstance(evm.get("gasLimit"), str) and evm.get("gasLimit", "").startswith("0x") else int(evm.get("gasLimit", 0)),
        "nonce": int(evm.get("nonce", 0)),
        "chainId": int(evm.get("chainId", 1)),
    }

    value = evm.get("value", "0x0")
    if isinstance(value, str) and value.startswith("0x"):
        tx_dict["value"] = int(value, 16)
    else:
        tx_dict["value"] = int(value)

    source_type = source.get("type", "")

    if source_type == "evm_1559":
        max_fee = evm.get("maxFeePerGas", "0x0")
        max_priority = evm.get("maxPriorityFeePerGas", "0x0")
        tx_dict["maxFeePerGas"] = int(max_fee, 16) if isinstance(max_fee, str) and max_fee.startswith("0x") else int(max_fee)
        tx_dict["maxPriorityFeePerGas"] = int(max_priority, 16) if isinstance(max_priority, str) and max_priority.startswith("0x") else int(max_priority)
        tx_dict["type"] = 2
    else:
        gas_price = evm.get("gasPrice", "0x0")
        tx_dict["gasPrice"] = int(gas_price, 16) if isinstance(gas_price, str) and gas_price.startswith("0x") else int(gas_price)

    signed_tx = acct.sign_transaction(tx_dict)
    return "0x" + signed_tx.raw_transaction.hex()


def _sign_evm_7702(source: dict, private_key: str) -> str:
    """
    Sign evm_7702 source data. Returns JSON.stringify(signedMsgs).
    Each msgToSign item has a 'hash' field to sign with unsafe_sign_hash.
    """
    from eth_account import Account
    acct = Account.from_key(private_key)

    evm7702 = source.get("evm7702", {})
    msgs = evm7702.get("msgToSign", [])
    if not msgs:
        raise ValueError("evm_7702 source has no msgToSign")

    for msg in msgs:
        msg_hash = msg.get("hash", "")
        if not msg_hash:
            raise ValueError(f"msgToSign item missing 'hash': {msg}")
        hash_bytes = bytes.fromhex(msg_hash.replace("0x", ""))
        signed = acct.unsafe_sign_hash(hash_bytes)
        sig_hex = signed.signature.hex()
        msg["sig"] = sig_hex if sig_hex.startswith("0x") else "0x" + sig_hex

    return json.dumps(msgs)


def _sign_solana(source: dict, private_key_sol: str) -> str:
    """
    Sign sol_raw or sol_partial source data. Returns base58 signed transaction.
    For sol_partial, feePayer has already signed slot 0.
    """
    from order_sign import sign_solana_tx, _load_sol_keypair

    sol = source.get("sol", {})
    raw_tx = sol.get("rawTx", "")
    if not raw_tx:
        raise ValueError("Solana source has no rawTx")

    seed, pubkey = _load_sol_keypair(private_key_sol)
    return sign_solana_tx(raw_tx, seed, pubkey)


def main():
    parser = argparse.ArgumentParser(
        description="Gasless token transfer: makeTransferOrder + sign + submitTransferOrder. "
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
    parser.add_argument("--memo", default="",
                        help="Optional memo written to chain transaction")
    parser.add_argument("--gasless", action="store_true",
                        help="Request gasless transfer (gas paid from token balance)")
    parser.add_argument("--gasless-pay-token", dest="gasless_pay_token", default="",
                        help="Gasless: contract address of token to pay gas with")
    parser.add_argument("--override-7702", dest="override_7702", action="store_true",
                        help="[DANGEROUS] Overwrite an existing third-party EIP-7702 binding. "
                             "Script will prompt for confirmation before proceeding.")
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

    # Step 1: makeTransferOrder
    print(">>> Step 1: makeTransferOrder", file=sys.stderr)
    resp = _api.make_transfer_order(
        chain=args.chain,
        contract=args.contract,
        from_=args.from_address,
        to=args.to_address,
        amount=args.amount,
        memo=args.memo,
        no_gas=args.gasless,
        no_gas_pay_token=args.gasless_pay_token,
        override7702=args.override_7702,
    )

    status = resp.get("status", -1)
    if status != 0:
        error_code = resp.get("error_code") or resp.get("data", {}).get("error_code")
        if error_code == 30108:
            print("ERROR: Existing third-party EIP-7702 binding detected on this address.", file=sys.stderr)
            print("Gasless transfer requires overwriting this binding.", file=sys.stderr)
            print("To override, re-run with --override-7702 (this will REPLACE the existing binding).", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    data = resp.get("data", {})
    order_id = data.get("orderId")
    if not order_id:
        print("Error: no orderId in makeTransferOrder response", file=sys.stderr)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    print(f"    orderId: {order_id}", file=sys.stderr)
    print(f"    chain: {data.get('chain')}, from: {data.get('from')}, to: {data.get('to')}", file=sys.stderr)
    print(f"    amount: {data.get('amount')}, contract: {data.get('contract')}", file=sys.stderr)

    # Check estimateRevert
    if data.get("estimateRevert"):
        print("WARNING: Transaction is estimated to fail (insufficient balance, contract revert, etc.).",
              file=sys.stderr)
        print("Aborting — do not proceed with this transfer.", file=sys.stderr)
        print(json.dumps({"status": -1, "msg": "estimateRevert=true, transaction likely to fail",
                          "orderId": order_id, "fee": data.get("fee")}, indent=2))
        sys.exit(1)

    # Check gasless availability
    no_gas_info = data.get("noGas")
    if args.gasless and not no_gas_info:
        print("WARNING: Gasless requested but not available for this transfer.", file=sys.stderr)
        print("Reason: amount below threshold, chain not supported, or no eligible pay token.", file=sys.stderr)
        print("This will fall back to a STANDARD transfer (native gas required).", file=sys.stderr)
        confirm = input("Type 'yes' to proceed with standard transfer, anything else to abort: ").strip()
        if confirm != "yes":
            print("Aborted — gasless not available and fallback not confirmed.", file=sys.stderr)
            sys.exit(1)
        print("    Proceeding with standard transfer (user confirmed).", file=sys.stderr)
    elif no_gas_info and no_gas_info.get("available"):
        print(f"    gasless: {no_gas_info.get('payTokenSymbol')} "
              f"(pay: {no_gas_info.get('payAmount')} {no_gas_info.get('payTokenSymbol')})",
              file=sys.stderr)
        if no_gas_info.get("warn"):
            print(f"    WARNING: {no_gas_info['warn']}", file=sys.stderr)

    # EIP-7702 override confirmation
    if args.override_7702 and no_gas_info and no_gas_info.get("need7702Auth"):
        print("", file=sys.stderr)
        print("⚠️  EIP-7702 OVERRIDE WARNING", file=sys.stderr)
        print("This will OVERWRITE the existing third-party EIP-7702 binding on this address.", file=sys.stderr)
        print("This is a permanent account-level change. The previous binding cannot be restored.", file=sys.stderr)
        if no_gas_info.get("warn"):
            print(f"Server warning: {no_gas_info['warn']}", file=sys.stderr)
        print("", file=sys.stderr)
        confirm = input("Type 'yes' to confirm override, anything else to abort: ").strip()
        if confirm != "yes":
            print("Aborted — 7702 override not confirmed.", file=sys.stderr)
            sys.exit(1)
        print("    7702 override confirmed by user.", file=sys.stderr)

    # Fee info
    fee = data.get("fee", {})
    if fee:
        print(f"    fee: {fee.get('fee')} {fee.get('coin')}, "
              f"balance: {fee.get('balance')}, enough: {fee.get('balanceForFeeEnough')}",
              file=sys.stderr)

    source = data.get("source", {})
    source_type = source.get("type", "")
    print(f"    source.type: {source_type}", file=sys.stderr)

    # Step 2: Sign
    print(">>> Step 2: sign", file=sys.stderr)
    sig = None

    if source_type in ("evm_legacy", "evm_1559"):
        if not private_key:
            print("Error: EVM transfer detected but --private-key-file not provided", file=sys.stderr)
            sys.exit(1)
        sig = _sign_evm_standard(source, private_key)
        print(f"    signed EVM {source_type} raw tx", file=sys.stderr)

    elif source_type == "evm_7702":
        if not private_key:
            print("Error: EVM 7702 transfer detected but --private-key-file not provided", file=sys.stderr)
            sys.exit(1)
        sig = _sign_evm_7702(source, private_key)
        print(f"    signed EVM 7702 ({len(source.get('evm7702', {}).get('msgToSign', []))} msg(s))",
              file=sys.stderr)

    elif source_type in ("sol_raw", "sol_partial"):
        if not private_key_sol:
            print("Error: Solana transfer detected but --private-key-file-sol not provided", file=sys.stderr)
            sys.exit(1)
        sig = _sign_solana(source, private_key_sol)
        print(f"    signed Solana {source_type} tx", file=sys.stderr)

    elif source_type == "evm_morph_altfee":
        print("Error: evm_morph_altfee (Morph AltFee) requires viem + Morph serializer. "
              "Use the standard source (evm_1559) with --no-altfee, or sign externally.",
              file=sys.stderr)
        sys.exit(1)

    else:
        print(f"Error: unsupported source.type: {source_type!r}", file=sys.stderr)
        sys.exit(1)

    # Clear keys from memory
    private_key = None
    private_key_sol = None

    # Step 3: submitTransferOrder
    print(">>> Step 3: submitTransferOrder", file=sys.stderr)
    submit_resp = _api.submit_transfer_order(order_id=order_id, sig=sig)
    print(json.dumps(submit_resp, indent=2))

    if submit_resp.get("status") != 0:
        sys.exit(1)

    submit_data = submit_resp.get("data", {})
    print(f"\nOrderId: {order_id}", file=sys.stderr)
    print(f"Status: {submit_data.get('orderStatus', 'unknown')}", file=sys.stderr)
    txid = submit_data.get("txid", "")
    if txid:
        print(f"TxID: {txid}", file=sys.stderr)
    print(f"Check: python3 scripts/bitget-wallet-agent-api.py get-transfer-order --order-id {order_id}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
