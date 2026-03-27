# Address Discovery Domain Knowledge

## bgw_address_find — Address Discovery

**Covers:** Finding high-performance wallet addresses by role (KOL, smart money) with performance-based filtering and sorting.

**Design principle:** One tool covers the "find address" domain. The backend provides curated address lists with pre-computed performance metrics; the Skills layer handles presentation and context.

### API Mapping

| Use Case | Command | Endpoint |
|----------|---------|----------|
| **Find by role** | `recommend-address-list` | `POST /market/v2/monitor/recommend-group/address/list` |

---

## recommend-address-list

Find addresses by role (KOL / smart money) with performance filters.

**When to use:** Discover high-performing wallets for copy-trading research, alpha discovery, or whale watching. Use role groups to filter by address type, and param_filters to narrow by chain, win rate, profit, or trade count.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--group-ids` | string | no | Role group IDs, comma-separated. `0`=all (default), `1`=smart money, `2`=KOL. IDs are dynamic — verify from response `recommend_groups` |
| `--data-period` | string | no | Statistics window: `24h` / `7d` (default) / `30d` |
| `--sort-field` | string | no | Sort by: `pnl_usd` (profit, default) / `win_rate` / `trade_count` / `last_activity_time` |
| `--sort-order` | string | no | Sort direction: `desc` (default) / `asc` |
| `--filter-chain` | string | no | Chain filter, comma-separated: `sol`, `bnb`, `base`, `eth` |
| `--filter-win-rate-min` | float | no | Min win rate (0-100) |
| `--filter-win-rate-max` | float | no | Max win rate (0-100) |
| `--filter-pnl-min` | float | no | Min profit (USD) |
| `--filter-pnl-max` | float | no | Max profit (USD) |
| `--filter-trade-count-min` | int | no | Min trade count |
| `--filter-trade-count-max` | int | no | Max trade count |
| `--page` | int | no | Page number (default: 1) |
| `--limit` | int | no | Page size, max 30 (default: 30) |

### Response — Top Level

| Field | Type | Description |
|-------|------|-------------|
| `addresses` | array | Address list (see per-address fields below) |
| `recommend_groups` | array | Available role groups: `group_id` + `name` + `is_default`. Use these IDs for `--group-ids` |
| `sort_fields` | array | Available sort fields with `key`, `name`, `is_default` |
| `filter_fields` | array | Available filter fields with type (`range` or `multiple`) and options/ranges |
| `statistic_times` | array | Available time periods: `24h`, `7d`, `30d` |
| `current_timestamp` | int64 | Server timestamp (seconds) |

### Response — Each Address

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique ID (chain + address) |
| `chain` | string | Chain code |
| `address` | string | Wallet address |
| `address_avatar` | string | Avatar URL |
| `address_user_name` | string | Display name (KOLs have Twitter username) |
| `chain_symbol` | string | Chain symbol (e.g. SOL, BNB) |
| `address_balance_usd` | decimal | Current balance (USD) |
| `last_active_time` | int64 | Last activity timestamp (seconds) |
| `holdings` | array | Current token holdings (max 5). Each: `chain`, `contract`, `symbol`, `name`, `icon` |
| `address_icons` | array | Social links (e.g. Twitter redirect URL) |
| `address_tags` | array | Role tags: `[{key: "kol", name: "KOLs"}]` or `[{key: "smart_money", name: "Smart Money"}]` |
| `profit_analysis` | object | Performance metrics (see below) |
| `user_status` | object | Follow/monitor status: `is_following`, `is_monitoring` |

### Response — profit_analysis

| Field | Type | Description |
|-------|------|-------------|
| `win_rate` | decimal | Win rate (0.91 = 91%) |
| `total_profit_usd` | decimal | Total profit (USD) |
| `total_profit_rate` | decimal | Total profit rate (0.887 = 88.7%) |
| `tx_count` | int | Total trade count |
| `buy_tx_count` / `sell_tx_count` | int | Buy/sell trade counts |
| `buy_usd` / `sell_usd` | decimal | Buy/sell total volume (USD) |
| `volume_usd` | decimal | Total trading volume (USD) |
| `win_coin_count` / `loss_coin_count` | int | Profitable / losing token count |
| `profit_list` | array | Daily profit aggregation: `timestamp` + `profit_usd` + `profit_rate` |

### Available Role Groups

Current groups (dynamic — always verify from response `recommend_groups`):

| group_id | Name | Description |
|----------|------|-------------|
| 0 | All | Default, returns all role addresses |
| 2 | KOLs | KOL addresses (often with Twitter profiles) |
| 1 | Smart Money | Smart money addresses (proven on-chain performance) |

### Available Filters

| Filter Key | Type | Description |
|------------|------|-------------|
| `chain` | multiple | Chain filter: `sol`, `bnb`, `base`, `eth` |
| `pnl_usd` | range | Profit range (USD): min 0, max 999999999 |
| `win_rate` | range | Win rate range (%): min 0, max 100 |
| `trade_count` | range | Trade count range: min 0, max 999999 |

### Usage Examples

```bash
# Top profitable addresses across all roles (default)
python3 scripts/bitget-wallet-agent-api.py recommend-address-list

# Smart money on Solana, sorted by win rate
python3 scripts/bitget-wallet-agent-api.py recommend-address-list \
  --group-ids 1 --filter-chain sol --sort-field win_rate

# KOLs with >80% win rate in the last 30 days
python3 scripts/bitget-wallet-agent-api.py recommend-address-list \
  --group-ids 2 --filter-win-rate-min 80 --data-period 30d

# High-profit smart money (>$10K profit, 7d)
python3 scripts/bitget-wallet-agent-api.py recommend-address-list \
  --group-ids 1 --filter-pnl-min 10000 --data-period 7d

# Most active traders on Base
python3 scripts/bitget-wallet-agent-api.py recommend-address-list \
  --filter-chain base --sort-field trade_count --sort-order desc

# Recently active addresses
python3 scripts/bitget-wallet-agent-api.py recommend-address-list \
  --sort-field last_activity_time --sort-order desc --limit 10
```

### Key Signals

| Signal | Meaning |
|--------|---------|
| High `win_rate` + high `tx_count` | Consistently profitable, not just lucky |
| High `win_rate` + low `tx_count` | May be lucky or selective; verify with more data |
| `address_tags` contains `smart_money` | Algorithmically identified as high-performance |
| `address_tags` contains `kol` | Known influencer; check `address_icons` for Twitter |
| `holdings` shows specific tokens | Currently holding — can cross-reference with token analysis |
| High `total_profit_usd` + recent `last_active_time` | Active and profitable — strong signal |
| `profit_list` shows consistent daily profits | Sustained performance, not one-time luck |

### Combining with Other Tools

After finding interesting addresses via `recommend-address-list`, use bgw_token_analyze tools for deeper analysis:

1. Check their `holdings` tokens with `coin-market-info` and `security` (bgw_token_check)
2. Use `transaction-list --address-list <addr>` to see their recent trades on a specific token
3. Use `holders-info --special-holder-key smart_money` to see if they appear in top holders
