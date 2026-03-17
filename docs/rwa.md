# RWA (Real World Asset) Stock Trading

This document describes **RWA stock trading**: tokenized real-world stocks (e.g. NVDA, TSLA) tradable on supported chains via the same swap flow. Use `scripts/bitget_agent_api.py` for RWA discovery and config, then follow [Swap](swap.md) for execution.

## Business Background

**RWA (Real World Asset)** in this context refers to **tokenized stocks** — on-chain representations of traditional equities (e.g. NVIDIA, Tesla). Users can:

- **Buy** RWA stock tokens by spending stablecoins (USDT, USDC, etc.) on a supported chain (e.g. BNB, Ethereum).
- **Sell** RWA stock tokens to receive stablecoins.

Trading uses the same **swap** backend: RWA stock is treated as a token with a **ticker** (e.g. `NVDAon`), **name**, and **contract** address per chain. Supported chains for RWA are currently **bnb** and **eth**. The agent should use RWA-specific APIs for discovery and market info, then reuse the standard swap flow (quote → confirm → makeOrder → sign & send → getOrderDetails) with RWA ticker/contract as from/to token.

## RWA Trading Flow

| Step | Purpose |
|------|--------|
| a | User selects an RWA stock: use **rwa-get-user-ticker-selector** to search or list supported RWA tickers and pick one. |
| b | Get config: **rwa-get-config** to obtain stablecoins allowed for RWA trading (fromTokenList / toTokenList). |
| c | Get market state: **rwa-stock-info** for market status and trading amount limits. |
| d | Get display prices: **rwa-stock-order-price** for current buy/sell display price. |
| e (optional) | K-line: **rwa-kline** if the user wants RWA stock chart data. |
| e (optional) | Holdings: **rwa-get-my-holdings** or **rwa-get-user-ticker-selector** with `user_address` to see current RWA holdings. |
| f | Execute trade: reuse the **swap flow** in [swap.md](swap.md). Use RWA **name** (or symbol) for `fromSymbol`/`toSymbol` and RWA **contract** for `fromContract`/`toContract`. After a successful swap, use **rwa-get-user-ticker-selector** (with user_address) or **rwa-get-my-holdings** to show updated holdings. |

### Combined Query After User Selects an RWA Stock

Once the user has chosen which RWA stock to operate (ticker + chain), the agent should **call in parallel** (or in one batch):

1. **rwa-get-config** — with the user’s addresses (e.g. bnb, eth, sol) to get `fromTokenList` / `toTokenList` (stablecoins).
2. **rwa-stock-info** — with the ticker to get market status and amount limits.
3. **rwa-stock-order-price** — with ticker, chain, `side=buy`, one stablecoin contract from config, and user address.
4. **rwa-stock-order-price** — with ticker, chain, `side=sell`, same stablecoin contract, and user address.

Then **summarize and show** the user in one place:

- **Current securities market status** — from `rwa_stock_info` (e.g. `market_status_title`, `market_status_simple_content`, `status`).
- **Current buy price** — from `rwa_stock_order_price` (side=buy) `data.order_price`.
- **Current sell price** — from `rwa_stock_order_price` (side=sell) `data.order_price`.
- **Supported stablecoin list** — from `rwa_get_config` `data.fromTokenList` / `data.toTokenList` (symbol, chain, contract).
- **Trading amount limits** — from `rwa_stock_info` (e.g. `tx_minimum_usd`, `tx_maximum_usd`, `tx_minimum_sell_usd`, `tx_maximum_sell_usd`, or per-chain in `chain_assets[].tx_*`).

## Swap Flow Reuse for RWA

When the user decides to trade (buy or sell an RWA stock on a chosen chain):

- **Buy RWA:** fromToken = stablecoin (e.g. USDT), toToken = RWA stock. Set `fromSymbol`/`fromContract` to the stablecoin, `toSymbol`/`toContract` to the RWA stock **name** and **contract** for that chain.
- **Sell RWA:** fromToken = RWA stock, toToken = stablecoin. Set `fromSymbol`/`fromContract` to the RWA stock **name** and **contract**, `toSymbol`/`toContract` to the stablecoin.

Follow [swap.md](swap.md) for balance check, token risk check, quote, confirm, makeOrder, sign, send, and getOrderDetails. After a successful swap, call **rwa-get-user-ticker-selector** (with `--user-address`) or **rwa-get-my-holdings** to show the user’s updated RWA position.

## Python Script Commands (RWA)

All commands are run via `python3 scripts/bitget_agent_api.py <command> ...`.

### rwa-get-user-ticker-selector

Query or search RWA stock tickers; optionally include user balance when `--user-address` is provided.

```bash
python3 scripts/bitget_agent_api.py rwa-get-user-ticker-selector --chain bnb [--user-address <addr>] [--key-word <keyword>]
```

- `--chain` (required): `bnb` or `eth`.
- `--user-address` (optional): wallet address; if set, response includes `balance` and `balance_usd` per ticker.
- `--key-word` (optional): search by name or stock contract address.

### rwa-get-config

Get RWA trading config: stablecoin list (fromTokenList / toTokenList), slippage, amount limits, gasInfoList.

```bash
python3 scripts/bitget_agent_api.py rwa-get-config --address-list "bnb,0x...;eth,0x...;sol,..."
# Or JSON stdin:
echo '{"addressList":[{"chain":"bnb","address":"0x..."},{"chain":"eth","address":"0x..."}]}' | python3 scripts/bitget_agent_api.py rwa-get-config --json-stdin
```

- `--address-list`: semicolon-separated `chain,address` pairs for bnb, eth, sol.
- `--json-stdin`: read body `{ "addressList": [ { "chain", "address" }, ... ] }` from stdin.

### rwa-stock-info

Get RWA stock info by ticker (market status, trading limits, chain_assets). **GET** request.

```bash
python3 scripts/bitget_agent_api.py rwa-stock-info --ticker NVDAon
```

### rwa-stock-order-price

Get display buy/sell price for an RWA stock (for pre-trade display only).

```bash
python3 scripts/bitget_agent_api.py rwa-stock-order-price --ticker NVDAon --chain bnb --side buy --tx-coin-contract 0x55d398326f99059ff775485246999027b3197955 --user-address 0x...
python3 scripts/bitget_agent_api.py rwa-stock-order-price --ticker NVDAon --chain bnb --side sell --tx-coin-contract 0x55d398326f99059ff775485246999027b3197955 --user-address 0x...
```

- `--tx-coin-contract`: stablecoin contract from rwaGetConfig (fromTokenList / toTokenList).

### rwa-kline

Get K-line data for an RWA stock.

```bash
python3 scripts/bitget_agent_api.py rwa-kline --chain rwa --contract NVDAon --period 1d [--size 30]
```

- `--chain`: use `rwa` for RWA kline.
- `--contract`: RWA ticker (e.g. NVDAon).
- `--period`: e.g. `1d`, `1h`.

### rwa-get-my-holdings

Get the user’s RWA stock holdings.

```bash
python3 scripts/bitget_agent_api.py rwa-get-my-holdings --user-address 0x...
```

Response includes `data.balance_list` with ticker, balance, chain_asset, etc.
