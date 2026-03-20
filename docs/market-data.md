# Market Data Domain Knowledge

## Tool Architecture — Market Side

Market tools handle **token discovery and analysis only**. No trading, wallet, or on-chain execution.

### bgw_token_find — Token Discovery (Single Entry Point)

**Covers:** Chain scanning, search, rankings, sectors, new token discovery

**Design principle:** One tool covers the "find token" domain. Parameters control depth and scope. Skills layer handles computation and rules; backend provides raw data only.

#### API Mapping

| Use Case | Command | Endpoint |
|----------|---------|----------|
| **Scan new pools** | `launchpad-tokens` | `POST /market/v3/launchpad/tokens` |
| **Search tokens** | `search-tokens-v3` | `POST /market/v3/coin/search` |
| **Rankings** | `rankings` | `POST /market/v3/topRank/detail` |
| **New launches** | `historical-coins` | `POST /market/v3/historical-coins` |
| **Token list** | `get-token-list` | `POST /swap-go/swapx/getTokenList` |

#### Launchpad Scanner (launchpad-tokens)

**Core scenarios:** Meme coin sniping, new pool discovery, bonding curve monitoring

**Filter dimensions:**

| Dimension | Parameter | Typical Values | Description |
|-----------|-----------|----------------|-------------|
| Chain | `--chain` | sol, bnb, base | Default: sol |
| Platform | `--platforms` | pump.fun, four.meme, virtuals | Comma-separated |
| Stage | `--stage` | 0/1/2 | 0=new (progress<0.5), 1=launching (0.5~1.0), 2=launched (>=1.0) |
| Age | `--age-min/max` | 60~86400 | Seconds; filter too old or too new |
| Market cap | `--mc-min/max` | 10000~5000000 | USD |
| Liquidity | `--lp-min/max` | 5000~ | USD |
| Volume | `--vol-min/max` | 1000~ | USD |
| Holders | `--holder-min/max` | 100~ | Filter ghost tokens |
| Bonding progress | `--progress-min/max` | 0~1 | 0.5~1.0 = launching phase |
| Sniper % | `--sniper-percent-max` | 0.1 | Filter sniped tokens |
| Keywords | `--keywords` | pepe, trump | Name search |

**Supported platforms:**

| Chain | Platforms |
|-------|----------|
| Solana | pump.fun, pump.fun.mayhem, raydium.Launchlab, believe, bonk.fun, jup.studio, bags.fm, trends.fun, MeteoraBC, muffun.fun |
| BNB | four.meme, four.meme.bn, four.meme.agent, flap |
| Base | zoraContent, zoraCreator, virtuals, clanker, bankr |

**Response fields (per token):**
chain, contract, symbol, name, icon, issue_date, holders, liquidity, price, platform, progress, market_cap, turnover, txns, top10_holder_percent, insider_holder_percent, sniper_holder_percent, dev_holder_percent, dev_holder_balance, dev_issue_coin_count, dev_rug_coin_count, dev_rug_percent, lock_lp_percent, twitter, website, telegram, discord

**Skills-layer computation (backend provides raw data, agent/skills compute):**

- **Pool TIER rating:** Based on market_cap + liquidity + holders
  - TIER-S: MC > $1M, LP > $100K, holders > 5000
  - TIER-A: MC > $100K, LP > $20K, holders > 1000
  - TIER-B: MC > $10K, LP > $5K, holders > 100
  - TIER-C: Everything else
- **Safety pre-screening:** dev_rug_percent > 20% → red flag; sniper_holder_percent > 10% → warning; top10 > 50% → concentration risk
- **Progress assessment:** progress approaching 1.0 = about to launch, highest volatility

**Common discovery strategies:**

```bash
# Strategy 1: High-quality pump.fun tokens about to launch
launchpad-tokens --chain sol --platforms pump.fun --stage 1 --progress-min 0.8 --holder-min 200 --lp-min 10000

# Strategy 2: Launched tokens with high liquidity (value scan)
launchpad-tokens --stage 2 --lp-min 50000 --holder-min 1000

# Strategy 3: Low-cap gems (high risk)
launchpad-tokens --stage 1 --mc-min 5000 --mc-max 50000 --holder-min 50

# Strategy 4: BNB chain four.meme scan
launchpad-tokens --chain bnb --platforms four.meme --stage 1

# Strategy 5: Keyword sniping
launchpad-tokens --keywords trump --stage 1 --holder-min 50
```

#### Token Search (search-tokens-v3)

**Core scenario:** Find tokens by name, symbol, or contract address

| Parameter | Description |
|-----------|-------------|
| `--keyword` | Name, symbol, or full contract address |
| `--chain` | Optional chain filter |
| `--order-by` | Sort field (e.g. `market_cap`) |
| `--limit` | Max results |

**Response fields:** chain, contract, symbol, name, icon, issue_date, holders, liquidity, top10/insider/sniper/dev holder percents, dev_rug_percent, lock_lp_percent, price, socials, risk_level, market_cap, turnover, txns

**risk_level field:** low / medium / high — pre-computed by backend, use directly

**Tips:**
- Contract address search doesn't need `--chain`; backend auto-detects
- `--order-by market_cap` puts highest MC first, effective for filtering fakes
- risk_level is a quick pre-screen; use bgw_token_check for deep security analysis

#### Rankings

**Built-in rankings:**

| Name | Description |
|------|-------------|
| `topGainers` | Top price gainers |
| `topLosers` | Top price losers |
| `Hotpicks` | Curated picks (platform editorial / algorithm recommended trending tokens) |

#### New Token Discovery (historical-coins)

Scan newly issued tokens by timestamp. Supports pagination: response `lastTime` is passed as `--create-time` in next request.

---

### bgw_token_check — Token Analysis (Single Entry Point)

**Covers:** Security audit, dev analysis, market overview, anti-manipulation detection, signal confluence

**Design principle:** One tool covers the "check token" domain. Backend returns raw data; Skills layer handles scoring and rules. Narrative tags are pre-labeled by backend — use directly.

#### API Mapping

| Use Case | Command | Endpoint |
|----------|---------|----------|
| **Security audit** | `security` | `POST /market/v3/coin/security/audits` |
| **Dev analysis** | `coin-dev` | `POST /market/v3/coin/dev` |
| **Market overview** | `coin-market-info` | `POST /market/v3/coin/getMarketInfo` |
| **Token info** | `token-info` | `POST /market/v3/coin/batchGetBaseInfo` |
| **K-line data** | `kline` | `POST /market/v3/coin/getKline` |
| **Tx stats** | `tx-info` | `POST /market/v3/coin/getTxInfo` |
| **Liquidity pools** | `liquidity` | `POST /market/v3/poolList` |
| **Swap risk check** | `check-swap-token` | `POST /swap-go/swapx/checkSwapToken` |

#### Security Audit (security)

**Core scenario:** Contract detection (honeypot/mint/proxy) + risk level + buy/sell tax

**Response structure:**
```
data[]:
  highRisk: bool           # Critical risk flag
  riskCount / warnCount    # Risk/warning counts
  buyTax / sellTax         # Trade tax rates
  freezeAuth / mintAuth    # Freeze/mint authority (Solana)
  lpLock: bool             # LP locked
  top_10_holder_risk_level # Top holder risk level
  riskChecks[]             # High risk items (status=1 = triggered)
  warnChecks[]             # Warning items
  lowChecks[]              # Low risk items (status=0 = safe)
```

**labelName Reference — EVM:**

| Check | Risk | Warn | Low (Safe) |
|-------|------|------|------------|
| Honeypot | `RiskTitle2` | — | `LowTitle2` ✅ |
| Trade tax | `RiskTitle1` (≥50%) | `WarnTitle1` (≥10%) | `LowTitle1` (<10%) ✅ |
| Tax modifiable | `RiskTitle8` | `WarnTitle8` | `LowTitle8` ✅ |
| Trading pause | `RiskTitle4` | `WarnTitle4` | `LowTitle4` ✅ |
| Blacklist | `RiskTitle15` | `WarnTitle15` | `LowTitle15` ✅ |
| Contract upgradeable | — | `WarnTitle6` | `LowTitle6` ✅ |
| Mintable | — | `WarnTitle10` | `LowTitle10` ✅ |
| Balance modifiable | — | — | `LowTitle7` ✅ |
| Top 10 holder % | `RiskTitle23` (high) | `WarnTitle23` | `LowTitle23` ✅ |
| LP lock | — | `WarnTitle24` | `LowTitle24` ✅ |
| Sniper % | `RiskTitle25` | `WarnTitle25` | `LowTitle25` ✅ |
| Insider % | `RiskTitle26` | `WarnTitle26` | `LowTitle26` ✅ |
| Dev rug rate | `RiskTitle27` (≥50%) | `WarnTitle27` (≥25%) | `LowTitle27` ✅ |
| Dev holdings | `RiskTitle28` (≥30%) | `WarnTitle28` (≥10%) | `LowTitle28` ✅ |
| Suspected honeypot | `RiskTitle29` | `WarnTitle29` | `LowTitle29` ✅ |
| Bundle tx | `RiskTitle30` (>20%) | `WarnTitle30` (>10%) | `LowTitle30` ✅ |

**labelName Reference — Solana:**

| Check | Risk | Warn | Low (Safe) |
|-------|------|------|------------|
| Freeze authority | `SolanaRiskTitle1` | — | `SolanaLowTitle1` ✅ |
| LP burn ratio | — | `SolanaWarnTitle2` | `SolanaLowTitle2` ✅ |
| Top 10 holder % | `SolanaRiskTitle3` (>60%) | `SolanaWarnTitle3` | `SolanaLowTitle3` ✅ |
| Mint authority | — | `SolanaWarnTitle6` | `SolanaLowTitle6` ✅ |
| Trade tax | `SolanaRiskTitle10` (≥50%) | `SolanaWarnTitle10` (≥10%) | `SolanaLowTitle10` ✅ |
| Tax modifiable | `SolanaRiskTitle11` | — | `SolanaLowTitle11` ✅ |
| Sniper % | `SolanaRiskTitle12` | `SolanaWarnTitle12` | `SolanaLowTitle12` ✅ |
| Insider % | `SolanaRiskTitle13` | `SolanaWarnTitle13` | `SolanaLowTitle13` ✅ |

#### Dev Analysis (coin-dev)

**Core scenario:** Dev address + rug history + LP lock + buy/sell volume + holdings + project history

**Response fields:**

| Field | Description |
|-------|-------------|
| `dev_address` | Dev wallet address |
| `dev_holder_percent` | Dev holdings as % of supply |
| `dev_holder_balance` | Dev token balance |
| `dev_is_white_list` | Whitelisted (known trustworthy dev) |
| `dev_issue_coin_count` | Total tokens dev has launched |
| `dev_rug_coin_count` | Tokens dev has rugged |
| `dev_rug_percent` | Rug rate (rug_count / issue_count) |
| `lock_lp_percent` | LP lock ratio (0~1) |
| `dev_buy_amount` / `dev_sell_amount` | Dev buy/sell quantity |
| `dev_buy_value` / `dev_sell_value` | Dev buy/sell value (USD) |
| `dev_migrated_count` | Dev's migrated projects |
| `dev_unmigrated_count` | Dev's unmigrated projects |
| `dev_pump_migrated_count` | Dev's pump migrated count |
| `dev_pump_unmigrated_count` | Dev's pump unmigrated count |

**Skills-layer computation rules:**

- **Dev trust score (Skills layer computes):**
  - dev_is_white_list = true → High trust
  - dev_rug_percent = 0 and dev_issue_coin_count > 10 → Medium-high trust
  - dev_rug_percent < 5% → Medium trust
  - dev_rug_percent 5~20% → Low trust
  - dev_rug_percent > 20% → 🔴 High risk, strong warning
- **Dev behavior analysis:**
  - dev_sell_value >> dev_buy_value → Dev is dumping
  - dev_holder_percent > 10% → Dev holds too much, potential dump
  - lock_lp_percent < 50% → LP not sufficiently locked

#### Market Overview (coin-market-info)

**Core scenario:** Token info + full pool list + narrative tags

**Response fields:**

| Field | Description |
|-------|-------------|
| `price` | Current price |
| `market_cap` / `fdv` | Market cap / fully diluted valuation |
| `liquidity` | Total liquidity across all pools |
| `turnover` | 24h trading volume |
| `holders` | Holder count |
| `age` | Token age (seconds) |
| `change_5m/1h/4h/24h` | Price change by timeframe |
| `pairs[]` | Full list of trading pairs |
| `narratives` | Project narrative description (backend-generated) |
| `narrative_tags` | Narrative tags (e.g. "dog", "ai", "meme") — pre-labeled by backend, use directly |

**pairs[] per pool:** pool_address, protocol, token0_symbol, token1_symbol, liquidity

**Skills-layer computation rules:**

- **Liquidity health:** liquidity / market_cap ratio
  - > 10% → Healthy
  - 5~10% → Normal
  - < 5% → Thin, large trades cause slippage
- **Trading activity:** turnover / liquidity ratio
  - > 100% → High activity
  - 20~100% → Normal
  - < 20% → Low activity
- **Price trend analysis:** Combine change_5m/1h/4h/24h
  - Short-term (5m/1h) up + long-term (24h) down → Bounce / bull trap
  - All timeframes up → Strong momentum
  - Short-term spike (5m > 50%) → Pump warning

#### Recommended Check Flow

Complete token analysis — agent should combine calls in this order:

```
1. coin-market-info  → Price/MC/pools/narratives (overview)
2. security          → Contract security audit (honeypot/tax/permissions)
3. coin-dev          → Dev background + rug history
4. kline + tx-info   → Price trend + volume (optional, for deep analysis)
```

**Quick safety check (pre-trade mandatory):**
```
1. check-swap-token  → forbidden-buy detection
2. security          → highRisk / buyTax / sellTax
```

#### Risk Signal Matrix (Skills Layer Composite Judgment)

| Signal | Source | Flag |
|--------|--------|------|
| `highRisk = true` | security | 🔴 **Do not trade** |
| `buyTax/sellTax > 5%` | security | 🔴 Suspected honeypot |
| `dev_rug_percent > 20%` | coin-dev | 🔴 Dev has rug history |
| `dev_holder_percent > 30%` | coin-dev | 🟡 Dev holds too much |
| `top10_holder_percent > 50%` | search/launchpad | 🟡 Concentrated holdings |
| `holders < 100` | coin-market-info | 🟡 Extremely early or abandoned |
| `liquidity < $10K` | coin-market-info | 🟡 Very thin liquidity |
| `lock_lp_percent < 50%` | coin-dev | 🟡 LP not locked |
| `sniper_holder_percent > 10%` | search/launchpad | 🟡 Sniped |
| `age < 3600` (1h) | coin-market-info | ⚠️ Extremely new, high risk |
| `change_5m > 50%` | coin-market-info | ⚠️ Active pump |
| `forbidden-buy` | check-swap-token | 🔴 **Buying prohibited** |

**When multiple red flags appear together, strongly advise the user against trading.**

---

## K-line Parameters

- **Periods**: `1s`, `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`
- **Max entries**: 1440 per request
- **Buy/sell fields**: Each candle includes `buyTurnover`/`sellTurnover` (USD volume) and `buyAmount`/`sellAmount`. Use to detect buying vs selling pressure.

## Transaction Info Parameters

- **Intervals**: `5m`, `1h`, `4h`, `24h` only
- Returns: buy/sell volume, buyer/seller count

## Historical Coins Pagination

- `createTime` format: `"YYYY-MM-DD HH:MM:SS"` (string, not Unix timestamp)
- Response `lastTime` used for next page pagination
