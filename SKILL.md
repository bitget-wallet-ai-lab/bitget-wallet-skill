---
name: bitget-wallet
description: "Interact with Bitget Wallet ToB API for crypto market data, token info, swap quotes, and security audits. Use when the user asks about token prices, market data, swap/trading quotes, token security checks, K-line charts, or token rankings on supported chains (ETH, SOL, BSC, Base, etc.)."
---

# Bitget Wallet ToB API

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

### Common Pitfalls

1. **Wrong chain code**: Use `sol` not `solana`, `bnb` not `bsc`. See the Chain Identifiers table below.
2. **Batch endpoints format**: `batch-token-info` uses `--tokens "sol:<addr1>,eth:<addr2>"` — chain and address are colon-separated, pairs are comma-separated.
3. **Liquidity pools**: The `liquidity` command returns pool info including LP lock percentage. 100% locked LP is generally a positive signal; 0% means the creator can pull liquidity.

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

# Swap calldata (returns tx data for signing)
python3 scripts/bitget_api.py swap-calldata --from-chain sol --from-contract <addr> --to-contract <addr> --amount 1 --from-address <wallet> --to-address <wallet> --market <market>

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

Use empty string `""` for native tokens (ETH, SOL, BNB, etc.).

## Safety Rules

- Built-in demo keys are public; if using custom keys via env vars, avoid exposing them in output
- Swap API uses `Partner-Code: bgw_swap_public` header (hardcoded in script)
- Swap calldata is for **information only** — actual signing requires wallet interaction
- For large trades, always show the quote first and ask for user confirmation
- Present security audit results before recommending any token action
