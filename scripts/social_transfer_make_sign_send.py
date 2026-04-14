#!/usr/bin/env python3
"""
One-shot: makeTransferOrder -> sign (Social Login Wallet TEE) -> submitTransferOrder.

Social Login Wallet equivalent of transfer_make_sign_send.py.
No local private key needed — signing is done via Bitget Wallet TEE API.

Supports: EVM (evm_legacy, evm_1559, evm_7702 gasless), Solana (sol_raw, sol_partial).

Example (EVM gasless):
  python3 scripts/social_transfer_make_sign_send.py \\
    --wallet-id <walletId> \\
    --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955 \\
    --from-address 0xAbC... --to-address 0xDeF... \\
    --amount 1 --gasless

Example (Solana):
  python3 scripts/social_transfer_make_sign_send.py \\
    --wallet-id <walletId> \\
    --chain sol --contract Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB \\
    --from-address ApPjj... --to-address 7xKXt... \\
    --amount 10
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Chain code → social-wallet chain param mapping (same as social_order_make_sign_send.py)
_EVM_CHAIN_MAP = {
    "eth": "eth",
    "bnb": "evm_custom#bnb",
    "base": "evm_custom#base",
    "arbitrum": "evm_custom#arb",
    "matic": "matic",
    "morph": "evm_custom#morph",
}


def _get_social_chain(api_chain: str) -> str:
    c = api_chain.lower()
    if c in _EVM_CHAIN_MAP:
        return _EVM_CHAIN_MAP[c]
    if c in ("sol", "solana"):
        return "sol"
    return c


def _sign_evm_7702(source: dict, social_chain: str, sw) -> str:
    """Sign evm_7702 msgToSign items via Social Login Wallet TEE."""
    msgs = source.get("evm7702", {}).get("msgToSign", [])
    if not msgs:
        raise ValueError("evm_7702 source has no msgToSign")

    for m in msgs:
        h = m.get("hash", "")
        if not h:
            raise ValueError(f"msgToSign item missing hash: {m}")
        result = sw.sign_message_return(social_chain, f"EthSign:{h}")
        m["sig"] = result.get("result", result.get("signature", ""))
        print(f"    [{m['msgType']}] signed", file=sys.stderr)

    return json.dumps(msgs)


def _parse_hex_or_int(val, default=0):
    """Parse a hex string (0x-prefixed) or decimal string/int to int."""
    if isinstance(val, str) and val.startswith("0x"):
        return int(val, 16)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _sign_evm_standard(source: dict, social_chain: str, sw) -> str:
    """Sign evm_legacy or evm_1559 source via Social Login Wallet TEE."""
    evm = source.get("evm", {})
    source_type = source.get("type", "evm_legacy")

    sign_params = {
        "chain": social_chain,
        "chainId": _parse_hex_or_int(evm.get("chainId", 1), default=1),
        "to": evm.get("to", ""),
        "value": _parse_hex_or_int(evm.get("value", "0x0")),
        "data": evm.get("data", "0x"),
        "nonce": _parse_hex_or_int(evm.get("nonce", 0)),
        "gasLimit": str(_parse_hex_or_int(evm.get("gasLimit", 0))),
    }

    if source_type == "evm_1559":
        sign_params["maxFeePerGas"] = str(_parse_hex_or_int(evm.get("maxFeePerGas", "0x0")))
        sign_params["maxPriorityFeePerGas"] = str(_parse_hex_or_int(evm.get("maxPriorityFeePerGas", "0x0")))
    else:
        sign_params["gasPrice"] = str(_parse_hex_or_int(evm.get("gasPrice", "0x0")))

    result = sw.sign_transaction_return(social_chain, sign_params)
    return result.get("result", result.get("signature", ""))


def _sign_solana(source: dict, sw) -> str:
    """Sign sol_raw or sol_partial via Social Login Wallet TEE."""
    sol = source.get("sol", {})
    raw_tx = sol.get("rawTx", "")
    if not raw_tx:
        raise ValueError("Solana source has no rawTx")

    sign_params = {
        "chain": "sol",
        "signData": {"serializedTransaction": raw_tx, "version": "0"},
    }
    result = sw.sign_transaction_return("sol", sign_params)
    return result.get("result", result.get("signature", ""))


def main():
    parser = argparse.ArgumentParser(
        description="Social Login Wallet: makeTransferOrder + sign (TEE) + submitTransferOrder in one shot."
    )
    parser.add_argument("--wallet-id", dest="wallet_id", required=True,
                        help="Social Login Wallet walletId (from profile)")
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

    # Import API module
    _api = importlib.import_module("bitget-wallet-agent-api")
    _api.WALLET_ID = args.wallet_id

    # Import social wallet module
    sw_path = SCRIPTS_DIR / "social-wallet.py"
    spec = importlib.util.spec_from_file_location("social_wallet", sw_path)
    sw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sw)
    sw.load_secret()
    if not sw.APPID or not sw.APPSECRET:
        print(f"ERROR: Missing Social Login Wallet credentials. Create {sw.SECRET_FILE}", file=sys.stderr)
        sys.exit(1)

    social_chain = _get_social_chain(args.chain)

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

    if resp.get("status") != 0:
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
        print("Error: no orderId in response", file=sys.stderr)
        sys.exit(1)

    print(f"    orderId: {order_id}", file=sys.stderr)
    print(f"    chain: {data.get('chain')}, amount: {data.get('amount')}", file=sys.stderr)

    # Check estimateRevert
    if data.get("estimateRevert"):
        print("ERROR: estimateRevert=true — transaction predicted to fail. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Gasless status
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
        print(f"    gasless: pay {no_gas_info.get('payAmount')} {no_gas_info.get('payTokenSymbol')}", file=sys.stderr)
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

    source = data.get("source", {})
    source_type = source.get("type", "")
    print(f"    source.type: {source_type}", file=sys.stderr)

    # Step 2: Sign via Social Login Wallet TEE
    print(">>> Step 2: sign (Social Login Wallet TEE)", file=sys.stderr)

    if source_type == "evm_7702":
        sig = _sign_evm_7702(source, social_chain, sw)

    elif source_type in ("evm_legacy", "evm_1559"):
        sig = _sign_evm_standard(source, social_chain, sw)
        print(f"    signed EVM {source_type} tx", file=sys.stderr)

    elif source_type in ("sol_raw", "sol_partial"):
        sig = _sign_solana(source, sw)
        print(f"    signed Solana {source_type} tx", file=sys.stderr)

    elif source_type == "evm_morph_altfee":
        print("ERROR: evm_morph_altfee requires viem + Morph serializer, not supported via Social Login Wallet.", file=sys.stderr)
        sys.exit(1)

    else:
        print(f"ERROR: unsupported source.type: {source_type!r}", file=sys.stderr)
        sys.exit(1)

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
