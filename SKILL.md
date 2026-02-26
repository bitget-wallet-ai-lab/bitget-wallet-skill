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

## ⚠️ IMPORTANT: Swap Amount Format

**Swap endpoints (`swap-quote`, `swap-calldata`, `swap-send`) use HUMAN-READABLE amounts, NOT raw/smallest-unit values.**

| ✅ Correct | ❌ Wrong |
|-----------|---------|
| `--amount 0.1` (0.1 USDT) | `--amount 100000000000000000` (this = 100 quadrillion USDT!) |
| `--amount 1` (1 SOL) | `--amount 1000000000` (this = 1 billion SOL!) |

The `toAmount` in responses is also human-readable. This differs from most on-chain APIs which use smallest units (wei, lamports, etc.).

**Market/token endpoints** (`token-info`, `kline`, etc.) are not affected — they don't take amount inputs.

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

# Token rankings (topGainers / topLosers)
python3 scripts/bitget_api.py rankings --name topGainers

# Token liquidity pools
python3 scripts/bitget_api.py liquidity --chain sol --contract <address>

# Security audit
python3 scripts/bitget_api.py security --chain sol --contract <address>

# Swap quote (amount = human-readable, e.g. 1 = 1 SOL, NOT lamports; toAmount likewise)
python3 scripts/bitget_api.py swap-quote --from-chain sol --from-contract <addr> --to-contract <addr> --amount 1

# Swap calldata (returns tx data for signing)
python3 scripts/bitget_api.py swap-calldata --from-chain sol --from-contract <addr> --to-contract <addr> --amount 1 --from-address <wallet> --to-address <wallet> --market <market>
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
