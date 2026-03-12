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

## K-line: Valid Parameters

- **Periods**: `1s`, `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`
- **Max entries**: 1440 per request
- Other period values will return an error or empty data.

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

