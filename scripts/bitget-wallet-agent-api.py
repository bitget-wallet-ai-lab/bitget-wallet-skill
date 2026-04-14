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
WALLET_ID = ""  # Set via --wallet-id flag for Social Login Wallet users


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
    token_val = WALLET_ID if WALLET_ID else "toc_agent"
    headers = {
        "Content-Type": "application/json",
        "channel": "toc_agent",
        "brand": "toc_agent",
        "clientversion": "10.0.0",
        "language": "en",
        "token": token_val,
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
    token_val = WALLET_ID if WALLET_ID else "toc_agent"
    headers = {
        "Content-Type": "application/json",
        "channel": "toc_agent",
        "brand": "toc_agent",
        "clientversion": "10.0.0",
        "language": "en",
        "token": token_val,
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
      Agent must check native token balance (via batch-v2) and choose accordingly.
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
# 8. Batch balance + price /user/wallet/batchV2 (primary balance API)
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


def search_tokens_v3(
    keyword: str,
    chain: Optional[str] = None,
    limit: int = 20,
    order_by: Optional[str] = None,
) -> dict:
    """
    Search tokens (v3). Supports ordering by market_cap etc.

    keyword: search term (name, symbol, or contract address)
    chain: optional chain filter (e.g. eth, sol, bnb)
    limit: max results (default 20)
    order_by: sort field (e.g. "market_cap")
    """
    body: dict = {"keyword": keyword, "limit": limit}
    if chain:
        body["chain"] = chain
    if order_by:
        body["order_by"] = order_by
    return _request("/market/v3/coin/search", body)


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


def alpha_gems() -> dict:
    """Get Alpha gems — AI-curated high-potential tokens with strategy labels."""
    return _request_get("/market/v3/alpha/gems")


def alpha_signals(
    chain: str = "all",
    page: int = 1,
    size: int = 20,
    offset: int = 0,
    filters: Optional[List[dict]] = None,
) -> dict:
    """Get Alpha signals — smart money/KOL/growth signals for tokens."""
    body: dict = {"chain": chain, "page": page, "size": size, "offset": offset}
    if filters is not None:
        body["filters"] = filters
    return _request("/market/v3/alpha/signals", body)


def alpha_hunter_find(chain: str, page: int = 1, limit: int = 20) -> dict:
    """Get Alpha hunter (smart money) address list with scoring factors."""
    body: dict = {"chain": chain, "page": page, "limit": limit}
    return _request("/market/v3/address/smart-money", body)


def alpha_hunter_detail(chain: str, address: str) -> dict:
    """Get Alpha hunter factor detail for a specific address."""
    body = {"chain": chain, "address": address}
    return _request("/market/v3/address/factor-detail", body)


def agent_alpha_tags() -> dict:
    """Get available Agent tag labels (static enum)."""
    return _request_get("/market/v3/address/agent-tags")


def agent_alpha_hunter_find(chain: str, tag: str, page: int = 1, limit: int = 20) -> dict:
    """Get addresses by Agent tag, sorted by score desc."""
    body: dict = {"chain": chain, "tag": tag, "page": page, "limit": limit}
    return _request("/market/v3/address/agent-tag-list", body)


def multi_agent_signal(chain: str = "all", page: int = 1, size: int = 20) -> dict:
    """Get Multi-Agent Signal list — tokens bought by Agent-tagged addresses (cross-strategy)."""
    body: dict = {"chain": chain, "page": page, "size": size}
    return _request("/market/v3/agent/signals", body)


def liquidity(chain: str, contract: str) -> dict:
    """Get liquidity pool info for a token."""
    body = {"chain": chain, "contract": contract}
    return _request("/market/v3/poolList", body)


def coin_market_info(chain: str, contract: str) -> dict:
    """
    Get token market info + pool list: price, market_cap, fdv, liquidity, turnover, holders, age,
    price changes (5m/1h/4h/24h), all trading pairs (pool_address, protocol, token0/1, liquidity),
    narratives description, narrative_tags.
    """
    body = {"chain": chain, "contract": contract}
    return _request("/market/v3/coin/getMarketInfo", body)


def coin_dev(
    chain: str,
    contract: str,
    limit: int = 30,
    is_migrated: Optional[bool] = None,
) -> dict:
    """
    Get token dev analysis: dev's historical projects with rug status, migration info.

    chain: chain code (e.g. sol, bnb)
    contract: token contract address
    limit: max tokens to return (default 30)
    is_migrated: null=all, true=migrated only, false=unmigrated only

    Response data fields:
      total_count, migrated_count, unmigrated_count,
      chain_coin_symbol, chain_coin_icon, chain_coin_price,
      tokens[]: list of dev's historical projects, each with:
        icon, chain, name, symbol, contract, market_cap, market_cap_chain_coin,
        liquidity, liquidity_chain_coin, rug_status (0=safe, 1=rugged),
        issue_date (unix timestamp), is_migrated (bool)
    """
    body: dict = {"chain": chain, "contract": contract, "limit": limit}
    if is_migrated is not None:
        body["is_migrated"] = is_migrated
    return _request("/market/v3/coin/dev", body)


def security(chain: str, contract: str, source: str = "bg") -> dict:
    """Security audit for a token. Check highRisk, riskCount, buyTax/sellTax, etc. See docs/market-data.md."""
    body = {"list": [{"chain": chain, "contract": contract}], "source": source}
    return _request("/market/v3/coin/security/audits", body)


def launchpad_tokens(
    chain: str = "sol",
    platforms: Optional[List[str]] = None,
    stage: Optional[int] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    mc_min: Optional[int] = None,
    mc_max: Optional[int] = None,
    lp_min: Optional[int] = None,
    lp_max: Optional[int] = None,
    vol_min: Optional[int] = None,
    vol_max: Optional[int] = None,
    holder_min: Optional[int] = None,
    holder_max: Optional[int] = None,
    progress_min: Optional[float] = None,
    progress_max: Optional[float] = None,
    sniper_percent_max: Optional[float] = None,
    keywords: Optional[str] = None,
    limit: int = 100,
) -> dict:
    """
    Scan launchpad new pools. Filters by chain, platform, stage, age, market cap, liquidity, volume, holders, progress, etc.

    stage: 0=new (progress<0.5), 1=launching (0.5~1.0), 2=launched (progress>=1.0)
    age_min/age_max: token age range in seconds
    mc_min/mc_max: market cap range (USD)
    lp_min/lp_max: liquidity range (USD)
    vol_min/vol_max: volume range (USD)
    holder_min/holder_max: holder count range
    progress_min/progress_max: bonding curve progress (0~1)
    sniper_percent_max: max sniper holder percentage (0~1)
    platforms: list of platform identifiers. Supported values:
      Solana: pump.fun, pump.fun.mayhem, raydium.Launchlab, believe, bonk.fun,
              jup.studio, bags.fm, trends.fun, MeteoraBC, muffun.fun
      BNB:    four.meme, four.meme.bn, four.meme.agent, flap
      Base:   zoraContent, zoraCreator, virtuals, clanker, bankr
    keywords: search keyword (e.g. "pepe")

    Response fields per token: chain, contract, symbol, name, icon, issue_date, holders,
    liquidity, top10/insider/sniper/dev holder percents, dev_rug_percent, lock_lp_percent,
    price, socials (twitter/website/telegram/discord), platform, progress, market_cap, turnover, txns.
    """
    body: dict = {"chain": chain, "limit": limit}
    if platforms is not None:
        body["platforms"] = platforms
    if stage is not None:
        body["stage"] = stage
    if age_min is not None:
        body["age_min"] = age_min
    if age_max is not None:
        body["age_max"] = age_max
    if mc_min is not None:
        body["mc_min"] = mc_min
    if mc_max is not None:
        body["mc_max"] = mc_max
    if lp_min is not None:
        body["lp_min"] = lp_min
    if lp_max is not None:
        body["lp_max"] = lp_max
    if vol_min is not None:
        body["vol_min"] = vol_min
    if vol_max is not None:
        body["vol_max"] = vol_max
    if holder_min is not None:
        body["holder_min"] = holder_min
    if holder_max is not None:
        body["holder_max"] = holder_max
    if progress_min is not None:
        body["progress_min"] = progress_min
    if progress_max is not None:
        body["progress_max"] = progress_max
    if sniper_percent_max is not None:
        body["sniper_percent_max"] = sniper_percent_max
    if keywords is not None:
        body["keywords"] = keywords
    return _request("/market/v3/launchpad/tokens", body)


# ---------------------------------------------------------------------------
# Token Deep Analysis APIs (bgw_token_analyze)
# ---------------------------------------------------------------------------


def simple_kline(
    chain: str,
    contract: str,
    period: str = "5m",
    size: Optional[int] = None,
    user_address: Optional[str] = None,
    is_show_kol: bool = True,
    is_show_smart_money: bool = True,
    is_show_developer: bool = True,
) -> dict:
    """K-line with KOL/smart money trade signals and hot level.

    period: 1m/5m/15m/30m/1h/2h/4h/6h/8h/12h/1d/3d/1w (default 5m)
    size: number of candles (auto-calculated if omitted)
    user_address: wallet address for user avg buy/sell price lines
    is_show_kol/is_show_smart_money/is_show_developer: toggle signal overlays

    Response includes: list (candles with tagUserStats), kolSmartHotLevel (low/medium/high),
    userAvgBuyPrice, userAvgSellPrice, ssekey, isHaveMoreData.
    """
    body: dict = {
        "chain": chain,
        "contract": contract,
        "period": period,
        "isShowKol": is_show_kol,
        "isShowSmartMoney": is_show_smart_money,
        "isShowDeveloper": is_show_developer,
    }
    if size is not None:
        body["size"] = size
    if user_address is not None:
        body["userAddress"] = user_address
    return _request("/market/v2/coin/SimpleKline", body)


def trading_dynamics(chain: str, contract: str) -> dict:
    """Multi-window trading dynamics (5m/1h/4h/24h).

    Returns 4 time windows with: summary (AI text), price_change, buy/sell volume,
    buyer/seller count, level_a/b/c/wash address counts, amount_distribution,
    address_tags (smart_money/kol/manipulator fund flow).
    """
    body = {"chain": chain, "contract": contract}
    return _request("/market/v2/coin/GetTradingDynamics", body)


def transaction_list(
    chain: str,
    contract: str,
    page: int = 1,
    size: int = 20,
    side: Optional[str] = None,
    only_barrage: bool = False,
    period: Optional[str] = None,
    txnfrom_tags: Optional[List[str]] = None,
    address_list: Optional[List[str]] = None,
) -> dict:
    """Transaction records with tag/direction/time filtering.

    side: buy / sell (omit for all)
    only_barrage: true = only tagged transactions (smart money/KOL/dev etc.)
    period: 5m / 15m / 1h / 4h / 24h
    txnfrom_tags: filter by tags — smart_money / kol / developer / bot / manipulator
    address_list: filter by specific addresses

    Response per tx: side, txnfrom, txhash, valueNum (USD), amountNum, price,
    ts, marketCap, txnfromTags, txnfromLevelTag (A/B/C/D), addressUserName, tx_url.
    """
    body: dict = {"chain": chain, "contract": contract, "page": page, "size": size}
    if side is not None:
        body["side"] = side
    if only_barrage:
        body["onlyBarrage"] = True
    if period is not None:
        body["period"] = period
    if txnfrom_tags is not None:
        body["txnfromTags"] = txnfrom_tags
    if address_list is not None:
        body["addressList"] = address_list
    return _request("/market/v2/coin/TransactionList", body)


def holders_info(
    chain: str,
    contract: str,
    sort: str = "holding_desc",
    special_holder_key: Optional[str] = None,
    address_tags: Optional[List[str]] = None,
) -> dict:
    """Top100 holders with classification (CEX/smart money/KOL) and PnL.

    sort: holding_desc (default) / pnl_desc / pnl_asc
    special_holder_key: kol / smart_money / follow
    address_tags: multi-tag OR filter

    Response: top10Percent, total_holder_count, price, avg_holder_balance,
    holders.list[] (addr, amount, amount_usd, percent, profit_amount_str,
    profit_rate_str, user_tags, level_tag), special_holders, other_holders.
    """
    body: dict = {"chain": chain, "contract": contract, "sort": sort}
    if special_holder_key is not None:
        body["special_holder_key"] = special_holder_key
    if address_tags is not None:
        body["address_tags"] = address_tags
    return _request("/market/v2/GetHoldersInfo", body)


def profit_address_analysis(chain: str, contract: str) -> dict:
    """Profitable address summary statistics.

    Response: profit_addr_count, total_profit_addr_count, total_addr_count,
    profit_percent, avg_cost, address_dynamics (add/hold/reduce/close counts
    with user_type breakdown: kol/smart_money/manipulator/other),
    profit_distribution (ranges: 0-100/100-500/500-1k/1k-5k/5k+),
    user_type_stats (kol/smart_money/manipulator counts).
    """
    body = {"chain": chain, "contract": contract}
    return _request("/market/v2/coin/GetProfitAddressAnalysis", body)


def top_profit(
    chain: str,
    contract: str,
    limit: int = 100,
    offset: int = 0,
    latest_position: Optional[str] = None,
    txn_from_tags: Optional[List[str]] = None,
) -> dict:
    """Top profitable addresses list with PnL details.

    Response: summary (profit_rate, buy_avg_price, sell_avg_price),
    list[] (address, latest_position, total_profit, total_profit_str,
    total_profit_rate, total_profit_rate_str, user_tags, level_tag),
    address_tag_config[], address_level_tag_config[].
    """
    body: dict = {"chain": chain, "contract": contract, "limit": limit, "offset": offset}
    if latest_position is not None:
        body["latest_position"] = latest_position
    if txn_from_tags is not None:
        body["txn_from_tags"] = txn_from_tags
    return _request("/market/v2/coin/GetTopProfit", body)


# ---------------------------------------------------------------------------
# Address Discovery APIs (bgw_address_find)
# ---------------------------------------------------------------------------


def recommend_address_list(
    recommend_group_ids: Optional[List[int]] = None,
    data_period: str = "7d",
    sort_field: str = "pnl_usd",
    sort_order: str = "desc",
    param_filters: Optional[dict] = None,
    page: int = 1,
    limit: int = 30,
) -> dict:
    """Find addresses by role (KOL / smart money) with performance filters.

    recommend_group_ids: role filter. [0]=all (default), [1]=smart money, [2]=KOL.
        Group IDs are dynamic — obtain from response recommend_groups field.
    data_period: statistics window — 24h / 7d (default) / 30d
    sort_field: pnl_usd (default) / win_rate / trade_count / last_activity_time
    sort_order: desc (default) / asc
    param_filters: filter map. Keys: chain (values: ["sol","bnb","base","eth"]),
        pnl_usd (range: min/max in USD), win_rate (range: min/max 0-100),
        trade_count (range: min/max).
        Example: {"chain": {"values": ["sol"]}, "win_rate": {"min": 70, "max": 100}}
    page: page number (default 1)
    limit: page size, max 30 (default 30)

    Response: addresses[] (chain, address, address_tags, profit_analysis with
    win_rate/total_profit_usd/tx_count, holdings[]),
    recommend_groups (available role groups), sort_fields, filter_fields, statistic_times.
    """
    body: dict = {
        "data_period": data_period,
        "sort_field": sort_field,
        "sort_order": sort_order,
        "page": page,
        "limit": limit,
    }
    if recommend_group_ids is not None:
        body["recommend_group_ids"] = recommend_group_ids
    if param_filters is not None:
        body["param_filters"] = param_filters
    return _request("/market/v2/monitor/recommend-group/address/list", body)


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


def _cmd_batch_v2(args):
    """Primary balance API: batch balance + price for all chains."""
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


def _cmd_search_tokens_v3(args):
    out = search_tokens_v3(
        keyword=args.keyword,
        chain=getattr(args, "chain", None),
        limit=args.limit,
        order_by=getattr(args, "order_by", None),
    )
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


def _cmd_alpha_gems(args):
    out = alpha_gems()
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_alpha_signals(args):
    filters = None
    if getattr(args, "filters", None):
        filters = json.loads(args.filters)
    out = alpha_signals(
        chain=args.chain,
        page=args.page,
        size=args.size,
        offset=args.offset,
        filters=filters,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_alpha_hunter_find(args):
    out = alpha_hunter_find(
        chain=args.chain,
        page=args.page,
        limit=args.limit,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_alpha_hunter_detail(args):
    out = alpha_hunter_detail(chain=args.chain, address=args.address)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_agent_alpha_tags(args):
    out = agent_alpha_tags()
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_agent_alpha_hunter_find(args):
    out = agent_alpha_hunter_find(
        chain=args.chain,
        tag=args.tag,
        page=args.page,
        limit=args.limit,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_multi_agent_signal(args):
    out = multi_agent_signal(
        chain=args.chain,
        page=args.page,
        size=args.size,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_liquidity(args):
    out = liquidity(chain=args.chain, contract=args.contract)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_coin_market_info(args):
    out = coin_market_info(chain=args.chain, contract=args.contract)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_coin_dev(args):
    is_mig = None
    if args.is_migrated is not None:
        is_mig = args.is_migrated.lower() == "true"
    out = coin_dev(
        chain=args.chain,
        contract=args.contract,
        limit=args.limit,
        is_migrated=is_mig,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_security(args):
    out = security(chain=args.chain, contract=args.contract)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_launchpad_tokens(args):
    out = launchpad_tokens(
        chain=args.chain,
        platforms=args.platforms.split(",") if args.platforms else None,
        stage=args.stage,
        age_min=args.age_min,
        age_max=args.age_max,
        mc_min=args.mc_min,
        mc_max=args.mc_max,
        lp_min=args.lp_min,
        lp_max=args.lp_max,
        vol_min=args.vol_min,
        vol_max=args.vol_max,
        holder_min=args.holder_min,
        holder_max=args.holder_max,
        progress_min=args.progress_min,
        progress_max=args.progress_max,
        sniper_percent_max=args.sniper_percent_max,
        keywords=args.keywords,
        limit=args.limit,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


# ---- Token Analyze CLI ----


def _cmd_simple_kline(args):
    out = simple_kline(
        chain=args.chain,
        contract=args.contract,
        period=getattr(args, "period", "5m"),
        size=getattr(args, "size", None),
        user_address=getattr(args, "user_address", None),
        is_show_kol=not getattr(args, "no_kol", False),
        is_show_smart_money=not getattr(args, "no_smart_money", False),
        is_show_developer=not getattr(args, "no_developer", False),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_trading_dynamics(args):
    out = trading_dynamics(chain=args.chain, contract=args.contract)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_transaction_list(args):
    out = transaction_list(
        chain=args.chain,
        contract=args.contract,
        page=getattr(args, "page", 1),
        size=getattr(args, "size", 20),
        side=getattr(args, "side", None),
        only_barrage=getattr(args, "only_barrage", False),
        period=getattr(args, "period", None),
        txnfrom_tags=args.txnfrom_tags.split(",") if getattr(args, "txnfrom_tags", None) else None,
        address_list=args.address_list.split(",") if getattr(args, "address_list", None) else None,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_holders_info(args):
    out = holders_info(
        chain=args.chain,
        contract=args.contract,
        sort=getattr(args, "sort", "holding_desc"),
        special_holder_key=getattr(args, "special_holder_key", None),
        address_tags=args.address_tags.split(",") if getattr(args, "address_tags", None) else None,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_profit_address_analysis(args):
    out = profit_address_analysis(chain=args.chain, contract=args.contract)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_top_profit(args):
    tags = args.txn_from_tags.split(",") if getattr(args, "txn_from_tags", None) else None
    out = top_profit(
        chain=args.chain,
        contract=args.contract,
        limit=args.limit,
        offset=args.offset,
        latest_position=getattr(args, "latest_position", None),
        txn_from_tags=tags,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _cmd_compare_tokens(args):
    period = getattr(args, "period", "1h")
    size = getattr(args, "size", None)
    out_a = simple_kline(chain=args.chain_a, contract=args.contract_a, period=period, size=size,
                         is_show_kol=False, is_show_smart_money=False, is_show_developer=False)
    out_b = simple_kline(chain=args.chain_b, contract=args.contract_b, period=period, size=size,
                         is_show_kol=False, is_show_smart_money=False, is_show_developer=False)
    # Build ts-indexed maps
    map_a = {item["ts"]: item for item in (out_a.get("data", {}).get("list", []))}
    map_b = {item["ts"]: item for item in (out_b.get("data", {}).get("list", []))}
    all_ts = sorted(set(map_a.keys()) | set(map_b.keys()))
    aligned = []
    for ts in all_ts:
        row = {"ts": ts}
        a = map_a.get(ts)
        b = map_b.get(ts)
        if a:
            row["price_a"] = a.get("price")
            row["volume_a"] = a.get("volume")
            row["marketCap_a"] = a.get("marketCap")
        if b:
            row["price_b"] = b.get("price")
            row["volume_b"] = b.get("volume")
            row["marketCap_b"] = b.get("marketCap")
        aligned.append(row)
    result = {
        "token_a": {"chain": args.chain_a, "contract": args.contract_a},
        "token_b": {"chain": args.chain_b, "contract": args.contract_b},
        "period": period,
        "aligned": aligned,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ---- Address Find CLI ----


def _cmd_recommend_address_list(args):
    group_ids = None
    if getattr(args, "group_ids", None):
        group_ids = [int(x) for x in args.group_ids.split(",")]
    param_filters = None
    if getattr(args, "filter_chain", None) or getattr(args, "filter_win_rate_min", None) \
            or getattr(args, "filter_win_rate_max", None) or getattr(args, "filter_pnl_min", None) \
            or getattr(args, "filter_pnl_max", None) or getattr(args, "filter_trade_count_min", None) \
            or getattr(args, "filter_trade_count_max", None):
        param_filters = {}
        if getattr(args, "filter_chain", None):
            param_filters["chain"] = {"values": args.filter_chain.split(",")}
        wr = {}
        if getattr(args, "filter_win_rate_min", None) is not None:
            wr["min"] = args.filter_win_rate_min
        if getattr(args, "filter_win_rate_max", None) is not None:
            wr["max"] = args.filter_win_rate_max
        if wr:
            param_filters["win_rate"] = wr
        pnl = {}
        if getattr(args, "filter_pnl_min", None) is not None:
            pnl["min"] = args.filter_pnl_min
        if getattr(args, "filter_pnl_max", None) is not None:
            pnl["max"] = args.filter_pnl_max
        if pnl:
            param_filters["pnl_usd"] = pnl
        tc = {}
        if getattr(args, "filter_trade_count_min", None) is not None:
            tc["min"] = args.filter_trade_count_min
        if getattr(args, "filter_trade_count_max", None) is not None:
            tc["max"] = args.filter_trade_count_max
        if tc:
            param_filters["trade_count"] = tc
    out = recommend_address_list(
        recommend_group_ids=group_ids,
        data_period=getattr(args, "data_period", "7d"),
        sort_field=getattr(args, "sort_field", "pnl_usd"),
        sort_order=getattr(args, "sort_order", "desc"),
        param_filters=param_filters,
        page=getattr(args, "page", 1),
        limit=getattr(args, "limit", 30),
    )
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
    global WALLET_ID
    parser = argparse.ArgumentParser(description="Bitget Wallet Agent API (new swap flow, no apiKey)")
    parser.add_argument("--wallet-id", default="",
                        help="Social Login Wallet ID (from profile endpoint). "
                             "When set, all API calls use this as the 'token' header "
                             "instead of the default 'toc_agent'.")
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

    # batchV2: primary balance API — balance + token price for all chains
    p = sub.add_parser("batch-v2", help="[Balance] Batch balance + token price /user/wallet/batchV2 (primary balance API)")
    p.add_argument("--json-stdin", action="store_true", help="Read body {list: [{chain, address, contract}]} from stdin")
    p.add_argument("--chain", help="Chain code (required when not using --json-stdin)")
    p.add_argument("--address", help="Wallet address (required when not using --json-stdin)")
    p.add_argument("--contract", action="append", default=[], help="Token contract(s); empty for native. Repeat or comma-separated.")
    p.add_argument("--no-include-native", action="store_true", dest="no_include_native", help="Do not add native token to contract list")
    p.set_defaults(func=_cmd_batch_v2)

    # searchTokens: search by keyword or contract address; optional chain to restrict to one chain
    p = sub.add_parser("search-tokens", help="[Search] Search tokens by keyword or contract (v2)")
    p.add_argument("--keyword", required=True, help="Keyword or full contract address")
    p.add_argument("--chain", default=None, help="Optional: restrict search to this chain (e.g. bnb, eth)")
    p.set_defaults(func=_cmd_search_tokens)

    p = sub.add_parser("search-tokens-v3", help="[Search] Search tokens with ordering support (v3)")
    p.add_argument("--keyword", required=True, help="Search term (name, symbol, or contract)")
    p.add_argument("--chain", default=None, help="Optional chain filter (e.g. eth, sol, bnb)")
    p.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    p.add_argument("--order-by", dest="order_by", default=None, help="Sort field (e.g. market_cap)")
    p.set_defaults(func=_cmd_search_tokens_v3)

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

    p = sub.add_parser("alpha-gems", help="[Alpha] Alpha gems — AI-curated high-potential tokens")
    p.set_defaults(func=_cmd_alpha_gems)

    p = sub.add_parser("alpha-signals", help="[Alpha] Alpha signals — smart money/KOL/growth signals")
    p.add_argument("--chain", default="all", help="Chain filter (sol, eth, bnb, base, all; default: all)")
    p.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    p.add_argument("--size", type=int, default=20, help="Page size (default: 20)")
    p.add_argument("--offset", type=int, default=0, help="Offset for dedup (default: 0)")
    p.add_argument("--filters", default=None, help='JSON array of {chain, contract} filters, e.g. \'[{"chain":"sol","contract":"0x..."}]\'')
    p.set_defaults(func=_cmd_alpha_signals)

    p = sub.add_parser("alpha-hunter-find", help="[Alpha] Alpha hunter — smart money address list with scores")
    p.add_argument("--chain", required=True, help="Chain code (sol, eth, bnb, base)")
    p.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    p.add_argument("--limit", type=int, default=20, help="Page size (default: 20, max: 200)")
    p.set_defaults(func=_cmd_alpha_hunter_find)

    p = sub.add_parser("alpha-hunter-detail", help="[Alpha] Alpha hunter factor detail for an address")
    p.add_argument("--chain", required=True, help="Chain code (sol, eth, bnb, base)")
    p.add_argument("--address", required=True, help="Wallet address")
    p.set_defaults(func=_cmd_alpha_hunter_detail)

    p = sub.add_parser("agent-alpha-tags", help="[Alpha] List available Agent tag labels")
    p.set_defaults(func=_cmd_agent_alpha_tags)

    p = sub.add_parser("agent-alpha-hunter-find", help="[Alpha] Find addresses by Agent tag (e.g. early_alpha_hunter)")
    p.add_argument("--chain", required=True, help="Chain code (sol, eth, bnb, base)")
    p.add_argument("--tag", required=True, help="Agent tag (use agent-alpha-tags to list available)")
    p.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    p.add_argument("--limit", type=int, default=20, help="Page size (default: 20, max: 200)")
    p.set_defaults(func=_cmd_agent_alpha_hunter_find)

    p = sub.add_parser("multi-agent-signal", help="[Alpha] Multi-agent signals — tokens bought by Agent-tagged addresses (cross-strategy)")
    p.add_argument("--chain", default="all", help="Chain filter (sol, eth, bnb, base, all; default: all)")
    p.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    p.add_argument("--size", type=int, default=20, help="Page size (default: 20, max: 100)")
    p.set_defaults(func=_cmd_multi_agent_signal)

    p = sub.add_parser("liquidity", help="[Market] Get liquidity pool info for a token")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=_cmd_liquidity)

    p = sub.add_parser("coin-market-info", help="[Market] Token market info + pool list (price, MC, FDV, pairs, narratives)")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=_cmd_coin_market_info)

    p = sub.add_parser("coin-dev", help="[Market] Dev historical projects (rug status, migration, MC, LP)")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.add_argument("--limit", type=int, default=30, help="Max tokens to return (default: 30)")
    p.add_argument("--is-migrated", dest="is_migrated", default=None, help="Filter: true=migrated, false=unmigrated, omit=all")
    p.set_defaults(func=_cmd_coin_dev)

    p = sub.add_parser("security", help="[Market] Security audit for a token")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=_cmd_security)

    p = sub.add_parser("launchpad-tokens", help="[Market] Scan launchpad new pools (pump.fun etc.)")
    p.add_argument("--chain", default="sol", help="Chain code (default: sol)")
    p.add_argument("--platforms", default=None, help="Comma-separated platforms (e.g. pump.fun,raydium.Launchlab,four.meme,virtuals)")
    p.add_argument("--stage", type=int, default=None, help="0=new, 1=launching, 2=launched")
    p.add_argument("--age-min", dest="age_min", type=int, default=None, help="Min token age in seconds")
    p.add_argument("--age-max", dest="age_max", type=int, default=None, help="Max token age in seconds")
    p.add_argument("--mc-min", dest="mc_min", type=int, default=None, help="Min market cap (USD)")
    p.add_argument("--mc-max", dest="mc_max", type=int, default=None, help="Max market cap (USD)")
    p.add_argument("--lp-min", dest="lp_min", type=int, default=None, help="Min liquidity (USD)")
    p.add_argument("--lp-max", dest="lp_max", type=int, default=None, help="Max liquidity (USD)")
    p.add_argument("--vol-min", dest="vol_min", type=int, default=None, help="Min volume (USD)")
    p.add_argument("--vol-max", dest="vol_max", type=int, default=None, help="Max volume (USD)")
    p.add_argument("--holder-min", dest="holder_min", type=int, default=None, help="Min holder count")
    p.add_argument("--holder-max", dest="holder_max", type=int, default=None, help="Max holder count")
    p.add_argument("--progress-min", dest="progress_min", type=float, default=None, help="Min bonding curve progress (0~1)")
    p.add_argument("--progress-max", dest="progress_max", type=float, default=None, help="Max bonding curve progress (0~1)")
    p.add_argument("--sniper-percent-max", dest="sniper_percent_max", type=float, default=None, help="Max sniper holder percent (0~1)")
    p.add_argument("--keywords", default=None, help="Search keyword (e.g. pepe)")
    p.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    p.set_defaults(func=_cmd_launchpad_tokens)

    # ---- Token Analyze (bgw_token_analyze) ----
    p = sub.add_parser("simple-kline", help="[Analyze] K-line + KOL/smart money signals + hot level")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.add_argument("--period", default="5m", help="K-line period: 1m/5m/15m/30m/1h/2h/4h/6h/8h/12h/1d/3d/1w (default: 5m)")
    p.add_argument("--size", type=int, default=None, help="Number of candles (auto if omitted)")
    p.add_argument("--user-address", dest="user_address", default=None, help="Wallet address for avg buy/sell price lines")
    p.add_argument("--no-kol", dest="no_kol", action="store_true", help="Hide KOL trade signals")
    p.add_argument("--no-smart-money", dest="no_smart_money", action="store_true", help="Hide smart money signals")
    p.add_argument("--no-developer", dest="no_developer", action="store_true", help="Hide developer signals")
    p.set_defaults(func=_cmd_simple_kline)

    p = sub.add_parser("trading-dynamics", help="[Analyze] Multi-window trading dynamics (5m/1h/4h/24h)")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=_cmd_trading_dynamics)

    p = sub.add_parser("transaction-list", help="[Analyze] Transaction records with tag/direction/time filtering")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    p.add_argument("--size", type=int, default=20, help="Page size (default: 20)")
    p.add_argument("--side", default=None, choices=["buy", "sell"], help="Direction filter")
    p.add_argument("--only-barrage", dest="only_barrage", action="store_true", help="Only tagged transactions (smart money/KOL/dev)")
    p.add_argument("--period", default=None, help="Time window: 5m/15m/1h/4h/24h")
    p.add_argument("--txnfrom-tags", dest="txnfrom_tags", default=None, help="Comma-separated tags: smart_money,kol,developer,bot,manipulator")
    p.add_argument("--address-list", dest="address_list", default=None, help="Comma-separated addresses to filter")
    p.set_defaults(func=_cmd_transaction_list)

    p = sub.add_parser("holders-info", help="[Analyze] Top100 holders + classification + PnL")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.add_argument("--sort", default="holding_desc", choices=["holding_desc", "pnl_desc", "pnl_asc"], help="Sort order (default: holding_desc)")
    p.add_argument("--special-holder-key", dest="special_holder_key", default=None, choices=["kol", "smart_money", "follow"], help="Filter special holders")
    p.add_argument("--address-tags", dest="address_tags", default=None, help="Comma-separated tag filter (OR logic)")
    p.set_defaults(func=_cmd_holders_info)

    p = sub.add_parser("profit-address-analysis", help="[Analyze] Profitable address statistics")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.set_defaults(func=_cmd_profit_address_analysis)

    p = sub.add_parser("top-profit", help="[Analyze] Top profitable addresses list")
    p.add_argument("--chain", required=True)
    p.add_argument("--contract", required=True)
    p.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    p.add_argument("--offset", type=int, default=0, help="Offset for pagination (default: 0)")
    p.add_argument("--latest-position", dest="latest_position", default=None, help="Filter by position: add/hold/reduce/close/open")
    p.add_argument("--txn-from-tags", dest="txn_from_tags", default=None, help="Comma-separated tag filter: smart_money,kol,bot,manipulator")
    p.set_defaults(func=_cmd_top_profit)

    p = sub.add_parser("compare-tokens", help="[Analyze] Compare two tokens K-line side by side")
    p.add_argument("--chain-a", dest="chain_a", required=True, help="Token A chain")
    p.add_argument("--contract-a", dest="contract_a", required=True, help="Token A contract")
    p.add_argument("--chain-b", dest="chain_b", required=True, help="Token B chain")
    p.add_argument("--contract-b", dest="contract_b", required=True, help="Token B contract")
    p.add_argument("--period", default="1h", help="K-line period (default: 1h)")
    p.add_argument("--size", type=int, default=None, help="Number of candles")
    p.set_defaults(func=_cmd_compare_tokens)

    # ---- Address Find (bgw_address_find) ----
    p = sub.add_parser("recommend-address-list", help="[Address] Find addresses by role (KOL/smart money) with performance filters")
    p.add_argument("--group-ids", dest="group_ids", default=None, help="Role group IDs, comma-separated. 0=all, 1=smart money, 2=KOL (dynamic — check response recommend_groups)")
    p.add_argument("--data-period", dest="data_period", default="7d", choices=["24h", "7d", "30d"], help="Statistics window (default: 7d)")
    p.add_argument("--sort-field", dest="sort_field", default="pnl_usd", choices=["pnl_usd", "win_rate", "trade_count", "last_activity_time"], help="Sort field (default: pnl_usd)")
    p.add_argument("--sort-order", dest="sort_order", default="desc", choices=["desc", "asc"], help="Sort direction (default: desc)")
    p.add_argument("--filter-chain", dest="filter_chain", default=None, help="Chain filter, comma-separated (sol,bnb,base,eth)")
    p.add_argument("--filter-win-rate-min", dest="filter_win_rate_min", type=float, default=None, help="Min win rate (0-100)")
    p.add_argument("--filter-win-rate-max", dest="filter_win_rate_max", type=float, default=None, help="Max win rate (0-100)")
    p.add_argument("--filter-pnl-min", dest="filter_pnl_min", type=float, default=None, help="Min profit (USD)")
    p.add_argument("--filter-pnl-max", dest="filter_pnl_max", type=float, default=None, help="Max profit (USD)")
    p.add_argument("--filter-trade-count-min", dest="filter_trade_count_min", type=int, default=None, help="Min trade count")
    p.add_argument("--filter-trade-count-max", dest="filter_trade_count_max", type=int, default=None, help="Max trade count")
    p.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    p.add_argument("--limit", type=int, default=30, help="Page size, max 30 (default: 30)")
    p.set_defaults(func=_cmd_recommend_address_list)

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
    if args.wallet_id:
        WALLET_ID = args.wallet_id
    args.func(args)


if __name__ == "__main__":
    main()
