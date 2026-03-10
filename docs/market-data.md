# Market Data Domain Knowledge

## Security Audit: Interpret Before Presenting

The `security` command returns raw audit data. Key fields to check:

| Field | Meaning | Action |
|-------|---------|--------|
| `highRisk = true` | Token has critical security issues | **Warn user strongly. Do not recommend trading.** |
| `riskCount > 0` | Number of risk items found | List the specific risks to the user |
| `warnCount > 0` | Number of warnings | Mention but less critical than risks |
| `buyTax` / `sellTax` > 0 | Token charges tax on trades | Include in cost estimation |
| `isProxy = true` | Contract is upgradeable | Mention — owner can change contract behavior |
| `cannotSellAll = true` | Cannot sell 100% of holdings | Major red flag for meme coins |

**Best practice:** Run `security` before any swap involving an unfamiliar token. This should follow the user's configured security preference (see "First-Time Swap Configuration"). If set to "Always check" (default), run automatically and silently — only surface results if risks are found. **Never skip security checks for tokens the user has not traded before, regardless of preference.**

### Security Audit: labelName Reference

The `riskChecks`, `warnChecks`, and `lowChecks` arrays contain items with `labelName` values. Use these tables to translate raw labels into human-readable risk descriptions.

**Solana Token Checks:**

| Check | Risk | Warn | Low |
|-------|------|------|-----|
| Mint authority | — | `SolanaWarnTitle6` (not discarded) | `SolanaLowTitle6` (discarded ✅) |
| Freeze authority | `SolanaRiskTitle1` (not discarded) | — | `SolanaLowTitle1` (discarded ✅) |
| LP burn ratio | — | `SolanaWarnTitle2` (below threshold) | `SolanaLowTitle2` (meets threshold ✅) |
| Top 10 holder % | `SolanaRiskTitle3` (>60%) | `SolanaWarnTitle3` (elevated) | `SolanaLowTitle3` (normal ✅) |
| Trade tax | `SolanaRiskTitle10` (≥50%) | `SolanaWarnTitle10` (≥10%) | `SolanaLowTitle10` (<10% ✅) |
| Tax modifiable | `SolanaRiskTitle11` (yes) | — | `SolanaLowTitle11` (no ✅) |
| Sniper holder % | `SolanaRiskTitle12` (high) | `SolanaWarnTitle12` (elevated) | `SolanaLowTitle12` (normal ✅) |
| Insider holder % | `SolanaRiskTitle13` (high) | `SolanaWarnTitle13` (elevated) | `SolanaLowTitle13` (normal ✅) |
| Dev rug rate | `RiskTitle27` (≥50%) | `WarnTitle27` (≥25%) | `LowTitle27` ✅ |
| Dev holder % | `RiskTitle28` (≥30%) | `WarnTitle28` (≥10%) | `LowTitle28` ✅ |
| Suspected honeypot | `RiskTitle29` | `WarnTitle29` | `LowTitle29` ✅ |

**EVM Token Checks:**

| Check | Risk | Warn | Low |
|-------|------|------|-----|
| Honeypot | `RiskTitle2` (yes) | — | `LowTitle2` (no ✅) |
| Trade tax | `RiskTitle1` (≥50%) | `WarnTitle1` (≥10%) | `LowTitle1` (<10% ✅) |
| Tax modifiable | `RiskTitle8` (yes) | `WarnTitle8` | `LowTitle8` (no ✅) |
| Timelock | — | `WarnTitle9` (has timelock) | `LowTitle9` (none ✅) |
| Trading pause | `RiskTitle4` (pausable) | `WarnTitle4` | `LowTitle4` (not pausable ✅) |
| Blacklist | `RiskTitle15` (has blacklist) | `WranTitle15` | `LowTitle15` (none ✅) |
| Contract upgrade | — | `WarnTitle6` (upgradeable) | `LowTitle6` (not upgradeable ✅) |
| Mint mechanism | — | `WarnTitle10` (mintable) | `LowTitle10` (not mintable ✅) |
| Balance modifiable | — | — | `LowTitle7` (not modifiable ✅) |
| Top 10 holder % | `RiskTitle23` (high) | `WarnTitle23` (elevated) | `LowTitle23` (normal ✅) |
| LP lock ratio | — | `WarnTitle24` (below threshold) | `LowTitle24` (meets threshold ✅) |
| Sniper holder % | `RiskTitle25` (high) | `WarnTitle25` (elevated) | `LowTitle25` (normal ✅) |
| Insider holder % | `RiskTitle26` (high) | `WarnTitle26` (elevated) | `LowTitle26` (normal ✅) |
| Dev rug rate | `RiskTitle27` (≥50%) | `WarnTitle27` (≥25%) | `LowTitle27` ✅ |
| Dev holder % | `RiskTitle28` (≥30%) | `WarnTitle28` (≥10%) | `LowTitle28` ✅ |
| Suspected honeypot | `RiskTitle29` | `WarnTitle29` | `LowTitle29` ✅ |
| Bundle tx detection | `RiskTitle30` (>20%) | `WarnTitle30` (>10%) | `LowTitle30` (<10% ✅) |

**Additional security response fields:**
- `freezeAuth` / `mintAuth` — boolean flags for Solana token authorities
- `token2022` — whether token uses Solana Token-2022 standard
- `lpLock` — whether LP is locked
- `top_10_holder_risk_level` — numeric risk level for top holders
- `buyTax` / `sellTax` — exact tax percentages

## Token Info: Available Fields

The `token-info` command returns comprehensive data including:

**Basic:** `symbol`, `name`, `decimals`, `price`, `total_supply`, `circulating_supply`, `icon`

**Social/Links:** `twitter`, `website`, `telegram`, `whitepaper`, `about` — useful for "where to learn more" questions

**On-chain Metrics:** `holders`, `liquidity`, `top10_holder_percent`, `insider_holder_percent`, `sniper_holder_percent`, `dev_holder_percent`, `dev_holder_balance`, `dev_issue_coin_count`, `dev_rug_coin_count`, `dev_rug_percent`, `lock_lp_percent`

When presenting token info, include social links if the user is researching a token. The `dev_rug_percent` field is particularly valuable — if the developer has a history of rug pulls, warn strongly.

## K-line: Valid Parameters

- **Periods**: `1s`, `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`
- **Max entries**: 1440 per request
- Other period values will return an error or empty data.
- **Buy/Sell breakdown fields**: Each K-line entry includes `buyTurnover`/`sellTurnover` (buy/sell volume in USD) and `buyAmount`/`sellAmount` (buy/sell quantity). Use these to detect buying vs selling pressure within each candle.

## Transaction Info: Valid Intervals

- **Intervals**: `5m`, `1h`, `4h`, `24h` only
- These return buy/sell volume, buyer/seller count for the given time window.
- Other interval values are not supported.

## Historical Coins: Pagination

- `createTime` is a **datetime string** in format `"YYYY-MM-DD HH:MM:SS"` (NOT a Unix timestamp).
- `limit` is a number (max results per page).
- Response contains `lastTime` field (also a datetime string) — pass it as `createTime` in the next request to paginate.
- Example: `--create-time "2026-02-27 00:00:00" --limit 20`
- Useful for discovering newly launched tokens.

## Using Market Data Effectively

The data commands (`token-info`, `kline`, `tx-info`, `liquidity`) are most useful when **combined**, not in isolation:

- **Quick token assessment**: `token-info` (price + market cap + holders) → `tx-info` (recent activity) → `security` (safety check). This gives a complete picture in 3 calls.
- **Trend analysis**: Use `kline --period 1h --size 24` for daily trend, `--period 1d --size 30` for monthly. Compare with `tx-info` to see if volume supports the price movement.
- **Liquidity depth check**: Before a large swap, run `liquidity` to check pool size. If your trade amount is >2% of pool liquidity, expect significant slippage.
- **New token discovery**: `rankings --name topGainers` finds trending tokens. Always follow up with `security` before acting on any discovery.
- **Hot picks**: `rankings --name Hotpicks` returns curated trending tokens across chains — useful for spotting market momentum beyond simple gainers/losers.
- **Whale activity detection**: `tx-info` shows buyer/seller count and volume. A high volume with very few buyers suggests whale activity — proceed with caution.


## Identifying Risky Tokens

Combine multiple signals to assess token risk. No single indicator is definitive:

| Signal | Source | Red Flag |
|--------|--------|----------|
| `highRisk = true` | `security` | **Critical — do not trade** |
| `cannotSellAll = true` | `security` | Honeypot-like behavior |
| `buyTax` or `sellTax` > 5% | `security` | Hidden cost, likely scam |
| `isProxy = true` | `security` | Owner can change rules anytime |
| Holder count < 100 | `token-info` | Extremely early or abandoned |
| Single holder > 50% supply | `token-info` | Rug pull risk |
| LP lock = 0% | `liquidity` | Creator can pull all liquidity |
| Pool liquidity < $10K | `liquidity` | Any trade will cause massive slippage |
| Very high 5m volume, near-zero 24h volume | `tx-info` | Likely wash trading |
| Token age < 24h | `token-info` | Unproven, higher risk |

**When multiple red flags appear together, strongly advise the user against trading.**

