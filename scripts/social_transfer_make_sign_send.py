#!/usr/bin/env python3
"""
One-shot: getTransferDataV4 -> sign (Social Login Wallet TEE) -> send.

Social Login Wallet equivalent of transfer_make_sign_send.py.
No local private key needed — signing is done via Bitget Wallet TEE API.
Gasless mode (gas paid from token balance) is chosen automatically by the
server based on the sender's native-coin balance — there is no client-side
flag to request or force it.

Signature dispatch is driven by the getTransferDataV4 response:
  - Standard self-pay EVM : sign the flat tx fields (EIP-1559 or legacy gasPrice)
  - Standard self-pay SOL : sign the raw unsigned transaction
  - EVM gasless (signDataV2) : EIP-712 typed-data signing
  - EVM gasless (signData)   : legacy gasless message signing (sign_7702_msgs)
  - SOL gasless             : sign the raw unsigned transaction

Example (EVM — gasless/standard chosen automatically by the server):
  python3 scripts/social_transfer_make_sign_send.py \\
    --wallet-id <walletId> \\
    --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955 \\
    --from-address 0xAbC... --to-address 0xDeF... \\
    --amount 1

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


def _parse_hex_or_int(val, default=0):
    """Parse a hex string (0x-prefixed) or decimal string/int to int."""
    if isinstance(val, str) and val.startswith("0x"):
        return int(val, 16)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _parse_fee_value(val) -> int:
    """
    Parse a gasPrice/maxFeePerGas/maxPriorityFeePerGas value from getTransferDataV4.
    Confirmed via a live call: these come back as a plain decimal string in native-coin
    units (e.g. "0.0000000001" BNB), NOT wei-hex. _parse_hex_or_int would silently return
    its `default` (0) on a decimal-point string via the swallowed ValueError, signing a
    tx with gasPrice=0 — this parses it correctly instead.
    """
    if isinstance(val, str):
        if val.startswith("0x"):
            return int(val, 16)
        if "." in val:
            fval = float(val)
            return int(fval * 1e18) if 0 < fval < 1 else int(fval * 1e9)
        return int(val)
    return int(val)


def _sign_evm_gasless_legacy(data: dict, social_chain: str, sw) -> str:
    """Sign EVM gasless legacy message data (signData.sign_type == "sign_7702_msgs")
    via Social Login Wallet TEE.

    Reads the msg array from data["signData"]["data"]; each item carries a 'hash'
    field signed with the EthSign TEE path. The signature is written back to the
    item's 'sig' field. Returns json.dumps(msgs)."""
    msgs = data.get("signData", {}).get("data", [])
    if not msgs:
        raise ValueError("gasless signData has no data to sign")

    for m in msgs:
        h = m.get("hash", "")
        if not h:
            raise ValueError(f"signData item missing 'hash': {m}")
        if len(h.replace("0x", "")) != 64:  # 32 bytes = 64 hex chars
            raise ValueError(f"Invalid hash length for msgType={m.get('msgType')!r}: {h!r} (expected 32 bytes)")
        result = sw.sign_message_return(social_chain, f"EthSign:{h}")
        m["sig"] = result.get("result", result.get("signature", ""))
        print(f"    [{m.get('msgType', 'unknown')}] signed", file=sys.stderr)

    return json.dumps(msgs)


def _sign_evm_typed_data_v2(data: dict, social_chain: str, sw) -> str:
    """Sign EVM gasless EIP-712 typed data (signDataV2) via Social Login Wallet TEE.

    Each item carries a typed-data payload under item["data"] with domain/types/message.

    NOTE (best-effort): social-wallet.py exposes no dedicated EIP-712 typed-data
    signing method (only sign_message_return / sign_transaction_return), so this
    passes the full typed-data object to sign_transaction_return under the
    "signTypeData" key as a best-effort. This path MUST be validated against the
    real TEE backend before production use.

    Returns json.dumps of a list of {"domain", "message", "signature"} objects."""
    items = data.get("signDataV2", [])
    if not items:
        raise ValueError("gasless signDataV2 has no data to sign")

    results = []
    for item in items:
        typed = item.get("data", {})
        domain = typed.get("domain", {})
        message = typed.get("message", {})
        result = sw.sign_transaction_return(social_chain, {"signTypeData": typed})
        sig = result.get("result", result.get("signature", ""))
        results.append({
            "domain": domain,
            "message": message,
            "signature": sig,
        })

    return json.dumps(results)


def _sign_evm_standard(data: dict, social_chain: str, sw) -> str:
    """Sign a standard self-pay EVM transaction from the flat response data via TEE.
    Chooses EIP-1559 vs legacy by the presence of maxFeePerGas/maxPriorityFeePerGas."""
    raw_nonce = data.get("nonce")
    if raw_nonce is None:
        raise ValueError("Missing required field 'nonce' in EVM data")
    raw_gas = data.get("gasLimit")
    if not raw_gas:
        raise ValueError("Missing required field 'gasLimit' in EVM data")
    gas_val = _parse_hex_or_int(raw_gas)
    if gas_val == 0:
        raise ValueError("gasLimit is zero — refusing to sign transaction that will certainly fail")

    raw_value = data.get("value", "0x0")
    if isinstance(raw_value, str) and "." in raw_value and not raw_value.startswith("0x"):
        # Same native-coin-decimal quirk as gasPrice below — e.g. "5" BNB, not wei.
        value_val = int(float(raw_value) * 1e18)
    else:
        value_val = _parse_hex_or_int(raw_value)

    sign_params = {
        "chain": social_chain,
        "chainId": _parse_hex_or_int(data.get("chainId", 1), default=1),
        "to": data.get("to", ""),
        "value": value_val,
        "data": data.get("data", "0x"),
        "nonce": _parse_hex_or_int(raw_nonce),
        "gasLimit": str(gas_val),
    }

    if data.get("maxFeePerGas") is not None or data.get("maxPriorityFeePerGas") is not None:
        sign_params["maxFeePerGas"] = str(_parse_fee_value(data.get("maxFeePerGas", "0x0")))
        sign_params["maxPriorityFeePerGas"] = str(_parse_fee_value(data.get("maxPriorityFeePerGas", "0x0")))
    else:
        sign_params["gasPrice"] = str(_parse_fee_value(data.get("gasPrice", "0x0")))

    result = sw.sign_transaction_return(social_chain, sign_params)
    return result.get("result", result.get("signature", ""))


def _sign_solana(data: dict, sw) -> str:
    """Sign a Solana raw unsigned transaction from the flat response data via TEE.
    Tries rawTx / serializedTx / serializedTransaction in order."""
    raw_tx = data.get("rawTx") or data.get("serializedTx") or data.get("serializedTransaction")
    if not raw_tx:
        raise ValueError(f"Solana source has no recognized raw-tx field, got keys: {list(data.keys())}")

    sign_params = {
        "chain": "sol",
        "signData": {"serializedTransaction": raw_tx, "version": "0"},
    }
    result = sw.sign_transaction_return("sol", sign_params)
    return result.get("result", result.get("signature", ""))


def main():
    parser = argparse.ArgumentParser(
        description="Social Login Wallet: getTransferDataV4 + sign (TEE) + send in one shot."
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

    # Step 1: getTransferDataV4
    print(">>> Step 1: getTransferDataV4", file=sys.stderr)
    resp = _api.get_transfer_data_v4(
        chain=args.chain,
        contract=args.contract,
        from_=args.from_address,
        to=args.to_address,
        amount=args.amount,
    )

    if resp.get("status") != 0:
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

    # chainType is the documented discriminator, but its presence on every response shape is
    # unconfirmed; fall back to the CLI-supplied --chain (unambiguous) if it's absent/different.
    is_sol = data.get("chainType") == "sol" or args.chain.lower() in ("sol", "solana")

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

    # Fee info (display only)
    fee = data.get("fee", {})
    if fee:
        print(f"    fee: {fee.get('fee')}, "
              f"balance: {fee.get('balance')}, enough: {fee.get('balanceForFeeEnough')}",
              file=sys.stderr)

    # Step 2: Sign via Social Login Wallet TEE
    print(">>> Step 2: sign (Social Login Wallet TEE)", file=sys.stderr)
    sig = None

    if gas_account and gas_account.get("selected"):
        sid = gas_account.get("pay", {}).get("sid") or gas_account.get("sid")
        if sid == "transfer_no_gas_trx":
            print("ERROR: TRX gasless not supported yet.", file=sys.stderr)
            sys.exit(1)
        elif data.get("signDataV2"):
            sig = _sign_evm_typed_data_v2(data, social_chain, sw)
            print("    signed EVM gasless (signDataV2/EIP-712)", file=sys.stderr)
        elif data.get("signData", {}).get("sign_type") == "sign_7702_msgs":
            sig = _sign_evm_gasless_legacy(data, social_chain, sw)
            print("    signed EVM gasless (signData legacy)", file=sys.stderr)
        elif is_sol:
            sig = _sign_solana(data, sw)
            print("    signed Solana gasless tx", file=sys.stderr)
        else:
            print(f"ERROR: unrecognized gasless signature shape for sid={sid!r}", file=sys.stderr)
            sys.exit(1)
    else:
        if is_sol:
            sig = _sign_solana(data, sw)
            print("    signed Solana tx", file=sys.stderr)
        else:
            sig = _sign_evm_standard(data, social_chain, sw)
            print("    signed EVM tx", file=sys.stderr)

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
