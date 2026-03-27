# Token Deep Analysis Domain Knowledge

## bgw_token_analyze — Token Deep Analysis

**Covers:** K-line with smart money signals, multi-window trading dynamics, tagged transactions, holder distribution, profitable address analysis, token comparison

**Design principle:** One tool covers the "deep analyze token" domain. Goes beyond bgw_token_check (which answers "is it safe?") to answer "should I trade it now?" — trading pressure, smart money flow, holder behavior, and profitability signals.

**vs bgw_token_check:** token_check provides security/dev/market overview (contract safety, rug risk). token_analyze provides trading dynamics/holders/smart money (real-time activity, who is trading, who is profiting).

### API Mapping

| Use Case | Command | Endpoint |
|----------|---------|----------|
| **K-line + signals** | `simple-kline` | `POST /market/v2/coin/SimpleKline` |
| **Trading dynamics** | `trading-dynamics` | `POST /market/v2/coin/GetTradingDynamics` |
| **Transaction list** | `transaction-list` | `POST /market/v2/coin/TransactionList` |
| **Holder analysis** | `holders-info` | `POST /market/v2/GetHoldersInfo` |
| **Profit summary** | `profit-address-analysis` | `POST /market/v2/coin/GetProfitAddressAnalysis` |
| **Top profit list** | `top-profit` | `POST /market/v2/coin/GetTopProfit` |
| **Token compare** | `compare-tokens` | 2x `SimpleKline`, ts-aligned |

### Recommended Analysis Flow

1. **trading-dynamics** — quick 4-window overview of buy/sell pressure and address quality
2. **simple-kline** — K-line with smart money/KOL trade signal overlay
3. **holders-info** — holder distribution, whale tags, PnL
4. **transaction-list --only-barrage** — only tagged transactions (smart money, KOL, dev)
5. **profit-address-analysis + top-profit** — who is profiting and their positions

---

## simple-kline

K-line data with KOL/smart money trade signals and hot level indicator.

**When to use:** Deep price analysis with smart money overlay. Prefer this over `kline` (bgw_token_check) when you need to see who (KOL/smart money/dev) is buying or selling at each candle.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--chain` | string | yes | Chain code (sol, eth, bnb, base, etc.) |
| `--contract` | string | yes | Token contract address |
| `--period` | string | no | K-line period. Default: `5m`. Options: 1m/5m/15m/30m/1h/2h/4h/6h/8h/12h/1d/3d/1w |
| `--size` | int | no | Number of candles (auto-calculated if omitted) |
| `--user-address` | string | no | Wallet address — enables user avg buy/sell price lines |
| `--no-kol` | flag | no | Hide KOL trade signals |
| `--no-smart-money` | flag | no | Hide smart money signals |
| `--no-developer` | flag | no | Hide developer signals |

### Response — Top Level

| Field | Type | Description |
|-------|------|-------------|
| `list` | array | K-line candles (ascending by time) |
| `chain` | string | Chain code |
| `contract` | string | Contract address |
| `userAvgBuyPrice` | float | User average buy price (USD), 0 if no user_address |
| `userAvgSellPrice` | float | User average sell price (USD) |
| `kolSmartHotLevel` | string | Smart money + KOL trade heat: `low` / `medium` / `high` |
| `ssekey` | string | SSE real-time push key |
| `isHaveMoreData` | bool | Whether more historical data is available |

### Response — Each Candle

| Field | Type | Description |
|-------|------|-------------|
| `ts` | int64 | Timestamp (seconds) |
| `price` | float | Close price (USD) |
| `volume` | float | Volume (USD) |
| `marketCap` | float | Market cap (USD) |
| `tagUserStats` | object/null | KOL/smart money trade signals for this candle (null if none) |

### Response — tagUserStats (per candle, when present)

| Field | Type | Description |
|-------|------|-------------|
| `totalTagUserCount` | int | Total tagged users who traded in this candle (deduplicated) |
| `statsList` | array | Grouped by type: `smart_kol_buy` / `smart_kol_sell` / `dev_buy` / `dev_sell`. Each has `textItems` (translation key + params) and `addressList` (address + avatar + tags) |
| `tagTypeStats` | array | Per-tag stats: tag (`smart_money`/`kol`/`developer`) + `buyCount`/`sellCount`/`buyUsers`/`sellUsers` |

```bash
# 24-hour hourly K-line with all signals
python3 scripts/bitget-wallet-agent-api.py simple-kline --chain sol --contract <addr> --period 1h --size 24

# With user avg price lines
python3 scripts/bitget-wallet-agent-api.py simple-kline --chain sol --contract <addr> --period 5m --user-address <wallet>
```

---

## trading-dynamics

Multi-window trading dynamics — returns 4 time windows (5m/1h/4h/24h) in a single call.

**When to use:** Quick activity overview. The AI-generated `summary` field gives a natural language description of each window. Check `wash_count` and `level_a/b/c_count` for address quality.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--chain` | string | yes | Chain code |
| `--contract` | string | yes | Token contract address |

### Response — Each Window

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | Window identifier: `5m` / `1h` / `4h` / `24h` |
| `is_default` | bool | Default display window (usually `1h`) |
| `summary` | string | AI-generated summary text for this window |
| `price_change` | float | Price change ratio (0.1426 = +14.26%) |
| `total_volume` | float | Total volume (USD) |
| `net_volume` | float | Net buy volume (USD, positive = buy pressure) |
| `buy_volume` / `sell_volume` | float | Buy/sell volume (USD) |
| `volume_change_ratio` | float | Volume change vs previous period (positive = increasing, negative = decreasing) |
| `buy_count` / `sell_count` | int | Number of buy/sell transactions |
| `buyers_count` / `sellers_count` | int | Unique buyer/seller addresses |
| `level_a_count` | int | Grade A addresses (high quality, stable behavior) |
| `level_b_count` | int | Grade B addresses (moderate quality) |
| `level_c_count` | int | Grade C addresses (low quality, short-term) |
| `wash_count` | int | Suspected wash-trading addresses |
| `amount_distribution` | array | Volume by range: $0-50 / $50-200 / $200-1K / $1K-5K / $5K+. Each has `volume`, `volume_ratio`, per-level address counts |
| `address_tags` | array/null | Tagged address buy/sell stats: type (`smart_money`/`kol`/`manipulator`) + `buyVolume`/`sellVolume`/`buyCount`/`sellCount`/`buy_wallets`/`sell_wallets` |

```bash
python3 scripts/bitget-wallet-agent-api.py trading-dynamics --chain sol --contract <addr>
```

**Key signals:**
- High `wash_count` relative to total = caution, likely manipulated volume
- `net_volume` strongly positive + increasing `buyers_count` = genuine buying pressure
- `address_tags` with `smart_money` buying = bullish signal
- `volume_change_ratio` negative across all windows = declining interest

---

## transaction-list

Transaction records with tag, direction, and time filtering.

**When to use:** Drill into specific trades. Use `--only-barrage` to see only tagged transactions (smart money, KOL, dev, bot, manipulator). Use `--txnfrom-tags` for fine-grained tag filtering.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--chain` | string | yes | Chain code |
| `--contract` | string | yes | Token contract address |
| `--page` | int | no | Page number (default: 1) |
| `--size` | int | no | Page size (default: 20) |
| `--side` | string | no | Direction filter: `buy` / `sell` |
| `--only-barrage` | flag | no | Only return tagged transactions |
| `--period` | string | no | Time window filter: `5m` / `15m` / `1h` / `4h` / `24h` |
| `--txnfrom-tags` | string | no | Comma-separated tag filter: `smart_money`, `kol`, `developer`, `bot`, `manipulator` |
| `--address-list` | string | no | Comma-separated addresses to filter |

### Response — Each Transaction

| Field | Type | Description |
|-------|------|-------------|
| `side` | string | Direction: `buy` / `sell` |
| `txnfrom` | string | Trader address |
| `txhash` | string | Transaction hash |
| `valueNum` | float | Trade value (USD) |
| `amountNum` | float | Token quantity |
| `price` | float | Execution price (USD) |
| `ts` | int64 | Timestamp (seconds) |
| `marketCap` | float | Market cap at trade time (USD) |
| `txnfromTags` | array | Address tags, e.g. `[{tag: "smart_money"}]` |
| `txnfromLevelTag` | string | Address quality grade: `A` / `B` / `C` / `D` |
| `addressUserName` | string | Twitter username (for KOLs) |
| `tx_url` | string | Block explorer link |

**Available address tags:** `developer`, `smart_money`, `rat_trader` (insider), `bot`, `transfer_in` (phishing), `kol`, `manipulator`

**Address quality grades:** A (high quality, stable) > B (moderate) > C (low quality, short-term) > D

```bash
# All recent transactions
python3 scripts/bitget-wallet-agent-api.py transaction-list --chain sol --contract <addr> --size 20

# Only tagged transactions (smart money, KOL, etc.)
python3 scripts/bitget-wallet-agent-api.py transaction-list --chain sol --contract <addr> --only-barrage

# Smart money buys only
python3 scripts/bitget-wallet-agent-api.py transaction-list --chain sol --contract <addr> --txnfrom-tags smart_money --side buy

# KOL activity in the last hour
python3 scripts/bitget-wallet-agent-api.py transaction-list --chain sol --contract <addr> --txnfrom-tags kol --period 1h
```

---

## holders-info

Top 100 holders with classification (CEX, smart money, KOL, manipulator) and PnL.

**When to use:** Understand holder distribution, concentration risk, and whether top holders are in profit or loss.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--chain` | string | yes | Chain code |
| `--contract` | string | yes | Token contract address |
| `--sort` | string | no | Sort: `holding_desc` (default) / `pnl_desc` / `pnl_asc` |
| `--special-holder-key` | string | no | Filter: `kol` / `smart_money` / `follow` |
| `--address-tags` | string | no | Comma-separated tag filter (OR logic) |

### Response — Top Level

| Field | Type | Description |
|-------|------|-------------|
| `top10Percent` | float | Top 10 holders' share of total supply |
| `total_holder_count` | int | Total holder count |
| `price` | float | Current price (USD) |
| `avg_holder_balance` | float | Average holder balance (USD) |
| `holders.list` | array | Top 100 holder details |
| `holders.total` | int | Total holder count |
| `special_holders` | array | Special holder group counts (KOL, smart money, followed) |
| `top100_buy_avg_price` | decimal | Top 100 average buy price |
| `top100_sell_avg_price` | decimal | Top 100 average sell price |
| `top100_buy_avg_price_change_rate` | decimal | Buy avg price vs current price change rate |
| `other_holders` | object/null | Holdings summary for holders outside top 100 |

### Response — Each Holder

| Field | Type | Description |
|-------|------|-------------|
| `addr` | string | Holder address |
| `amount` | float | Token quantity held |
| `amount_usd` | float | Holdings value (USD) |
| `percent` | float | Share of total supply |
| `profit_amount_str` | string | PnL amount, e.g. `+$9461.17` or `--` |
| `profit_rate_str` | string | PnL rate, e.g. `+573.10%` or `--` |
| `user_tags` | array | Tags (KOL includes Twitter info, CEX includes platform name) |
| `level_tag` | string | Address quality: `A` / `B` / `C` / `D` or empty |

```bash
# Default: top 100 by holdings
python3 scripts/bitget-wallet-agent-api.py holders-info --chain sol --contract <addr>

# Sorted by PnL (most profitable first)
python3 scripts/bitget-wallet-agent-api.py holders-info --chain sol --contract <addr> --sort pnl_desc

# Smart money holders only
python3 scripts/bitget-wallet-agent-api.py holders-info --chain sol --contract <addr> --special-holder-key smart_money
```

---

## profit-address-analysis

Profitable address summary statistics — how many addresses are in profit, their dynamics, and distribution.

**When to use:** Quick overview of profitability landscape. Check if smart money is adding or reducing positions.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--chain` | string | yes | Chain code |
| `--contract` | string | yes | Token contract address |

### Response

| Field | Type | Description |
|-------|------|-------------|
| `summary` | string | Natural language summary |
| `profit_addr_count` | int | Number of top profitable addresses analyzed |
| `total_profit_addr_count` | int | Total addresses in profit |
| `total_addr_count` | int | Total addresses that ever traded |
| `profit_percent` | string | Percentage of addresses in profit |
| `avg_cost` | float | Average cost basis (USD) |
| `address_dynamics` | object | Position dynamics: `add_count`/`hold_count`/`reduce_count`/`close_count` with percents. Includes `user_type_dynamics` breakdown by: `kol`, `smart_money`, `manipulator`, `other` |
| `profit_distribution` | array | Profit ranges: $0-100 / $100-500 / $500-1k / $1k-5k / $5k+, each with `count` and `percent` |
| `user_type_stats` | object | Counts by user type: `kol`, `smart_money`, `manipulator` |

```bash
python3 scripts/bitget-wallet-agent-api.py profit-address-analysis --chain sol --contract <addr>
```

**Key signals:**
- High `add_count` among smart money = accumulation phase
- High `close_count` among smart money = distribution phase
- Most profit concentrated in $0-100 range = retail-dominated, limited whale interest
- `profit_percent` very low = most traders losing money, caution

---

## top-profit

Top profitable addresses list with PnL details.

**When to use:** Identify the most successful traders on a token. Combine with `profit-address-analysis` for full picture.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--chain` | string | yes | Chain code |
| `--contract` | string | yes | Token contract address |

### Response — Summary

| Field | Type | Description |
|-------|------|-------------|
| `summary.profit_rate` | float | Average profit rate across top addresses |
| `summary.buy_avg_price` | float | Average buy price (USD) |
| `summary.sell_avg_price` | float | Average sell price (USD) |
| `summary.chain_coin_symbol` | string | Native token symbol (e.g. SOL) |

### Response — Each Address

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | Wallet address |
| `latest_position` | string | Current action: `open` / `add` / `hold` / `reduce` / `close` |
| `total_profit` | float | Total profit (USD) |
| `total_profit_str` | string | Formatted profit, e.g. `+$1.15K` |
| `total_profit_rate` | float | Profit rate (0.29 = 29%) |
| `total_profit_rate_str` | string | Formatted rate, e.g. `+0.29%` |
| `user_tags` | array | Tags (smart_money, bot, kol, etc.) |
| `level_tag` | string | Address quality: `A` / `B` / `C` / `D` |

```bash
python3 scripts/bitget-wallet-agent-api.py top-profit --chain sol --contract <addr>
```

---

## compare-tokens

Side-by-side K-line comparison of two tokens. Calls SimpleKline twice and aligns results by timestamp.

**When to use:** Compare price action, volume, and market cap trends between two tokens (e.g. competing meme coins, token vs stablecoin).

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--chain-a` | string | yes | Token A chain code |
| `--contract-a` | string | yes | Token A contract address |
| `--chain-b` | string | yes | Token B chain code |
| `--contract-b` | string | yes | Token B contract address |
| `--period` | string | no | K-line period (default: 1h) |
| `--size` | int | no | Number of candles |

### Response

```json
{
  "token_a": {"chain": "sol", "contract": "..."},
  "token_b": {"chain": "sol", "contract": "..."},
  "period": "1h",
  "aligned": [
    {
      "ts": 1774584000,
      "price_a": 5.9e-06, "volume_a": 8914.03, "marketCap_a": 519251174.6,
      "price_b": 0.9964,  "volume_b": 1710725.5, "marketCap_b": 3477374400.7
    }
  ]
}
```

Fields may be absent for a token if no candle exists at that timestamp.

```bash
# Compare BONK vs USDT hourly
python3 scripts/bitget-wallet-agent-api.py compare-tokens \
  --chain-a sol --contract-a DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 \
  --chain-b sol --contract-b Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB \
  --period 1h --size 24
```

---

## Identifying Trading Signals

Combine multiple analysis commands to form a composite view:

| Signal | Source | Bullish | Bearish |
|--------|--------|---------|---------|
| Smart money activity | `simple-kline` tagUserStats | `smart_kol_buy` signals on recent candles | `smart_kol_sell` signals clustering |
| Hot level | `simple-kline` kolSmartHotLevel | `high` — active smart money interest | `low` — no smart money attention |
| Buy/sell pressure | `trading-dynamics` net_volume | Strongly positive across multiple windows | Negative across all windows |
| Address quality | `trading-dynamics` level_a/wash_count | High A/B ratio, low wash | High wash ratio = likely manipulated |
| Tagged activity | `transaction-list --only-barrage` | Smart money/KOL buying | Smart money/KOL selling |
| Holder concentration | `holders-info` top10Percent | < 30% = distributed | > 50% = concentrated risk |
| Holder PnL | `holders-info --sort pnl_desc` | Top holders adding positions | Top holders reducing/closing |
| Profit dynamics | `profit-address-analysis` | Smart money `add_count` high | Smart money `close_count` high |
| Top earners | `top-profit` | Top earners still `hold`/`add` | Top earners `reduce`/`close` |

**When multiple bullish signals align, the token may be worth further investigation. When multiple bearish signals align, caution is strongly advised.**
