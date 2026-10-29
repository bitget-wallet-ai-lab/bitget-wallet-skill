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
from decimal import Decimal
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


def _gas_price_to_native_str(val) -> str:
    """
    Convert a getTransferDataV4 gasPrice value into the decimal native-coin-unit string
    the Social Login Wallet TEE (sw.sign_transaction_return) expects — the same format
    social_order_make_sign_send.py already passes through verbatim for the swap flow (see
    its gasPrice handling: `str(derive.get("gasPrice", ...))`, no wei conversion), and
    matching docs/social-wallet.md's ETH/EVM field table ("gasPrice: Gas price in ETH units").
    getTransferDataV4 returns gasPrice as a plain decimal string in native-coin units already
    (e.g. "0.0000000001" BNB); converting that to wei before handing it to the TEE double-
    converts, since the TEE does its own ×1e18 conversion internally for this field —
    confirmed live: a wei-converted "100000000" gasPrice was signed into a raw tx with
    gasPrice=100000000e18. Only 0x-wei-hex (forward-compat, not yet observed) is converted here.

    NOTE: this does NOT apply to maxFeePerGas/maxPriorityFeePerGas — docs/social-wallet.md
    documents those two as taken in Wei (unlike gasPrice); use _fee_value_to_wei for them.
    """
    if isinstance(val, str) and val.startswith("0x"):
        return str(int(val, 16) / 1e18)
    return str(val)


def _fee_value_to_wei(val) -> int:
    """
    Convert a getTransferDataV4 maxFeePerGas/maxPriorityFeePerGas value — a plain decimal
    string in native-coin units (e.g. "0.0000000002" BNB), per the same quirk as gasPrice —
    into a Wei integer, per docs/social-wallet.md's ETH/EVM field table which documents these
    two EIP-1559 fields as taken in Wei by sw.sign_transaction_return (unlike gasPrice, which
    is native units — see _gas_price_to_native_str). 0x-wei-hex is accepted for forward
    compatibility.
    """
    if isinstance(val, str):
        if val.startswith("0x"):
            return int(val, 16)
        return int(float(val) * 1e18)
    return int(val)


def _extract_sig(result: dict, context: str) -> str:
    """
    Extract a signature string from a Social Login Wallet TEE response, failing closed
    instead of silently defaulting to "". An empty/missing signature must never reach
    `send` — that would broadcast (or attempt to broadcast) an effectively-unsigned
    transfer. Confirmed by review (2026-10-29): the previous `result.get("result",
    result.get("signature", ""))` pattern let a malformed/empty TEE response flow all the
    way through to `send` with signature="".
    """
    sig = result.get("result") or result.get("signature") or ""
    if not sig:
        raise ValueError(f"{context}: TEE returned no signature (result={result!r})")
    return sig


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
        m["sig"] = _extract_sig(result, f"EVM gasless legacy msgType={m.get('msgType')!r}")
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

    print("    WARNING: signDataV2/EIP-712 gasless path uses an unverified best-effort TEE call "
          "(no dedicated EIP-712 method) — not yet confirmed via joint debugging, see docs/transfer.md",
          file=sys.stderr)

    results = []
    for item in items:
        typed = item.get("data", {})
        domain = typed.get("domain", {})
        message = typed.get("message", {})
        result = sw.sign_transaction_return(social_chain, {"signTypeData": typed})
        sig = _extract_sig(result, "EVM gasless signDataV2/EIP-712")
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

    raw_value = data.get("value", "0")
    if isinstance(raw_value, str) and raw_value.startswith("0x"):
        # value-as-wei-hex (standard EVM tx-field convention) — convert to the native-unit
        # number sw.sign_transaction_return expects (docs/social-wallet.md ETH/EVM field
        # table: "value: number, Amount in native token units"). Decimal avoids float
        # rounding on the division; cast to float only at the end since sign_params needs
        # a JSON-serializable number, not a Decimal.
        value_val = float(Decimal(int(raw_value, 16)) / Decimal(10 ** 18))
    elif isinstance(raw_value, str) and "." in raw_value:
        # Already a native-coin decimal string (e.g. "0.1" BNB) from getTransferDataV4.
        # The TEE wants this in native units too — pass it through, do NOT ×1e18.
        # (A previous version multiplied by 1e18 here, which wei-converts a value the
        # TEE expects in native units — wrong direction, confirmed by review 2026-10-29.
        # ERC-20/token transfers always carry value=0 so this branch was never
        # exercised by live testing; needs live confirmation for a nonzero native
        # transfer before fully trusting this direction.)
        value_val = float(raw_value)
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
        sign_params["maxFeePerGas"] = str(_fee_value_to_wei(data.get("maxFeePerGas", "0")))
        sign_params["maxPriorityFeePerGas"] = str(_fee_value_to_wei(data.get("maxPriorityFeePerGas", "0")))
    else:
        sign_params["gasPrice"] = _gas_price_to_native_str(data.get("gasPrice", "0"))

    result = sw.sign_transaction_return(social_chain, sign_params)
    return _extract_sig(result, "EVM standard")


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
    return _extract_sig(result, "Solana")


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
    parser.add_argument("--confirm-nonce-override", dest="confirm_nonce_override", action="store_true",
                        help="Proceed even when the server reports "
                             "hasPendingTransactionAndOverwriteNonce=true (reusing a nonce from a "
                             "still-pending transaction on this address, which can replace or race "
                             "it). Only pass this after the user has explicitly confirmed they want "
                             "to override the pending transaction.")
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

    # estimateRevert now lives under fee.* (moved there from the old top-level
    # makeTransferOrder response) — abort before signing rather than submitting a
    # transaction already predicted to fail on-chain.
    if fee.get("estimateRevert"):
        reason = fee.get("estimateRevertReason") or "transaction predicted to fail"
        print(f"ERROR: estimateRevert=true — {reason}. Aborting.", file=sys.stderr)
        sys.exit(1)

    if data.get("hasPendingTransactionAndOverwriteNonce"):
        if not args.confirm_nonce_override:
            print("ERROR: hasPendingTransactionAndOverwriteNonce=true — the server would reuse a "
                  "nonce from a still-pending transaction on this address. Signing and sending now "
                  "would race that pending transaction: whichever one confirms first invalidates the "
                  "other (replacement, or the new one failing as an already-used nonce). Aborting — "
                  "wait for the pending transaction to clear and retry, or re-run with "
                  "--confirm-nonce-override only after the user has explicitly confirmed they want "
                  "to override the pending transaction.", file=sys.stderr)
            sys.exit(1)
        print("WARNING: hasPendingTransactionAndOverwriteNonce=true — proceeding with nonce "
              "override as explicitly confirmed via --confirm-nonce-override.", file=sys.stderr)

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
