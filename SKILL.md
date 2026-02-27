---
name: bitget-wallet
description: "Interact with Bitget Wallet API for crypto market data, token info, swap quotes, and security audits. Use when the user asks about token prices, market data, swap/trading quotes, token security checks, K-line charts, or token rankings on supported chains (ETH, SOL, BSC, Base, etc.)."
---

# Bitget Wallet Trade Skill

## API Overview

- **Base URL**: `https://bopenapi.bgwapi.io`
- **Auth**: HMAC-SHA256 signature with appId + apiSecret
- **All requests**: POST with JSON body
- **Credentials**: Built-in public demo credentials (works out of the box). Override with `BGW_API_KEY` / `BGW_API_SECRET` env vars for your own keys.
- **Partner-Code**: `bgw_swap_public` (for swap endpoints)

## Domain Knowledge

What you need to know **beyond command syntax** to use these tools correctly. These are cross-command constraints, common pitfalls, and the relationships between commands that the CLI README alone doesn't cover.

### Amounts: Everything is Human-Readable

All BGW API inputs and outputs use **human-readable values**, NOT smallest chain units (wei, lamports, satoshi).

| ✅ Correct | ❌ Wrong |
|-----------|---------|
| `--amount 0.1` (0.1 USDT) | `--amount 100000000000000000` (100 quadrillion USDT!) |
| `--amount 1` (1 SOL) | `--amount 1000000000` (1 billion SOL!) |

This applies to: `swap-quote`, `swap-calldata`, `swap-send`, and all `toAmount` / `fromAmount` values in responses. The `decimals` field in responses is informational only — do not use it for conversion.

### Swap Flow: Command Sequence Matters

Swap is a multi-step process. These commands must be called in order:

```
1. swap-quote     → Get route and estimated output
2. swap-calldata  → Generate unsigned transaction data
3. (wallet signs the transaction externally)
4. swap-send      → Broadcast the signed transaction
```

- **Do not skip steps.** You cannot call `swap-calldata` without first getting a quote.
- **Quotes expire.** If too much time passes between quote and calldata, the route may no longer be valid. Re-quote if the user hesitates.
- **`swap-send` requires a signed raw transaction.** The signing happens outside this skill (wallet app, hardware wallet, or local keyfile).
- **Transaction deadline**: The calldata response includes a `deadline` field (default: 600 seconds = 10 minutes). After this time, the on-chain transaction will revert even if broadcast. The `--deadline` parameter in `swap-calldata` allows customization (in seconds). For volatile markets, users may want a shorter deadline (e.g., 60-120s) to avoid executing at stale prices.

### Swap Quote: Reading the Response

- `estimateRevert=true` means the API **estimates** the transaction may fail on-chain, but it is not guaranteed to fail. For valid amounts, successful on-chain execution has been observed even with `estimateRevert=true`. Still, inform the user of the risk.
- `toAmount` is human-readable. "0.1005" means 0.1005 tokens, not a raw integer.
- `market` field from the quote response is required as input for `swap-calldata`.

### Security Audit: Interpret Before Presenting

The `security` command returns raw audit data. Key fields to check:

| Field | Meaning | Action |
|-------|---------|--------|
| `highRisk = true` | Token has critical security issues | **Warn user strongly. Do not recommend trading.** |
| `riskCount > 0` | Number of risk items found | List the specific risks to the user |
| `warnCount > 0` | Number of warnings | Mention but less critical than risks |
| `buyTax` / `sellTax` > 0 | Token charges tax on trades | Include in cost estimation |
| `isProxy = true` | Contract is upgradeable | Mention — owner can change contract behavior |
| `cannotSellAll = true` | Cannot sell 100% of holdings | Major red flag for meme coins |

**Best practice:** Run `security` before any swap involving an unfamiliar token. Present the audit summary to the user before proceeding.

### K-line: Valid Parameters

- **Periods**: `1s`, `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`
- **Max entries**: 1440 per request
- Other period values will return an error or empty data.

### Transaction Info: Valid Intervals

- **Intervals**: `5m`, `1h`, `4h`, `24h` only
- These return buy/sell volume, buyer/seller count for the given time window.
- Other interval values are not supported.

### Historical Coins: Pagination

- Uses `createTime` (string timestamp) and `limit` (number) parameters.
- Response contains `lastTime` field — pass it as `createTime` in the next request to paginate.
- Useful for discovering newly launched tokens.

### Native Tokens

Use empty string `""` as the contract address for native tokens (ETH, SOL, BNB, etc.). This is a common source of errors — do not pass the wrapped token address (e.g., WETH, WSOL) when querying native token info.

### Common Stablecoin Addresses

**Always use these verified addresses for USDT/USDC.** Do not guess or generate contract addresses from memory — incorrect addresses will cause API errors (`error_code: 80000`, "get token info failed").

> **USDT vs USDT0:** Tether has begun migrating USDT to USDT0 (omnichain version via LayerZero) on some chains. On Arbitrum, the same contract address now represents USDT0 instead of legacy USDT. The contract addresses remain unchanged and work identically with the BGW API — no special handling is needed. When a user asks to swap "USDT", use the address below regardless of whether the chain has migrated to USDT0.

| Chain (code) | USDT (USDT0) | USDC |
|-------------|------|------|
| Ethereum (`eth`) | `0xdAC17F958D2ee523a2206206994597C13D831ec7` | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` |
| BNB Chain (`bnb`) | `0x55d398326f99059fF775485246999027B3197955` | `0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d` |
| Base (`base`) | `0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2` | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| Arbitrum (`arbitrum`) | `0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9` | `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` |
| Optimism (`optimism`) | `0x94b008aA00579c1307B0EF2c499aD98a8ce58e58` | `0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85` |
| Polygon (`matic`) | `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` |
| Solana (`sol`) | `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB` | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |

For other tokens, use `token-info` or a block explorer to verify the contract address before calling swap endpoints.

### Using Market Data Effectively

The data commands (`token-info`, `kline`, `tx-info`, `liquidity`) are most useful when **combined**, not in isolation:

- **Quick token assessment**: `token-info` (price + market cap + holders) → `tx-info` (recent activity) → `security` (safety check). This gives a complete picture in 3 calls.
- **Trend analysis**: Use `kline --period 1h --size 24` for daily trend, `--period 1d --size 30` for monthly. Compare with `tx-info` to see if volume supports the price movement.
- **Liquidity depth check**: Before a large swap, run `liquidity` to check pool size. If your trade amount is >2% of pool liquidity, expect significant slippage.
- **New token discovery**: `rankings --name topGainers` finds trending tokens. Always follow up with `security` before acting on any discovery.
- **Whale activity detection**: `tx-info` shows buyer/seller count and volume. A high volume with very few buyers suggests whale activity — proceed with caution.

### Pre-Trade Workflow

Before executing any swap, the agent should silently run risk checks and then present a **single confirmation summary** to the user. Do not prompt the user at every step.

**Behind the scenes (agent runs automatically):**

```
1. security     → Check highRisk, honeypot, tax
2. token-info   → Get current price, market cap, holder count
3. liquidity    → Check pool depth vs trade size
4. swap-quote   → Get route, expected output, slippage
```

**If any red flags are found** (highRisk, high tax, low liquidity, extreme slippage), stop and warn the user immediately with specifics.

**If everything looks normal**, present a single confirmation:

```
Swap Summary:
• 0.1 USDC → ~0.1000 USDT (BNB Chain)
• Route: bgwevmaggregator
• Slippage tolerance: 0.5%
• Price impact: ~0.07%
• Estimated gas: ~$0.05
• Token safety: ✅ No risks found
• Deadline: 600s (default)

Proceed? [yes/no]
```

**After user confirms:**

```
5. swap-calldata → Generate unsigned transaction
6. (wallet signs the transaction)
7. swap-send    → Broadcast via MEV-protected endpoint
```

**For well-known tokens** (ETH, SOL, BNB, USDT, USDC, DAI, WBTC), the risk checks will almost always pass — the single confirmation is sufficient. For unfamiliar or new tokens, be more verbose about the risks.

### EVM Token Approval (Critical)

On EVM chains (Ethereum, BNB Chain, Base, Arbitrum, Optimism), tokens require an **approve** transaction before the router contract can spend them. **Without approval, the swap transaction will fail on-chain and still consume gas fees.**

- Before calling `swap-calldata`, check if the token has sufficient allowance for the BGW router (`0xBc1D9760bd6ca468CA9fB5Ff2CFbEAC35d86c973`).
- If allowance is 0 or less than the swap amount, an approve transaction must be sent first.
- USDT on some chains (notably Ethereum mainnet) requires setting allowance to 0 before setting a new value.
- **Native tokens** (ETH, SOL, BNB) do not need approval — only ERC-20/SPL tokens.
- Approval is a one-time cost per token per router. Once approved with max amount, subsequent swaps of the same token skip this step.
- **Solana does not use approvals** — this applies only to EVM chains.

Include the approval status in the confirmation summary when relevant:
```
• Token approval: ⚠️ USDC not yet approved for router (one-time gas ~$0.03)
```

### Identifying Risky Tokens

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

### Slippage Control

**Important: distinguish between slippage tolerance and actual price impact.** These are different things:

- **Slippage tolerance** = how much worse than the quoted price you're willing to accept (protection against price movement between quote and execution)
- **Price impact** = how much your trade itself moves the market price (caused by trade size vs pool depth)

**Slippage tolerance (auto-calculated by BGW):**

The `swap-quote` response includes a `slippage` field (e.g., `"0.5"` = 0.5%). This is the system's recommended tolerance, auto-calculated based on token volatility and liquidity.

In `swap-calldata`, you can override it:
- `--slippage <number>` — custom tolerance (1 = 1%). If omitted, uses system default.
- `toMinAmount` — alternative: specify the exact minimum tokens to receive. More precise for advanced users.

**Slippage tolerance thresholds:**

| Tolerance | Action |
|-----------|--------|
| ≤ 1% | Normal for major pairs. Show in summary. |
| 1-3% | Acceptable for mid-cap tokens. Include in summary. |
| 3-10% | **Warn user.** Suggest reducing trade size or setting a custom lower value. |
| > 10% | **Strongly warn.** Low liquidity or high volatility. Suggest splitting into smaller trades. |
| > 0.5% for stablecoin pairs | **Abnormal.** Flag to user — stablecoin swaps should have minimal slippage. |

**Price impact (calculated by agent):**

1. Get **market price** from `token-info`
2. Get **quote price** from `swap-quote` (= `toAmount / fromAmount`)
3. **Price impact** ≈ `(market_price - quote_price) / market_price × 100%`

Price impact > 3% means the trade size is too large relative to available liquidity. The `liquidity` command can confirm — if trade amount > 2% of pool size, expect significant impact.

### Gas and Fees

Transaction costs vary by chain. Be aware of these when presenting swap quotes:

| Chain | Typical Gas | Notes |
|-------|------------|-------|
| Solana | ~$0.001-0.01 | Very cheap, rarely a concern |
| BNB Chain | ~$0.05-0.30 | Low, but check during congestion |
| Ethereum | ~$1-50+ | **Highly variable.** Small trades (<$100) may not be worth the gas. |
| Base / Arbitrum / Optimism | ~$0.01-0.50 | L2s are cheap but not free |

**Important considerations:**
- Gas is paid in the chain's native token (ETH, SOL, BNB). The user must have enough native token balance for gas — a swap will fail if the wallet has tokens but no gas.
- `buyTax` and `sellTax` from the security audit are **on top of** gas fees. A 5% sell tax on a $100 trade = $5 gone before gas.
- For small trades on Ethereum mainnet, total fees (gas + tax + slippage) can exceed the trade value. Flag this to the user.

### Broadcasting with swap-send (Complete CLI Flow)

The `swap-send` command broadcasts a **signed** raw transaction via BGW's MEV-protected endpoint. This is the final step in the swap flow.

**Command format:**
```bash
python3 scripts/bitget_api.py swap-send --chain <chain> --txs "<id>:<chain>:<from_address>:<signed_raw_tx>"
```

**Parameter breakdown:**
- `--chain`: Chain name (e.g., `bnb`, `eth`, `sol`)
- `--txs`: One or more transaction strings in format `id:chain:from:rawTx`
  - `id`: Transaction identifier (use a unique string, e.g., `tx1` or a UUID)
  - `chain`: Chain name again (must match `--chain`)
  - `from`: The sender's wallet address
  - `rawTx`: The **signed** raw transaction hex (with `0x` prefix for EVM)

**Complete swap flow using only CLI commands:**
```bash
# Step 1: Get quote
python3 scripts/bitget_api.py swap-quote \
  --from-chain bnb --from-contract 0x55d398326f99059fF775485246999027B3197955 \
  --to-contract 0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d \
  --amount 0.1

# Step 2: Get calldata (use market value from step 1 response)
python3 scripts/bitget_api.py swap-calldata \
  --from-chain bnb --from-contract 0x55d398326f99059fF775485246999027B3197955 \
  --to-contract 0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d \
  --amount 0.1 --from-address <wallet> --to-address <wallet> \
  --market bgwevmaggregator

# Step 3: Sign the calldata externally (wallet app, web3.py, etc.)
# This produces a signed raw transaction hex

# Step 4: Broadcast
python3 scripts/bitget_api.py swap-send --chain bnb \
  --txs "tx1:bnb:<wallet_address>:<signed_raw_tx_hex>"
```

**Key points:**
- The colon (`:`) is the delimiter in `--txs`. Since EVM raw transactions don't contain colons, this format is safe.
- Multiple transactions can be sent at once: `--txs "tx1:..." "tx2:..."`
- The endpoint is MEV-protected — transactions are sent through a private mempool to avoid front-running.
- A successful broadcast returns a transaction hash, but **success ≠ confirmed**. The transaction still needs to be mined/confirmed on-chain.

### Common Pitfalls

1. **Wrong chain code**: Use `sol` not `solana`, `bnb` not `bsc`. See the Chain Identifiers table below.
2. **Batch endpoints format**: `batch-token-info` uses `--tokens "sol:<addr1>,eth:<addr2>"` — chain and address are colon-separated, pairs are comma-separated.
3. **Liquidity pools**: The `liquidity` command returns pool info including LP lock percentage. 100% locked LP is generally a positive signal; 0% means the creator can pull liquidity.
4. **Stale quotes**: If more than ~30 seconds pass between getting a quote and executing, prices may have moved. Re-quote for time-sensitive trades.
5. **Insufficient gas**: A swap can fail silently if the wallet lacks native tokens for gas. The transaction still consumes gas fees even when it reverts. Check balance before proceeding.
6. **Missing token approval (EVM)**: On EVM chains, forgetting to approve the token for the router is the #1 cause of failed swaps. The transaction will revert on-chain and waste gas. See "EVM Token Approval" section above.
7. **Automate the boring parts**: Run security/liquidity/quote checks silently. Only surface results to the user in the final confirmation summary unless something is wrong.

## Scripts

All scripts are in `scripts/` and use Python 3.11+. No external credential setup needed — demo API keys are built in.

### `scripts/bitget_api.py` — Unified API Client

```bash
# Token info (price, supply, holders, socials)
python3 scripts/bitget_api.py token-info --chain sol --contract <address>

# Token price only
python3 scripts/bitget_api.py token-price --chain sol --contract <address>

# Batch token info (comma-separated)
python3 scripts/bitget_api.py batch-token-info --tokens "sol:<addr1>,eth:<addr2>"

# K-line data
python3 scripts/bitget_api.py kline --chain sol --contract <address> --period 1h --size 24

# Token transaction info (5m/1h/4h/24h volume, buyers, sellers)
python3 scripts/bitget_api.py tx-info --chain sol --contract <address>

# Batch transaction info
python3 scripts/bitget_api.py batch-tx-info --tokens "sol:<addr1>,eth:<addr2>"

# Token rankings (topGainers / topLosers)
python3 scripts/bitget_api.py rankings --name topGainers

# Token liquidity pools
python3 scripts/bitget_api.py liquidity --chain sol --contract <address>

# Historical coins (discover new tokens)
python3 scripts/bitget_api.py history --create-time <timestamp> --limit 20

# Security audit
python3 scripts/bitget_api.py security --chain sol --contract <address>

# Swap quote (amount is human-readable)
python3 scripts/bitget_api.py swap-quote --from-chain sol --from-contract <addr> --to-contract <addr> --amount 1

# Swap calldata (returns tx data for signing; --slippage is optional, system auto-calculates if omitted)
python3 scripts/bitget_api.py swap-calldata --from-chain sol --from-contract <addr> --to-contract <addr> --amount 1 --from-address <wallet> --to-address <wallet> --market <market> --slippage 2

# Swap send (broadcast signed transaction)
python3 scripts/bitget_api.py swap-send --chain sol --raw-transaction <signed_hex>
```

### Chain Identifiers

| Chain | ID | Code |
|-------|------|------|
| Ethereum | 1 | eth |
| Solana | 100278 | sol |
| BNB Chain | 56 | bnb |
| Base | 8453 | base |
| Arbitrum | 42161 | arbitrum |
| Tron | 6 | trx |
| Ton | 100280 | ton |
| Sui | 100281 | suinet |
| Optimism | 10 | optimism |
| Polygon | 137 | matic |

Use empty string `""` for native tokens (ETH, SOL, BNB, etc.).

## Safety Rules

- Built-in demo keys are public; if using custom keys via env vars, avoid exposing them in output
- Swap API uses `Partner-Code: bgw_swap_public` header (hardcoded in script)
- Swap calldata is for **information only** — actual signing requires wallet interaction
- For large trades, always show the quote first and ask for user confirmation
- Present security audit results before recommending any token action
