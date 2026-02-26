#!/usr/bin/env python3
"""
Bitget Wallet ToB API client.
Built-in demo credentials or override via env vars.
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import requests

BASE_URL = "https://bopenapi.bgwapi.io"

# Public demo credentials for testing purposes. These may change over time —
# if they stop working, please update the skill to get the latest keys.
# Override via BGW_API_KEY / BGW_API_SECRET env vars.
DEFAULT_API_KEY = "4843D8C3F1E20772C0E634EDACC5C5F9A0E2DC92"
DEFAULT_API_SECRET = "F2ABFDC684BDC6775FD6286B8D06A3AAD30FD587"


def get_credentials():
    """Load appId and apiSecret from env vars or use built-in defaults."""
    api_key = os.environ.get("BGW_API_KEY", DEFAULT_API_KEY)
    api_secret = os.environ.get("BGW_API_SECRET", DEFAULT_API_SECRET)
    return api_key, api_secret


def sign_request(api_path, body_str, api_key, api_secret, timestamp, query_params=None):
    """Generate HMAC-SHA256 signature per Bitget Wallet docs."""
    content = {
        "apiPath": api_path,
        "body": body_str,
        "x-api-key": api_key,
        "x-api-timestamp": timestamp,
    }
    if query_params:
        for k, v in query_params.items():
            content[k] = str(v)

    # Sort keys alphabetically
    sorted_content = dict(sorted(content.items()))
    payload = json.dumps(sorted_content, separators=(',', ':'))

    sig = hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()


DEFAULT_PARTNER_CODE = "bgw_swap_public"


def api_request(path, body=None):
    """Make authenticated API request."""
    api_key, api_secret = get_credentials()
    timestamp = str(int(time.time() * 1000))
    body_str = json.dumps(body, separators=(',', ':'), sort_keys=True) if body else ""

    signature = sign_request(path, body_str, api_key, api_secret, timestamp)

    url = BASE_URL + path
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "x-api-timestamp": timestamp,
        "x-api-signature": signature,
    }
    # Swap endpoints require Partner-Code header
    if "/swapx/" in path:
        headers["Partner-Code"] = os.environ.get("BGW_PARTNER_CODE", DEFAULT_PARTNER_CODE)

    try:
        resp = requests.post(url, data=body_str if body_str else None, headers=headers, timeout=30)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "message": resp.text[:500]}
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def _get_single_token_info(chain, contract):
    """Get single token info via batchGetBaseInfo (getBaseInfo returns 400)."""
    body = {"list": [{"chain": chain, "contract": contract}]}
    result = api_request("/bgw-pro/market/v3/coin/batchGetBaseInfo", body)
    if "data" in result and "list" in result["data"] and result["data"]["list"]:
        return {"data": result["data"]["list"][0], "status": result.get("status", 0)}
    return result


def cmd_token_info(args):
    result = _get_single_token_info(args.chain, args.contract)
    print(json.dumps(result, indent=2))


def cmd_token_price(args):
    result = _get_single_token_info(args.chain, args.contract)
    if "data" in result:
        d = result["data"]
        print(json.dumps({
            "symbol": d.get("symbol"),
            "name": d.get("name"),
            "price": d.get("price"),
            "chain": args.chain,
            "contract": args.contract,
        }, indent=2))
    else:
        print(json.dumps(result, indent=2))


def cmd_batch_token_info(args):
    tokens = []
    for item in args.tokens.split(","):
        chain, contract = item.strip().split(":", 1)
        tokens.append({"chain": chain, "contract": contract})
    body = {"list": tokens}
    print(json.dumps(api_request("/bgw-pro/market/v3/coin/batchGetBaseInfo", body), indent=2))


def cmd_kline(args):
    body = {"chain": args.chain, "contract": args.contract, "period": args.period, "size": args.size}
    print(json.dumps(api_request("/bgw-pro/market/v3/coin/getKline", body), indent=2))


def cmd_tx_info(args):
    body = {"chain": args.chain, "contract": args.contract}
    print(json.dumps(api_request("/bgw-pro/market/v3/coin/getTxInfo", body), indent=2))


def cmd_batch_tx_info(args):
    """Batch get transaction statistics for multiple tokens."""
    tokens = []
    for item in args.tokens.split(","):
        chain, contract = item.strip().split(":", 1)
        tokens.append({"chain": chain, "contract": contract})
    body = {"list": tokens}
    print(json.dumps(api_request("/bgw-pro/market/v3/coin/batchGetTxInfo", body), indent=2))


def cmd_historical_coins(args):
    """Get token list by timestamp (paginated)."""
    body = {"createTime": args.create_time, "limit": args.limit}
    print(json.dumps(api_request("/bgw-pro/market/v3/historical-coins", body), indent=2))


def cmd_rankings(args):
    body = {"name": args.name}
    print(json.dumps(api_request("/bgw-pro/market/v3/topRank/detail", body), indent=2))


def cmd_liquidity(args):
    body = {"chain": args.chain, "contract": args.contract}
    print(json.dumps(api_request("/bgw-pro/market/v3/poolList", body), indent=2))


def cmd_security(args):
    body = {
        "list": [{"chain": args.chain, "contract": args.contract}],
        "source": "bg"
    }
    print(json.dumps(api_request("/bgw-pro/market/v3/coin/security/audits", body), indent=2))


def cmd_swap_quote(args):
    body = {
        "fromChain": args.from_chain,
        "fromContract": args.from_contract,
        "toChain": args.to_chain or args.from_chain,
        "toContract": args.to_contract,
        "fromAmount": str(args.amount),
        "estimateGas": True,
    }
    if args.from_symbol:
        body["fromSymbol"] = args.from_symbol
    if args.to_symbol:
        body["toSymbol"] = args.to_symbol
    if args.from_address:
        body["fromAddress"] = args.from_address
    print(json.dumps(api_request("/bgw-pro/swapx/pro/quote", body), indent=2))


def cmd_swap_calldata(args):
    body = {
        "fromChain": args.from_chain,
        "fromContract": args.from_contract,
        "toChain": args.to_chain or args.from_chain,
        "toContract": args.to_contract,
        "fromAmount": str(args.amount),
        "fromAddress": args.from_address,
        "toAddress": args.to_address,
        "market": args.market,
    }
    if args.from_symbol:
        body["fromSymbol"] = args.from_symbol
    if args.to_symbol:
        body["toSymbol"] = args.to_symbol
    if args.slippage:
        body["slippage"] = args.slippage
    print(json.dumps(api_request("/bgw-pro/swapx/pro/swap", body), indent=2))


def cmd_swap_send(args):
    """Broadcast signed transactions via MEV-protected endpoint."""
    txs = []
    for tx_str in args.txs:
        parts = tx_str.split(":", 3)
        if len(parts) < 4:
            print(f"Error: each tx must be id:chain:from:rawTx, got: {tx_str}", file=sys.stderr)
            sys.exit(1)
        tx = {"id": parts[0], "chain": parts[1], "from": parts[2], "rawTx": parts[3]}
        txs.append(tx)
    body = {"chain": args.chain, "txs": txs}
    print(json.dumps(api_request("/bgw-pro/swapx/pro/send", body), indent=2))


def main():
    parser = argparse.ArgumentParser(description="Bitget Wallet ToB API Client")
    sub = parser.add_subparsers(dest="command", required=True)

    # token-info
    p = sub.add_parser("token-info", help="Get token info")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=cmd_token_info)

    # token-price
    p = sub.add_parser("token-price", help="Get token price")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=cmd_token_price)

    # batch-token-info
    p = sub.add_parser("batch-token-info", help="Batch get token info")
    p.add_argument("--tokens", required=True, help="chain:contract,chain:contract,...")
    p.set_defaults(func=cmd_batch_token_info)

    # kline
    p = sub.add_parser("kline", help="Get K-line data")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.add_argument("--period", default="1h", help="1s,1m,5m,15m,30m,1h,4h,1d,1w")
    p.add_argument("--size", type=int, default=24, help="Max 1440")
    p.set_defaults(func=cmd_kline)

    # tx-info
    p = sub.add_parser("tx-info", help="Get token transaction info")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=cmd_tx_info)

    # batch-tx-info
    p = sub.add_parser("batch-tx-info", help="Batch get token transaction info")
    p.add_argument("--tokens", required=True, help="Comma-separated chain:contract pairs")
    p.set_defaults(func=cmd_batch_tx_info)

    # historical-coins
    p = sub.add_parser("historical-coins", help="Get token list by timestamp")
    p.add_argument("--create-time", required=True, help="Timestamp (e.g. 2025-06-17 06:55:28)")
    p.add_argument("--limit", type=int, default=10, help="Number of records (default 10)")
    p.set_defaults(func=cmd_historical_coins)

    # rankings
    p = sub.add_parser("rankings", help="Get token rankings")
    p.add_argument("--name", required=True, help="topGainers or topLosers")
    p.set_defaults(func=cmd_rankings)

    # liquidity
    p = sub.add_parser("liquidity", help="Get token liquidity info")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=cmd_liquidity)

    # security
    p = sub.add_parser("security", help="Security audit")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=cmd_security)

    # swap-quote
    p = sub.add_parser("swap-quote", help="Get swap quote")
    p.add_argument("--from-chain", required=True)
    p.add_argument("--from-contract", required=True)
    p.add_argument("--to-chain")
    p.add_argument("--to-contract", required=True)
    p.add_argument("--amount", required=True)
    p.add_argument("--from-symbol")
    p.add_argument("--to-symbol")
    p.add_argument("--from-address")
    p.set_defaults(func=cmd_swap_quote)

    # swap-calldata
    p = sub.add_parser("swap-calldata", help="Get swap calldata")
    p.add_argument("--from-chain", required=True)
    p.add_argument("--from-contract", required=True)
    p.add_argument("--to-chain")
    p.add_argument("--to-contract", required=True)
    p.add_argument("--amount", required=True)
    p.add_argument("--from-address", required=True)
    p.add_argument("--to-address", required=True)
    p.add_argument("--market", required=True)
    p.add_argument("--from-symbol")
    p.add_argument("--to-symbol")
    p.add_argument("--slippage", type=float)
    p.set_defaults(func=cmd_swap_calldata)

    # swap-send
    p = sub.add_parser("swap-send", help="Broadcast signed transactions (MEV-protected)")
    p.add_argument("--chain", required=True, help="Chain name (e.g. sol, eth, bnb)")
    p.add_argument("--txs", nargs="+", required=True, help="Transactions as id:chain:from:rawTx")
    p.set_defaults(func=cmd_swap_send)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
