#!/usr/bin/env python3
"""
One-shot: makeOrder → sign (Social Login Wallet TEE) → send.

Social Login Wallet equivalent of order_make_sign_send.py.
No local private key needed — signing is done via Bitget Wallet TEE API.

Supports: EVM (gasPayMaster + regular tx), Solana, Tron.

Example:
  python3 scripts/social_order_make_sign_send.py \
    --wallet-id <walletId> \
    --order-id <from confirm> \
    --from-chain bnb --from-contract 0x55d3... --from-symbol USDT \
    --to-chain bnb --to-contract 0x8AC7... --to-symbol USDC \
    --from-address 0x39C6... --to-address 0x39C6... \
    --from-amount 23.35 --slippage 0.005 \
    --market bgwevmaggregator --protocol bgwevmaggregator_v000
"""

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_SOLANA_CHAIN_ID = 501

# Chain code → social-wallet chain param mapping
_EVM_CHAIN_MAP = {
    "eth": "eth",
    "bnb": "evm_custom#bnb",
    "base": "evm_custom#base",
    "arbitrum": "evm_custom#arb",
    "matic": "matic",
    "morph": "evm_custom#morph",
    "op": "evm_custom#op",
}

_EVM_CHAIN_ID_MAP = {
    "eth": 1,
    "bnb": 56,
    "base": 8453,
    "arbitrum": 42161,
    "matic": 137,
    "morph": 2818,
    "op": 10,
}


def _get_social_chain(api_chain: str) -> str:
    """Map API chain code to social-wallet chain param."""
    c = api_chain.lower()
    if c in _EVM_CHAIN_MAP:
        return _EVM_CHAIN_MAP[c]
    if c in ("sol", "solana"):
        return "sol"
    if c in ("trx", "tron"):
        return "tron"
    return c


def _is_solana_order(order_data: dict) -> bool:
    for tx_item in order_data.get("txs", []):
        derive = tx_item.get("deriveTransaction") or {}
        cid = tx_item.get("chainId") or derive.get("chainId")
        if cid is not None and int(cid) == _SOLANA_CHAIN_ID:
            return True
        chain = (tx_item.get("chain") or "").lower()
        if chain in ("sol", "solana"):
            return True
        if derive.get("serializedTransaction"):
            return True
        source = tx_item.get("source") or derive.get("source")
        if isinstance(source, dict) and source.get("serializedTransaction"):
            return True
    return False


def _is_tron_order(order_data: dict) -> bool:
    for tx_item in order_data.get("txs", []):
        chain = (tx_item.get("chain") or "").lower()
        if chain in ("trx", "tron"):
            return True
        if tx_item.get("transaction") and isinstance(tx_item["transaction"].get("raw_data_hex"), str):
            return True
    return False


def _sign_evm_gasPayMaster(tx_item: dict, social_chain: str, sw) -> str:
    """Sign gasPayMaster msgs (eth_sign hashes) via Social Login Wallet.
    Returns JSON string of msgs with sig fields filled."""
    derive = tx_item.get("deriveTransaction", {})
    msgs = derive.get("msgs") or tx_item.get("msgs") or []

    for m in msgs:
        h = m["hash"]
        result = sw.sign_message_return(social_chain, f"EthSign:{h}")
        m["sig"] = result.get("result", result.get("signature", ""))

    # Also update top-level msgs
    top_msgs = tx_item.get("msgs") or []
    for i, m in enumerate(top_msgs):
        derive_msgs = derive.get("msgs", [])
        if i < len(derive_msgs):
            m["sig"] = derive_msgs[i].get("sig", "")

    return json.dumps(derive.get("msgs") or msgs)


def _sign_evm_regular(tx_item: dict, social_chain: str, sw) -> str:
    """Sign a regular EVM tx via Social Login Wallet. Returns signed tx hex."""
    derive = tx_item.get("deriveTransaction", {})
    chain_id = derive.get("chainId") or tx_item.get("chainId", 1)

    sign_params = {
        "chain": social_chain,
        "chainId": int(chain_id),
        "to": derive.get("to") or tx_item.get("to", ""),
        "value": derive.get("value") or tx_item.get("value", 0),
        "data": derive.get("data") or tx_item.get("data", "0x"),
        "nonce": int(derive.get("nonce", tx_item.get("nonce", 0))),
        "gasLimit": str(derive.get("gasLimit", tx_item.get("gasLimit", 0))),
        "gasPrice": str(derive.get("gasPrice", tx_item.get("gasPrice", "0.000000001"))),
    }

    result = sw.sign_transaction_return(social_chain, sign_params)
    return result.get("result", result.get("signature", ""))


def _sign_tron(tx_item: dict, sw) -> str:
    """Sign a Tron tx via Social Login Wallet. Returns JSON string for send API."""
    derive = tx_item.get("deriveTransaction", {})
    transaction = derive.get("transaction") or tx_item.get("transaction")
    if not transaction:
        raise ValueError("Tron tx missing 'transaction' object")

    sign_params = {"chain": "tron", "transaction": transaction}
    result = sw.sign_transaction_return("tron", sign_params)
    sig_hex = result.get("result", result.get("signature", ""))

    # Wrap in format expected by send API
    sig_obj = {
        "signature": [sig_hex],
        "txID": transaction["txID"],
        "raw_data": transaction["raw_data"],
    }
    return json.dumps(sig_obj)


def _sign_solana(tx_item: dict, sw) -> str:
    """Sign a Solana tx via Social Login Wallet. Returns signed tx for send API."""
    derive = tx_item.get("deriveTransaction") or {}

    # Find serialized transaction
    serialized_tx = None
    source = derive.get("source") or tx_item.get("source")
    if isinstance(source, dict):
        serialized_tx = source.get("serializedTransaction")

    if not serialized_tx:
        data = tx_item.get("data", {})
        if isinstance(data, dict):
            serialized_tx = data.get("serializedTx") or data.get("serializedTransaction")

    if not serialized_tx:
        raise ValueError("Cannot find serializedTransaction in Solana tx item")

    # Use signData with serializedTransaction for Social Login Wallet
    sign_params = {
        "chain": "sol",
        "signData": {"serializedTransaction": serialized_tx, "version": "0"},
    }
    result = sw.sign_transaction_return("sol", sign_params)
    return result.get("result", result.get("signature", ""))


def main():
    parser = argparse.ArgumentParser(
        description="Social Login Wallet: makeOrder + sign (TEE) + send in one shot."
    )
    parser.add_argument("--wallet-id", required=True, help="Social Login Wallet walletId (from profile)")
    parser.add_argument("--order-id", required=True, help="From confirm response data.orderId")
    parser.add_argument("--from-address", required=True)
    parser.add_argument("--to-address", required=True)
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

    # Import API module
    _api = importlib.import_module("bitget-wallet-agent-api")

    # Import social wallet signing functions
    sw_path = SCRIPTS_DIR / "social-wallet.py"
    spec = importlib.util.spec_from_file_location("social_wallet", sw_path)
    sw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sw)
    sw.load_secret()
    if not sw.APPID or not sw.APPSECRET:
        print(f"ERROR: Missing Social Login Wallet credentials. Create {sw.SECRET_FILE}", file=sys.stderr)
        sys.exit(1)

    # Set wallet-id for API calls
    _api.WALLET_ID = args.wallet_id

    # Step 1: makeOrder
    print(">>> Step 1: makeOrder", file=sys.stderr)
    resp = _api.make_order(
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
        print(json.dumps(resp, indent=2))
        sys.exit(1)

    data = resp["data"]
    order_id = data["orderId"]
    txs = data["txs"]
    print(f"    orderId: {order_id}, txs: {len(txs)}", file=sys.stderr)

    # Step 2: Sign each tx
    print(">>> Step 2: sign (Social Login Wallet TEE)", file=sys.stderr)

    for i, tx in enumerate(txs):
        api_chain = (tx.get("chain") or args.from_chain).lower()
        social_chain = _get_social_chain(api_chain)
        derive = tx.get("deriveTransaction") or {}
        msgs = derive.get("msgs") or tx.get("msgs") or []

        if _is_tron_order({"txs": [tx]}):
            print(f"    tx[{i}]: Tron signing", file=sys.stderr)
            tx["sig"] = _sign_tron(tx, sw)

        elif _is_solana_order({"txs": [tx]}):
            print(f"    tx[{i}]: Solana signing", file=sys.stderr)
            tx["sig"] = _sign_solana(tx, sw)

        elif msgs and any(m.get("signType") == "eth_sign" for m in msgs):
            print(f"    tx[{i}]: EVM gasPayMaster ({len(msgs)} msg(s))", file=sys.stderr)
            tx["sig"] = _sign_evm_gasPayMaster(tx, social_chain, sw)

        else:
            print(f"    tx[{i}]: EVM regular tx", file=sys.stderr)
            tx["sig"] = _sign_evm_regular(tx, social_chain, sw)

    # Step 3: Send
    print(">>> Step 3: send", file=sys.stderr)
    send_resp = _api.send(order_id=order_id, txs=txs)
    print(json.dumps(send_resp, indent=2))

    if send_resp.get("status") != 0 or send_resp.get("error_code") != 0:
        sys.exit(1)

    print(
        f"\nOrderId: {order_id}\n"
        f"Check: python3 scripts/bitget-wallet-agent-api.py get-order-details --order-id {order_id}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
