# Alpha Intelligence Domain Knowledge

## bgw_alpha — Alpha Intelligence

**Covers:** AI-curated token discovery (gems), real-time trading signals (smart money flow, KOL calls, buyer growth), and alpha hunter (smart money) address intelligence.

**Design principle:** One tool covers the "alpha intelligence" domain. Six watch_types: `alpha` for curated gems, `alpha_signals` for real-time signals, `alpha_hunter_find` for smart money address discovery, `alpha_hunter_detail` for individual address scoring, `agent_alpha_tags` for behavioral tag enum, `agent_alpha_hunter_find` for tag-based address discovery.

**vs bgw_token_find:** token_find is keyword/filter-based discovery (user searches). bgw_alpha is AI-curated — the system surfaces tokens based on detected on-chain activity patterns.

### API Mapping

| watch_type | Command | Endpoint | Method |
|------------|---------|----------|--------|
| **alpha** | `alpha-gems` | `/market/v3/alpha/gems` | GET |
| **alpha_signals** | `alpha-signals` | `/market/v3/alpha/signals` | POST |
| **alpha_hunter_find** | `alpha-hunter-find` | `/market/v3/address/smart-money` | POST |
| **alpha_hunter_detail** | `alpha-hunter-detail` | `/market/v3/address/factor-detail` | POST |
| **agent_alpha_tags** | `agent-alpha-tags` | `/market/v3/address/agent-tags` | GET |
| **agent_alpha_hunter_find** | `agent-alpha-hunter-find` | `/market/v3/address/agent-tag-list` | POST |

---

## alpha (alpha-gems)

AI-curated high-potential tokens with strategy labels. No parameters — returns the current gems list.

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `chain` | string | Chain: sol, eth, bnb, base |
| `contract` | string | Contract address |
| `symbol` | string | Token symbol |
| `name` | string | Token name |
| `icon` | string | Token icon URL |
| `chain_icon` | string | Chain icon URL |
| `today_first_price` | string | Price when first pushed today |
| `today_max_change` | number | Max price change since first push today (percentage) |
| `first_time` | string | Time of first push today |
| `market_cap` | number | Market cap at first push time |
| `strategy` | string | Strategy label (see strategy values below) |

**strategy values:** `smart_money`, `kol`, and others

```bash
python3 scripts/bitget-wallet-agent-api.py alpha-gems
```

---

## alpha_signals (alpha-signals)

Real-time trading signals — smart money flow, KOL calls, buyer growth patterns.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--chain` | string | no | all | Chain filter: sol, eth, bnb, base, all |
| `--page` | int | no | 1 | Page number |
| `--size` | int | no | 20 | Page size |
| `--offset` | int | no | 0 | Offset for dedup pagination |
| `--filters` | JSON string | no | — | Array of `{chain, contract}` to filter specific tokens |

### Response fields

| Field | Type | Description |
|-------|------|-------------|
| `chain` | string | Chain: sol, eth, bnb, base |
| `contract` | string | Contract address |
| `symbol` | string | Token symbol |
| `name` | string | Token name |
| `icon` | string | Token icon URL |
| `price` | number | Current price (USD) |
| `change_24h` | number | 24h price change (percentage) |
| `market_cap` | number | Market cap (USD) |
| `signal` | string | Signal description (translated, human-readable) |
| `signal_value` | number | Signal metric (e.g. buyer count) |
| `holder` | number | Holder count |
| `media_list` | array | Media links: `[{name, url, icon}]` |
| `push_times` | number | Number of times this token was pushed |
| `max_change` | number | Max price change (percentage) |
| `strategy` | string | Strategy type (see below) |
| `push_time` | number | Push timestamp (seconds) |
| `open_time` | number | Token open timestamp (seconds) |
| `ai_summary` | string | AI-generated summary |
| `trigger_window` | string | Trigger time window: 5m / 1h / 4h / 24h (strategy-specific) |
| `trigger_address_count` | number | Number of trigger addresses (strategy-specific) |
| `total_inflow_usd` | number | Total inflow USD (strategy-specific) |
| `growth_rate` | number | Growth rate as decimal, e.g. 0.35 = 35% (strategy-specific) |
| `addresses` | array\<string\> | Trigger wallet addresses (strategy-specific) |
| `kols` | array | KOL details (kol_call strategy only): `[{username, follower_count, timestamp}]` |

### Strategy types

| Strategy | Description | Key fields |
|----------|-------------|------------|
| `alpha_hunter` | Smart money / alpha hunters buying in | `trigger_address_count`, `total_inflow_usd`, `addresses` |
| `kol_call` | KOL mentions / calls | `kols` (username, followers, timestamp) |
| `buyers_growth_5min` | Rapid buyer count growth in 5 min window | `growth_rate`, `trigger_address_count` |

More strategy types may be added by backend.

### filters parameter

Filter by specific chain+contract pairs:

```bash
python3 scripts/bitget-wallet-agent-api.py alpha-signals --filters '[{"chain":"sol","contract":"CE2Mfjg46daZVQHmc3iVLnVDFKQyQe5zwLB9Zmrppump"}]'
```

### Usage examples

```bash
# All signals (cross-chain)
python3 scripts/bitget-wallet-agent-api.py alpha-signals

# Solana signals only
python3 scripts/bitget-wallet-agent-api.py alpha-signals --chain sol --size 10

# Paginated
python3 scripts/bitget-wallet-agent-api.py alpha-signals --chain all --page 2 --size 20
```

---

## alpha_hunter_find (alpha-hunter-find)

Discover top-ranked smart money (alpha hunter) addresses on a chain with multi-dimensional scoring.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--chain` | string | yes | — | Chain: sol, eth, bnb, base |
| `--page` | int | no | 1 | Page number |
| `--limit` | int | no | 20 | Page size (max: 200) |

### Response — Top Level

| Field | Type | Description |
|-------|------|-------------|
| `list` | array | Smart money address list |
| `total` | number | Total count (max 5000) |
| `page` | number | Current page |
| `limit` | number | Page size |
| `date_time` | string | Data batch timestamp |

### Response — Each Address

**Core scoring:**

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | Wallet address |
| `chain` | string | Chain |
| `score` | number | Overall score |
| `score_win_rate` | number | Win rate score |
| `score_total_profit` | number | Total profit |
| `score_7d_profit` | number | 7-day profit |
| `score_30d_profit` | number | 30-day profit |

**Factor dimensions (each has `_factor` score + `_label` tag):**

| Factor | Description |
|--------|-------------|
| `profit_factor` / `profit_label` | Profitability |
| `capture_factor` / `capture_label` | Token capture ability |
| `early_sniffer_factor` / `early_sniffer_label` | Early entry detection |
| `activity_factor` / `activity_label` | Trading activity level |

**Trading style metrics:**

| Field | Description |
|-------|-------------|
| `score_rate_buy` / `score_rate_sell` | Buy/sell win rate |
| `score_holding_time` / `score_holding_time_label` | Holding duration |
| `score_stability` / `score_stability_label` | Trading stability |
| `score_style` / `score_style_label` | Trading style |
| `score_blue_chip_ratio` / `score_blue_chip_ratio_label` | Blue chip allocation ratio |
| `avg_buy_cost_label` | Average buy cost level |

**Profit/loss breakdown:**

| Field | Description |
|-------|-------------|
| `score_top1/5/10_profit` + `_label` | Top 1/5/10 best trade profit |
| `score_top1/5/10_loss` + `_label` | Top 1/5/10 worst trade loss |
| `score_avg_profit_buy` / `score_avg_profit_sell` | Average profit per buy/sell |

```bash
# Top smart money on Solana
python3 scripts/bitget-wallet-agent-api.py alpha-hunter-find --chain sol

# Page 2, 50 per page
python3 scripts/bitget-wallet-agent-api.py alpha-hunter-find --chain sol --page 2 --limit 50
```

---

## alpha_hunter_detail (alpha-hunter-detail)

Get detailed scoring factors for a specific smart money address. Returns the same fields as `alpha-hunter-find` list items.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--chain` | string | yes | Chain: sol, eth, bnb, base |
| `--address` | string | yes | Wallet address |

### Response

Returns `data.data` (single address object, same fields as alpha-hunter-find list element) + `data.date_time`. Returns `null` if address not found.

```bash
python3 scripts/bitget-wallet-agent-api.py alpha-hunter-detail --chain sol --address <wallet_address>
```

---

## agent_alpha_hunter_find (agent-alpha-tags + agent-alpha-hunter-find)

Find smart money addresses by **Agent tag** — a behavioral classification system. Two-step flow: first list available tags, then query addresses by tag.

### Step 1: List available tags

```bash
python3 scripts/bitget-wallet-agent-api.py agent-alpha-tags
```

No parameters. Returns the static tag enum:

| Tag | Description |
|-----|-------------|
| `early_alpha_hunter` | Early alpha hunter |
| `stable_profiteer` | Stable profiteer |
| `whale_player` | Whale player |
| `short_term_trader` | Short-term trader |
| `diamond_hand` | Diamond hand holder |
| `meme_sniper` | Meme sniper |
| `high_odds_hunter` | High odds hunter |
| `trend_rider` | Trend rider |
| `balanced_all_rounder` | Balanced all-rounder |
| `bluechip_player` | Blue chip player |

### Step 2: Query addresses by tag

```bash
python3 scripts/bitget-wallet-agent-api.py agent-alpha-hunter-find --chain sol --tag early_alpha_hunter
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--chain` | string | yes | — | Chain: sol, eth, bnb, base |
| `--tag` | string | yes | — | Agent tag from the enum above |
| `--page` | int | no | 1 | Page number |
| `--limit` | int | no | 20 | Page size (max: 200) |

#### Response — Top Level

| Field | Type | Description |
|-------|------|-------------|
| `list` | array | Address list |
| `total` | number | Total count (max 5000) |
| `page` | number | Current page |
| `limit` | number | Page size |
| `date_time` | string | Data batch timestamp |

#### Response — Each Address

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | Wallet address |
| `chain` | string | Chain |
| `tag` | string | Agent tag |
| `score` | number | Overall score |
| `score_v1` | number | Macro factor score |
| `score_v2` | number | Micro factor score |
| `date_time` | string | Data batch timestamp |

#### Usage examples

```bash
# List tags first
python3 scripts/bitget-wallet-agent-api.py agent-alpha-tags

# Find early alpha hunters on Solana
python3 scripts/bitget-wallet-agent-api.py agent-alpha-hunter-find --chain sol --tag early_alpha_hunter --limit 10

# Find meme snipers on BNB
python3 scripts/bitget-wallet-agent-api.py agent-alpha-hunter-find --chain bnb --tag meme_sniper

# Diamond hands on Solana, page 2
python3 scripts/bitget-wallet-agent-api.py agent-alpha-hunter-find --chain sol --tag diamond_hand --page 2 --limit 50
```

**vs alpha-hunter-find:** `alpha-hunter-find` returns all smart money addresses with full multi-dimensional scoring factors. `agent-alpha-hunter-find` filters by behavioral tag (e.g. meme_sniper, diamond_hand) with simpler scoring (score + score_v1 + score_v2). Use `alpha-hunter-find` for comprehensive scoring; use `agent-alpha-hunter-find` for targeted behavioral discovery.

---

## Combined Usage

**Alpha discovery flow:**

1. `alpha-gems` — get today's AI-curated gems (quick overview, no parameters)
2. `alpha-signals` — get real-time signals with more detail (ai_summary, signal descriptions)
3. Follow up with `bgw_token_check` (security + coin-market-info) for any token that looks interesting

**Alpha hunter flow:**

1. `alpha-hunter-find` — discover top smart money addresses on a chain
2. `alpha-hunter-detail` — deep dive into a specific address's scoring factors
3. Cross-reference with `bgw_token_analyze` (transaction-list / top-profit) to see what tokens these addresses are trading

**Mandatory output rule:** All alpha results presented to the user **must** include **chain** and **contract address (CA)** (for tokens) or **chain** and **address** (for wallets). This ensures the user can immediately proceed to check, analyze, or trade.
