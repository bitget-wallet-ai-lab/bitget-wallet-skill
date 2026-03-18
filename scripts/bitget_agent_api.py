#!/usr/bin/env python3
"""
Bitget Wallet Agent API client — new swap flow (no apiKey).

Flow: quote → confirm → makeOrder → send → getOrderDetails.
Signing via order_sign.py with private key derived from mnemonic in secure storage (derive on-the-fly, discard after signing).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from typing import List, Optional

import requests

BASE_URL = "https://copenapi.bgwapi.io"


def _make_sign(method: str, path: str, body_str: str, ts: str) -> str:
    """
    BKHmacAuth signature: SHA256(Method + Path + Body + Timestamp).
    Returns '0x' + lowercase hex digest.
    """
    message = method + path + body_str + ts
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()
    return "0x" + digest


def _request(path: str, body: dict) -> dict:
    """Send POST request with BKHmacAuth signing."""
    url = BASE_URL.rstrip("/") + path
    ts = str(int(time.time() * 1000))
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    sign = _make_sign("POST", path, body_str, ts)
    headers = {
        "Content-Type": "application/json",
        "channel": "toc_agent",
        "brand": "toc_agent",
        "clientversion": "10.0.0",
        "language": "en",
        "token": "toc_agent",
        "X-SIGN": sign,
        "X-TIMESTAMP": ts,
    }
    try:
        resp = requests.post(url, data=body_str, headers=headers, timeout=30)
        if resp.status_code != 200:
            return {"status": -1, "error_code": resp.status_code, "msg": resp.text[:500]}
        return resp.json()
    except Exception as e:
        return {"status": -1, "error_code": -1, "msg": str(e)}


def _request_get(path_with_query: str) -> dict:
    """Send GET request with BKHmacAuth signing. path_with_query includes query string (e.g. /path?ticker=NVDAon)."""
    url = BASE_URL.rstrip("/") + path_with_query
    ts = str(int(time.time() * 1000))
    body_str = ""
    sign = _make_sign("GET", path_with_query, body_str, ts)
    headers = {
        "Content-Type": "application/json",
        "channel": "toc_agent",
        "brand": "toc_agent",
        "clientversion": "10.0.0",
        "language": "en",
        "token": "toc_agent",
        "X-SIGN": sign,
        "X-TIMESTAMP": ts,
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return {"status": -1, "error_code": resp.status_code, "msg": resp.text[:500]}
        return resp.json()
    except Exception as e:
        return {"status": -1, "error_code": -1, "msg": str(e)}


# ---------------------------------------------------------------------------
# 1. First quote /swapx/quote
# ---------------------------------------------------------------------------

def quote(
    from_address: str,
    from_chain: str,
    from_symbol: str,
    from_contract: str,
    from_amount: str,
    to_chain: str,
    to_symbol: str,
    to_contract: str = "",
    to_address: Optional[str] = None,
    tab_type: str = "swap",
    slippage: str = "",
    request_id: Optional[str] = None,
) -> dict:
    """
    First quote; get multi-market quotes.
    Pass empty string for to_contract when the output is the native token.
    """
    body = {
        "fromAddress": from_address,
        "fromChain": from_chain,
        "fromSymbol": from_symbol,
        "fromContract": from_contract,
        "fromAmount": from_amount,
        "toChain": to_chain,
        "toSymbol": to_symbol,
        "toContract": to_contract or "",
        "tab_type": tab_type,
        "publicKey": "",
        "slippage": slippage,
        "toAddress": to_address or from_address,
        "requestId": request_id or str(int(time.time() * 1000)),
    }
    return _request("/swap-go/swapx/quote", body)


# ---------------------------------------------------------------------------
# 2. Second quote /swapx/confirm
# ---------------------------------------------------------------------------

def confirm(
    from_chain: str,
    from_symbol: str,
    from_contract: str,
    from_amount: str,
    from_address: str,
    to_chain: str,
    to_symbol: str,
    to_contract: str,
    to_address: str,
    market: str,
    protocol: str,
    slippage: str,
    gas_level: str = "average",
    features: Optional[List[str]] = None,
    last_out_amount: str = "",
    recommend_slippage: str = "",
    mev_protection: Optional[dict] = None,
    user_actions: Optional[dict] = None,
) -> dict:
    """
    Second quote; get final quote and orderId for one market.
    market/protocol from quote response data.quoteResults[].market.id / .protocol.
    features: single-element array. Selection logic:
      - ["user_gas"] — user pays gas in native token. Use when native balance is sufficient for gas.
      - ["no_gas"] — gasless mode, gas deducted from fromToken. Use when native balance is insufficient.
      Agent must check native token balance (via get-processed-balance) and choose accordingly.
      Default: ["user_gas"] if not specified.
    """
    body = {
        "fromChain": from_chain,
        "fromSymbol": from_symbol,
        "fromContract": from_contract,
        "fromAmount": from_amount,
        "fromAddress": from_address,
        "toChain": to_chain,
        "toSymbol": to_symbol,
        "toContract": to_contract or "",
        "toAddress": to_address,
        "market": market,
        "slippage": slippage,
        "gasLevel": gas_level,
        "features": features or ["user_gas"],
        "protocol": protocol,
        "recommendSlippage": recommend_slippage or slippage,
        "lastOutAmount": last_out_amount,
    }
    if mev_protection is not None:
        body["mevProtection"] = mev_protection
    else:
        body["mevProtection"] = {
            "chain": from_chain,
            "mevFee": "0",
            "amountMin": from_amount,
            "mevTarget": True,
            "mode": "smart",
        }
    if user_actions is not None:
        body["userActions"] = user_actions
    return _request("/swap-go/swapx/confirm", body)


# ---------------------------------------------------------------------------
# 3. Create order /swapx/makeOrder
# ---------------------------------------------------------------------------

def make_order(
    order_id: str,
    from_chain: str,
    from_contract: str,
    from_symbol: str,
    from_address: str,
    to_chain: str,
    to_contract: str,
    to_symbol: str,
    to_address: str,
    from_amount: str,
    slippage: str,
    market: str,
    protocol: str,
    source: str = "agent",
) -> dict:
    """
    Create order; returns unsigned data.txs.
    Sign with scripts/order_sign.py (supports deriveTransaction format).
    """
    body = {
        "orderId": order_id,
        "fromChain": from_chain,
        "fromContract": from_contract,
        "fromSymbol": from_symbol,
        "fromAddress": from_address,
        "toChain": to_chain,
        "toContract": to_contract or "",
        "toSymbol": to_symbol,
        "toAddress": to_address,
        "fromAmount": from_amount,
        "slippage": slippage,
        "market": market,
        "protocol": protocol,
        "source": source,
    }
    return _request("/swap-go/swapx/makeOrder", body)


# ---------------------------------------------------------------------------
# 4. Send order (with signatures) — path /swapx/send
# ---------------------------------------------------------------------------

def send(order_id: str, txs: List[dict]) -> dict:
    """
    Submit signed order. txs is makeOrder data.txs with each txs[i].sig filled.
    Sign with order_sign.py to get signature array, then set txs[i].sig.
    """
    body = {"orderId": order_id, "txs": txs}
    return _request("/swap-go/swapx/send", body)


# ---------------------------------------------------------------------------
# 5. Query order /swapx/getOrderDetails
# ---------------------------------------------------------------------------


def get_order_details(order_id: str, timestamp: Optional[str] = None) -> dict:
    """Query order details and result. timestamp is optional (ms as string)."""
    body = {
        "orderId": order_id,
        # "timestamp": timestamp or str(int(time.time() * 1000)),
    }
    return _request("/swap-go/swapx/getOrderDetails", body)


# ---------------------------------------------------------------------------
# 6. Get token list /swapx/getTokenList
# ---------------------------------------------------------------------------

def get_token_list(chain: str, is_all_network: int = 1) -> dict:
    """Get popular token list for a chain. chain e.g. bnb, eth; isAllNetWork fixed 1."""
    body = {"chain": chain, "isAllNetWork": is_all_network}
    return _request("/swap-go/swapx/getTokenList", body)


# ---------------------------------------------------------------------------
# 7. Check swap token risk /swapx/checkSwapToken
# ---------------------------------------------------------------------------

def check_swap_token(list_: List[dict]) -> dict:
    """
    Check fromToken and toToken for risks before swap. list_: list of {chain, contract, symbol}.
    contract empty string for native token. Returns data.list[].checkTokenList; empty = no risk.
    If any item has waringType "forbidden-buy", that token must not be used as swap target (toToken).
    """
    body = {"list": list_}
    return _request("/swap-go/swapx/checkSwapToken", body)


# ---------------------------------------------------------------------------
# 8. Get processed balance /swapx/getProcessedBalance
# ---------------------------------------------------------------------------

def get_processed_balance(items: List[dict]) -> dict:
    """
    Batch get on-chain balance for address(es). items: list of {chain, address, contract: ["" for native, or contract addrs]}.
    """
    body = {"list": items}
    return _request("/swap-go/swapx/getProcessedBalance", body)


# ---------------------------------------------------------------------------
# 9. Batch balance + price /user/wallet/batchV2
# ---------------------------------------------------------------------------

def batch_v2(
    list_: List[dict],
    nocache: bool = True,
    appoint_currency: str = "usd",
    noreport: bool = True,
) -> dict:
    """
    Batch get on-chain balance and token price for address(es).
    list_: list of {chain, address, contract: ["" for native, or contract addrs]}.
    Returns data as array of {chain, address, token_protocol, list: { "": {balance, price, ...}, "0x...": {...} } }.
    """
    body = {
        "list": list_,
        "nocache": nocache,
        "appointCurrency": appoint_currency,
        "noreport": noreport,
    }
    return _request("/user/wallet/batchV2", body)


# ---------------------------------------------------------------------------
# 10. Search tokens by keyword or contract /market/v2/search/tokens
# ---------------------------------------------------------------------------

def search_tokens(keyword: str, chain: Optional[str] = None) -> dict:
    """
    Search on-chain tokens by keyword or full contract address.
    chain: optional; pass to restrict search to a specific chain (e.g. bnb, eth).
    Returns data.list (array of token info: name, symbol, chain, contract, price, etc.), data.showMore, data.isContract.
    """
    body = {"keyword": keyword}
    if chain:
        body["chain"] = chain
    return _request("/market/v2/search/tokens", body)


# ---------------------------------------------------------------------------
# Market data — token info, price, kline, tx info, rankings, liquidity, security
# Paths follow ToB market API; agent API uses same backend with token auth.
# ---------------------------------------------------------------------------

def token_info(chain: str, contract: str) -> dict:
    """Get single token base info (name, symbol, price, etc.) via batchGetBaseInfo with one item."""
    body = {"list": [{"chain": chain, "contract": contract}]}
    result = _request("/market/v3/coin/batchGetBaseInfo", body)
    if result.get("data") and result["data"].get("list") and len(result["data"]["list"]) > 0:
        return {"data": result["data"]["list"][0], "status": result.get("status", 0)}
    return result


def token_price(chain: str, contract: str) -> dict:
    """Get single token price; returns simplified { symbol, name, price, chain, contract }."""
    result = token_info(chain, contract)
    if result.get("data"):
        d = result["data"]
        return {
            "symbol": d.get("symbol"),
            "name": d.get("name"),
            "price": d.get("price"),
            "chain": chain,
            "contract": contract,
        }
    return result


def batch_token_info(tokens: List[dict]) -> dict:
    """Batch get token base info. tokens: list of { chain, contract }."""
    body = {"list": tokens}
    return _request("/market/v3/coin/batchGetBaseInfo", body)


def kline(chain: str, contract: str, period: str = "1h", size: int = 24) -> dict:
    """Get K-line (OHLC) data for a token. period: 1s,1m,5m,15m,30m,1h,4h,1d,1w; size max 1440."""
    body = {"chain": chain, "contract": contract, "period": period, "size": size}
    return _request("/market/v3/coin/getKline", body)


def tx_info(chain: str, contract: str) -> dict:
    """Get recent transaction stats for a single token (buy/sell volume, counts)."""
    body = {"chain": chain, "contract": contract}
    return _request("/market/v3/coin/getTxInfo", body)


def batch_tx_info(tokens: List[dict]) -> dict:
    """Batch get recent transaction stats for multiple tokens. tokens: list of { chain, contract }."""
    body = {"list": tokens}
    return _request("/market/v3/coin/batchGetTxInfo", body)


def historical_coins(create_time: str, limit: int = 10) -> dict:
    """Get recently issued tokens by create time (datetime string YYYY-MM-DD HH:MM:SS). Paginate with lastTime."""
    body = {"createTime": create_time, "limit": limit}
    return _request("/market/v3/historical-coins", body)


def rankings(name: str) -> dict:
    """Get token rankings. name: e.g. topGainers, topLosers, or Hotpicks."""
    body = {"name": name}
    return _request("/market/v3/topRank/detail", body)


def liquidity(chain: str, contract: str) -> dict:
    """Get liquidity pool info for a token."""
    body = {"chain": chain, "contract": contract}
    return _request("/market/v3/poolList", body)


def security(chain: str, contract: str, source: str = "bg") -> dict:
    """Security audit for a token. Check highRisk, riskCount, buyTax/sellTax, etc. See docs/market-data.md."""
    body = {"list": [{"chain": chain, "contract": contract}], "source": source}
    return _request("/market/v3/coin/security/audits", body)


# ---------------------------------------------------------------------------
# RWA (Real World Asset) stock trading APIs
# ---------------------------------------------------------------------------

def rwa_get_user_ticker_selector(
    chain: str,
    user_address: Optional[str] = None,
    key_word: Optional[str] = None,
) -> dict:
    """
    Query or search RWA stock tickers supported by the market; optionally with user address to include balance.
    chain: required, currently only bnb and eth supported.
    user_address: optional; if provided, response includes balance and balance_usd per ticker.
    key_word: optional search keyword (name or stock contract address).
    Returns data.list with ticker, name, icon, chain, contract, latest_price, balance, etc.
    """
    body = {"chain": chain}
    if user_address:
        body["user_address"] = user_address
    if key_word:
        body["key_word"] = key_word
    return _request("/market/v2/rwa/GetUserTickerSelector", body)


def rwa_get_config(address_list: List[dict]) -> dict:
    """
    Get RWA trading config: stablecoins (fromTokenList / toTokenList) for buying/selling RWA stocks,
    slippage, amount limits, gasInfoList, etc.
    address_list: list of { chain, address } for bnb, eth, sol.
    """
    body = {"addressList": address_list}
    return _request("/swap-go/rwa/getConfig", body)


def rwa_stock_info(ticker: str) -> dict:
    """
    Get RWA stock info by ticker (GET). Returns market status, trading amount limits (tx_minimum_usd,
    tx_maximum_usd, tx_minimum_sell_usd, tx_maximum_sell_usd), chain_assets, description, etc.
    """
    path = f"/market/v2/rwa/StockInfo?ticker={requests.utils.quote(ticker)}"
    return _request_get(path)


def rwa_stock_order_price(
    ticker: str,
    chain: str,
    side: str,
    tx_coin_contract: str,
    user_address: str,
) -> dict:
    """
    Get display buy/sell price for an RWA stock (for pre-trade display, not actual quote).
    side: "buy" or "sell". tx_coin_contract: stablecoin contract from rwaGetConfig (fromTokenList/toTokenList).
    Returns data.order_price, data.price_source.
    """
    body = {
        "ticker": ticker,
        "chain": chain,
        "side": side,
        "tx_coin_contract": tx_coin_contract,
        "user_address": user_address,
    }
    return _request("/market/v2/rwa/StockOrderPrice", body)


def rwa_kline(chain: str, contract: str, period: str = "1d", size: Optional[int] = None) -> dict:
    """
    Get K-line data for an RWA stock. chain should be "rwa"; contract is the ticker (e.g. NVDAon).
    period: e.g. 1d, 1h. size: optional limit.
    """
    body = {"chain": chain, "contract": contract, "period": period}
    if size is not None:
        body["size"] = size
    return _request("/market/v2/coin/Kline", body)


def rwa_get_my_holdings(user_address: str) -> dict:
    """
    Get user's RWA stock holdings. Returns data.balance_list with ticker, balance, chain_asset, etc.
    """
    body = {"user_address": user_address}
    return _request("/market/v2/rwa/GetMyHoldings", body)


# ---------------------------------------------------------------------------
# Quote response simplification (for Agent; see api/quote.md "simplified response example")
# ---------------------------------------------------------------------------

def _pick(obj: Optional[dict], *keys: str) -> Optional[dict]:
    """Return a dict with only the given keys present in obj."""
    if obj is None:
        return None
    return {k: obj[k] for k in keys if k in obj}


def simplify_quote_response(resp: dict) -> dict:
    """
    Trim quote API response to the simplified set of fields for Agent consumption.
    Keeps: status, error_code, data (fromAddress, toAddress, fromAmount, quoteResults, requestId),
    and per quoteResult: market (id, label, icon, protocol), features, recommendFeatures,
    outAmount, minAmount, slippageInfo.recommendSlippage, gasFees (gasFeeAmountInUsd, gasTotalAmount),
    tips, estimatedTradeTimeCost, txFeeInfo (feePercent, txFeeAmountInUsd); plus msg, title, timestamp, trace.
    """
    out = {
        "status": resp.get("status"),
        "error_code": resp.get("error_code"),
        "data": None,
        "msg": resp.get("msg"),
        "title": resp.get("title"),
        "timestamp": resp.get("timestamp"),
        "trace": resp.get("trace"),
    }
    data = resp.get("data")
    if data is None:
        return out
    results = []
    for q in data.get("quoteResults") or []:
        results.append({
            "market": _pick(q.get("market"), "id", "label", "icon", "protocol"),
            "features": q.get("features"),
            "recommendFeatures": q.get("recommendFeatures"),
            "outAmount": q.get("outAmount"),
            "minAmount": q.get("minAmount"),
            "slippageInfo": _pick(q.get("slippageInfo") or {}, "recommendSlippage"),
            "gasFees": _pick(q.get("gasFees") or {}, "gasFeeAmountInUsd", "gasTotalAmount"),
            "tips": q.get("tips"),
            "estimatedTradeTimeCost": q.get("estimatedTradeTimeCost"),
            "txFeeInfo": _pick(q.get("txFeeInfo") or {}, "feePercent", "txFeeAmountInUsd"),
        })
    out["data"] = {
        "fromAddress": data.get("fromAddress"),
        "toAddress": data.get("toAddress"),
        "fromAmount": data.get("fromAmount"),
        "quoteResults": results,
        "requestId": data.get("requestId"),
    }
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_quote(args):
    out = quote(
        from_address=args.from_address,
        from_chain=args.from_chain,
        from_symbol=args.from_symbol,
        from_contract=args.from_contract,
        from_amount=args.from_amount,
        to_chain=args.to_chain,
        to_symbol=args.to_symbol,
        to_contract=args.to_contract or "",
        to_address=args.to_address or args.from_address,
        slippage=args.slippage or "",
    )
    out = simplify_quote_response(out)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_confirm(args):
    out = confirm(
        from_chain=args.from_chain,
        from_symbol=args.from_symbol,
        from_contract=args.from_contract,
        from_amount=args.from_amount,
        from_address=args.from_address,
        to_chain=args.to_chain,
        to_symbol=args.to_symbol,
        to_contract=args.to_contract or "",
        to_address=args.to_address,
        market=args.market,
        protocol=args.protocol,
        slippage=args.slippage,
        gas_level=args.gas_level or "average",
        features=args.features.split(",") if args.features else ["user_gas"],
        last_out_amount=args.last_out_amount or "",
        recommend_slippage=args.recommend_slippage or args.slippage,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_make_order(args):
    out = make_order(
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
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_send(args):
    # Read { orderId, txs } from stdin or file; txs already have sig filled
    if args.json_stdin:
        payload = json.load(sys.stdin)
    else:
        with open(args.json_file, encoding="utf-8") as f:
            payload = json.load(f)
    out = send(order_id=payload["orderId"], txs=payload["txs"])
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _strip_tips_when_success(order_details_response: dict) -> dict:
    """When data.details.status is 'success', remove tips so it has no effect on the agent."""
    if order_details_response.get("error_code") != 0:
        return order_details_response
    data = order_details_response.get("data")
    if not data or not isinstance(data, dict):
        return order_details_response
    details = data.get("details")
    if not details or not isinstance(details, dict):
        return order_details_response
    if details.get("status") == "success":
        details.pop("tips", None)
    return order_details_response


def _cmd_get_order_details(args):
    out = get_order_details(
        order_id=args.order_id,
        timestamp=args.timestamp,
    )
    out = _strip_tips_when_success(out)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_get_token_list(args):
    out = get_token_list(chain=args.chain, is_all_network=getattr(args, "is_all_network", 1))
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_check_swap_token(args):
    if args.json_stdin:
        payload = json.load(sys.stdin)
        list_ = payload.get("list", payload if isinstance(payload, list) else [])
    else:
        for name in ("from_chain", "from_symbol", "to_chain", "to_symbol"):
            if not getattr(args, name, None):
                print(f"Error: when not using --json-stdin, --from-chain, --from-symbol, --to-chain, --to-symbol are required", file=sys.stderr)
                sys.exit(1)
        list_ = [
            {"chain": args.from_chain, "contract": args.from_contract or "", "symbol": args.from_symbol},
            {"chain": args.to_chain, "contract": args.to_contract or "", "symbol": args.to_symbol},
        ]
    out = check_swap_token(list_)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_get_processed_balance(args):
    if args.json_stdin:
        payload = json.load(sys.stdin)
        items = payload.get("list", payload) if isinstance(payload, dict) and "list" in payload else (payload if isinstance(payload, list) else [])
        if not items:
            print("Error: stdin JSON must contain 'list' array or be an array of items", file=sys.stderr)
            sys.exit(1)
    else:
        chain = getattr(args, "chain", None)
        address = getattr(args, "address", None)
        if not chain or not address:
            print("Error: when not using --json-stdin, both --chain and --address are required", file=sys.stderr)
            sys.exit(1)
        contracts = []
        if getattr(args, "contract", None):
            for c in args.contract:
                contracts.extend(s.strip() for s in str(c).split(",") if s.strip())
        if "" not in contracts and not getattr(args, "no_include_native", False):
            contracts.insert(0, "")
        if not contracts:
            contracts = [""]
        items = [{"chain": chain, "address": address, "contract": contracts}]
    out = get_processed_balance(items)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_batch_v2(args):
    """Batch balance + price: same list format as get-processed-balance."""
    if args.json_stdin:
        payload = json.load(sys.stdin)
        list_ = payload.get("list", payload if isinstance(payload, list) else [])
    else:
        chain = getattr(args, "chain", None)
        address = getattr(args, "address", None)
        if not chain or not address:
            print("Error: when not using --json-stdin, both --chain and --address are required", file=sys.stderr)
            sys.exit(1)
        contracts = []
        if getattr(args, "contract", None):
            for c in args.contract:
                contracts.extend(s.strip() for s in str(c).split(",") if s.strip())
        if "" not in contracts and not getattr(args, "no_include_native", False):
            contracts.insert(0, "")
        if not contracts:
            contracts = [""]
        list_ = [{"chain": chain, "address": address, "contract": contracts}]
    out = batch_v2(list_)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_search_tokens(args):
    out = search_tokens(keyword=args.keyword, chain=getattr(args, "chain", None))
    print(json.dumps(out, indent=2, ensure_ascii=False))


# ---- Market data CLI ----

def _cmd_token_info(args):
    out = token_info(chain=args.chain, contract=args.contract)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_token_price(args):
    out = token_price(chain=args.chain, contract=args.contract)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_batch_token_info(args):
    tokens = []
    for item in args.tokens.split(","):
        part = item.strip()
        if ":" in part:
            chain, contract = part.split(":", 1)
            tokens.append({"chain": chain.strip(), "contract": contract.strip()})
        else:
            tokens.append({"chain": "", "contract": part})
    out = batch_token_info(tokens)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_kline(args):
    out = kline(
        chain=args.chain,
        contract=args.contract,
        period=getattr(args, "period", "1h"),
        size=getattr(args, "size", 24),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_tx_info(args):
    out = tx_info(chain=args.chain, contract=args.contract)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_batch_tx_info(args):
    tokens = []
    for item in args.tokens.split(","):
        part = item.strip()
        if ":" in part:
            chain, contract = part.split(":", 1)
            tokens.append({"chain": chain.strip(), "contract": contract.strip()})
        else:
            tokens.append({"chain": "", "contract": part})
    out = batch_tx_info(tokens)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_historical_coins(args):
    out = historical_coins(
        create_time=args.create_time,
        limit=getattr(args, "limit", 10),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_rankings(args):
    out = rankings(name=args.name)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_liquidity(args):
    out = liquidity(chain=args.chain, contract=args.contract)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_security(args):
    out = security(chain=args.chain, contract=args.contract)
    print(json.dumps(out, indent=2, ensure_ascii=False))


# ---- RWA CLI ----

def _cmd_rwa_get_user_ticker_selector(args):
    out = rwa_get_user_ticker_selector(
        chain=args.chain,
        user_address=getattr(args, "user_address", None),
        key_word=getattr(args, "key_word", None),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_rwa_get_config(args):
    if args.json_stdin:
        payload = json.load(sys.stdin)
        address_list = payload.get("addressList", payload.get("address_list", payload))
        if isinstance(address_list, dict):
            address_list = [address_list]
    else:
        address_list = []
        for item in (args.address_list or "").split(";"):
            item = item.strip()
            if not item:
                continue
            parts = item.split(",")
            if len(parts) >= 2:
                address_list.append({"chain": parts[0].strip(), "address": parts[1].strip()})
    if not address_list:
        print("Error: --address-list or --json-stdin with addressList required", file=sys.stderr)
        sys.exit(1)
    out = rwa_get_config(address_list)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_rwa_stock_info(args):
    out = rwa_stock_info(ticker=args.ticker)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_rwa_stock_order_price(args):
    out = rwa_stock_order_price(
        ticker=args.ticker,
        chain=args.chain,
        side=args.side,
        tx_coin_contract=args.tx_coin_contract,
        user_address=args.user_address,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_rwa_kline(args):
    out = rwa_kline(
        chain=args.chain,
        contract=args.contract,
        period=getattr(args, "period", "1d"),
        size=getattr(args, "size", None),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_rwa_get_my_holdings(args):
    out = rwa_get_my_holdings(user_address=args.user_address)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Bitget Wallet Agent API (new swap flow, no apiKey)")
    sub = parser.add_subparsers(dest="command", required=True)

    # quote
    p = sub.add_parser("quote", help="First quote /swapx/quote")
    p.add_argument("--from-address", required=True)
    p.add_argument("--from-chain", required=True)
    p.add_argument("--from-symbol", required=True)
    p.add_argument("--from-contract", required=True)
    p.add_argument("--from-amount", required=True)
    p.add_argument("--to-chain", required=True)
    p.add_argument("--to-symbol", required=True)
    p.add_argument("--to-contract", default="", help="Empty for native token")
    p.add_argument("--to-address", default=None)
    p.add_argument("--slippage", default="")
    p.set_defaults(func=_cmd_quote)

    # confirm
    p = sub.add_parser("confirm", help="Second quote /swapx/confirm")
    p.add_argument("--from-chain", required=True)
    p.add_argument("--from-symbol", required=True)
    p.add_argument("--from-contract", required=True)
    p.add_argument("--from-amount", required=True)
    p.add_argument("--from-address", required=True)
    p.add_argument("--to-chain", required=True)
    p.add_argument("--to-symbol", required=True)
    p.add_argument("--to-contract", default="")
    p.add_argument("--to-address", required=True)
    p.add_argument("--market", required=True)
    p.add_argument("--protocol", required=True)
    p.add_argument("--slippage", required=True)
    p.add_argument("--gas-level", default="average")
    p.add_argument("--features", default=None, help="Comma-separated, e.g. user_gas or no_gas")
    p.add_argument("--last-out-amount", default="")
    p.add_argument("--recommend-slippage", default="")
    p.set_defaults(func=_cmd_confirm)

    # makeOrder
    p = sub.add_parser("make-order", help="Create order /swapx/makeOrder")
    p.add_argument("--order-id", required=True)
    p.add_argument("--from-chain", required=True)
    p.add_argument("--from-contract", required=True)
    p.add_argument("--from-symbol", required=True)
    p.add_argument("--from-address", required=True)
    p.add_argument("--to-chain", required=True)
    p.add_argument("--to-contract", default="")
    p.add_argument("--to-symbol", required=True)
    p.add_argument("--to-address", required=True)
    p.add_argument("--from-amount", required=True)
    p.add_argument("--slippage", required=True)
    p.add_argument("--market", required=True)
    p.add_argument("--protocol", required=True)
    p.set_defaults(func=_cmd_make_order)

    # send
    p = sub.add_parser("send", help="Send order (body: orderId + signed txs)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--json-stdin", action="store_true", help="Read JSON from stdin")
    g.add_argument("--json-file", help="Read JSON from file")
    p.set_defaults(func=_cmd_send)

    # getOrderDetails
    p = sub.add_parser("get-order-details", help="Query order /swapx/getOrderDetails")
    p.add_argument("--order-id", required=True)
    p.add_argument("--timestamp", default=None)
    p.set_defaults(func=_cmd_get_order_details)

    # checkSwapToken: --json-stdin with {"list": [{chain, contract, symbol}, ...]} or --from-* and --to-*
    p = sub.add_parser("check-swap-token", help="Check from/to tokens for risk before swap /swapx/checkSwapToken")
    p.add_argument("--json-stdin", action="store_true", help="Read body {list: [{chain, contract, symbol}, ...]} from stdin")
    p.add_argument("--from-chain", help="From token chain (when not using --json-stdin)")
    p.add_argument("--from-contract", default="", help="From token contract, empty for native")
    p.add_argument("--from-symbol", help="From token symbol")
    p.add_argument("--to-chain", help="To token chain (when not using --json-stdin)")
    p.add_argument("--to-contract", default="", help="To token contract, empty for native")
    p.add_argument("--to-symbol", help="To token symbol")
    p.set_defaults(func=_cmd_check_swap_token)

    # getTokenList
    p = sub.add_parser("get-token-list", help="Get popular token list for chain /swapx/getTokenList")
    p.add_argument("--chain", required=True, help="Chain code e.g. bnb, eth")
    p.add_argument("--is-all-network", type=int, default=1, dest="is_all_network")
    p.set_defaults(func=_cmd_get_token_list)

    # getProcessedBalance: either --json-stdin (full body) or --chain + --address (single query)
    p = sub.add_parser("get-processed-balance", help="Get address balance /swapx/getProcessedBalance")
    p.add_argument("--json-stdin", action="store_true", help="Read body {list: [{chain, address, contract}]} from stdin; then --chain/--address are ignored")
    p.add_argument("--chain", help="Chain code (required when not using --json-stdin)")
    p.add_argument("--address", help="Wallet address (required when not using --json-stdin)")
    p.add_argument("--contract", action="append", default=[], help="Token contract(s); empty for native. Repeat or comma-separated. Used only when not --json-stdin.")
    p.add_argument("--no-include-native", action="store_true", dest="no_include_native", help="Do not add native token to contract list")
    p.set_defaults(func=_cmd_get_processed_balance)

    # batchV2: balance + token price per address (same list format as get-processed-balance)
    p = sub.add_parser("batch-v2", help="Batch balance and token price /user/wallet/batchV2")
    p.add_argument("--json-stdin", action="store_true", help="Read body {list: [{chain, address, contract}]} from stdin")
    p.add_argument("--chain", help="Chain code (required when not using --json-stdin)")
    p.add_argument("--address", help="Wallet address (required when not using --json-stdin)")
    p.add_argument("--contract", action="append", default=[], help="Token contract(s); empty for native. Repeat or comma-separated.")
    p.add_argument("--no-include-native", action="store_true", dest="no_include_native", help="Do not add native token to contract list")
    p.set_defaults(func=_cmd_batch_v2)

    # searchTokens: search by keyword or contract address; optional chain to restrict to one chain
    p = sub.add_parser("search-tokens", help="Search tokens by keyword or contract /market/v2/search/tokens")
    p.add_argument("--keyword", required=True, help="Keyword or full contract address")
    p.add_argument("--chain", default=None, help="Optional: restrict search to this chain (e.g. bnb, eth)")
    p.set_defaults(func=_cmd_search_tokens)

    # ---- Market data ----
    p = sub.add_parser("token-info", help="[Market] Get single token base info")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=_cmd_token_info)

    p = sub.add_parser("token-price", help="[Market] Get single token price")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=_cmd_token_price)

    p = sub.add_parser("batch-token-info", help="[Market] Batch get token info (chain:contract,chain:contract,...)")
    p.add_argument("--tokens", required=True, help="Comma-separated chain:contract pairs")
    p.set_defaults(func=_cmd_batch_token_info)

    p = sub.add_parser("kline", help="[Market] Get K-line data for a token")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.add_argument("--period", default="1h", help="1s,1m,5m,15m,30m,1h,4h,1d,1w")
    p.add_argument("--size", type=int, default=24, help="Max 1440")
    p.set_defaults(func=_cmd_kline)

    p = sub.add_parser("tx-info", help="[Market] Get recent tx stats for a token")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=_cmd_tx_info)

    p = sub.add_parser("batch-tx-info", help="[Market] Batch get recent tx stats (chain:contract,...)")
    p.add_argument("--tokens", required=True, help="Comma-separated chain:contract pairs")
    p.set_defaults(func=_cmd_batch_tx_info)

    p = sub.add_parser("historical-coins", help="[Market] Get recently issued tokens by time")
    p.add_argument("--create-time", required=True, dest="create_time", help="Datetime YYYY-MM-DD HH:MM:SS")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=_cmd_historical_coins)

    p = sub.add_parser("rankings", help="[Market] Get token rankings (e.g. topGainers, topLosers, Hotpicks)")
    p.add_argument("--name", required=True, help="e.g. topGainers, topLosers, or Hotpicks")
    p.set_defaults(func=_cmd_rankings)

    p = sub.add_parser("liquidity", help="[Market] Get liquidity pool info for a token")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=_cmd_liquidity)

    p = sub.add_parser("security", help="[Market] Security audit for a token")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=_cmd_security)

    # ---- RWA ----
    p = sub.add_parser("rwa-get-user-ticker-selector", help="[RWA] Query/search RWA stock tickers; optional user_address for balance")
    p.add_argument("--chain", default="bnb", help="Chain (bnb or eth)")
    p.add_argument("--user-address", dest="user_address", default=None, help="Optional wallet address to include balance")
    p.add_argument("--key-word", dest="key_word", default=None, help="Optional search keyword (name or contract)")
    p.set_defaults(func=_cmd_rwa_get_user_ticker_selector)

    p = sub.add_parser("rwa-get-config", help="[RWA] Get RWA config (stablecoins, limits). addressList: chain,addr;chain,addr")
    p.add_argument("--address-list", dest="address_list", default="", help="Semicolon-separated chain,address (e.g. bnb,0x...;eth,0x...)")
    p.add_argument("--json-stdin", action="store_true", help="Read {addressList: [...]} from stdin")
    p.set_defaults(func=_cmd_rwa_get_config)

    p = sub.add_parser("rwa-stock-info", help="[RWA] Get RWA stock info by ticker (market status, limits)")
    p.add_argument("--ticker", required=True, help="RWA stock ticker (e.g. NVDAon)")
    p.set_defaults(func=_cmd_rwa_stock_info)

    p = sub.add_parser("rwa-stock-order-price", help="[RWA] Get display buy/sell price for RWA stock")
    p.add_argument("--ticker", required=True)
    p.add_argument("--chain", required=True)
    p.add_argument("--side", required=True, choices=["buy", "sell"])
    p.add_argument("--tx-coin-contract", dest="tx_coin_contract", required=True, help="Stablecoin contract from rwaGetConfig")
    p.add_argument("--user-address", dest="user_address", required=True)
    p.set_defaults(func=_cmd_rwa_stock_order_price)

    p = sub.add_parser("rwa-kline", help="[RWA] Get K-line for RWA stock (chain=rwa, contract=ticker)")
    p.add_argument("--chain", default="rwa", help="Use rwa for RWA kline")
    p.add_argument("--contract", required=True, help="RWA ticker e.g. NVDAon")
    p.add_argument("--period", default="1d", help="e.g. 1d, 1h")
    p.add_argument("--size", type=int, default=None, help="Optional limit")
    p.set_defaults(func=_cmd_rwa_kline)

    p = sub.add_parser("rwa-get-my-holdings", help="[RWA] Get user RWA stock holdings")
    p.add_argument("--user-address", dest="user_address", required=True)
    p.set_defaults(func=_cmd_rwa_get_my_holdings)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
