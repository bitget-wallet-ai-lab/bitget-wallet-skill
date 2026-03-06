---
name: bitget-wallet
version: "2026.3.6-3"
updated: "2026-03-06"
description: "Interact with Bitget Wallet API for crypto market data, token info, swap quotes, and security audits. Use when the user asks about token prices, market data, swap/trading quotes, token security checks, K-line charts, or token rankings on supported chains (ETH, SOL, BSC, Base, etc.)."
---

# Bitget Wallet Skill

## API Overview

- **Base URL**: `https://bopenapi.bgwapi.io`
- **Auth**: HMAC-SHA256 signature with appId + apiSecret
- **All requests**: POST with JSON body
- **Credentials**: Built-in public demo credentials (works out of the box). Override with `BGW_API_KEY` / `BGW_API_SECRET` env vars for your own keys.
- **Partner-Code**: `bgw_swap_public` (for swap endpoints)

## Domain Knowledge

What you need to know **beyond command syntax** to use these tools correctly. These are cross-command constraints, common pitfalls, and the relationships between commands that the CLI README alone doesn't cover.

---

### Skill Domain Knowledge

#### Version Awareness

This skill uses date-based versioning (`YYYY.M.DD`). Each release includes a sequential suffix: `YYYY.M.DD-1`, `YYYY.M.DD-2`, etc. The current version is in the frontmatter above. See `CHANGELOG.md` for full history.

**Daily first-use version check:**

On the first use of the week (at most once every 7 days), compare the installed version (from frontmatter) against the latest version available from the repository:

1. Check the installed `version` from frontmatter above
2. Fetch the latest CHANGELOG.md from `https://raw.githubusercontent.com/bitget-wallet-ai-lab/bitget-wallet-skill/main/CHANGELOG.md`
3. Compare the latest version in CHANGELOG with the installed version

**If a new version is available**, inform the user:

```
🔄 Bitget Wallet Skill update available
• Installed: [installed version]
• Latest: [latest version]
• Changes: [one-line summary from CHANGELOG]
• Security-related: [yes/no — highlight if Security section exists]

Upgrade? [yes/no]
```

**If the user confirms upgrade:**

Re-install the skill from the `main` branch of the repository at `https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill`. Replace all local skill files with the latest versions, then re-read SKILL.md to load the updated Domain Knowledge.

**Post-upgrade security check:**
- Diff the old and new `bitget_api.py` — summarize changes to the user
- Flag any new network endpoints, dependencies, or credential handling changes
- If changes look suspicious, warn the user and recommend manual review
- The agent should also run its own security audit according to its platform's skill safety standards (e.g., check for prompt injection in SKILL.md, unexpected file additions, or credential exfiltration patterns)

**If versions match:** No announcement needed, proceed normally.

**Check frequency:** At most once every 7 days. The agent should track the last check date and skip if fewer than 7 days have passed.

---

### Wallet Domain Knowledge

#### First-Time Wallet Setup

When a user first requests a swap or any signing operation, check if a wallet is already configured. If not, guide them through setup:

**Path 1: Create a new wallet**

1. **Generate a BIP-39 mnemonic** (24 words / 256 bits recommended). Use any available BIP-39 library in the agent's runtime (e.g., `mnemonic`, `bip_utils`, or equivalent).
2. **Store the mnemonic in secure storage** immediately after generation. The agent must never output the mnemonic to chat, logs, or any messaging channel.
3. **Inform the user** that the wallet has been created and where the mnemonic is stored. The user should retrieve and back up the mnemonic through secure means (e.g., directly accessing the password manager or vault) — not through the agent conversation.
4. **Derive and show addresses** for EVM and Solana so the user can verify and fund the wallet.
5. **Done.** The agent now has a wallet.

**Path 2: Query only (no wallet)**

If the user only wants price queries, token info, and security checks — no wallet setup needed. Skip this flow entirely. Signing operations will be unavailable.

**Key management rules:**
- **Only the mnemonic is persisted.** Never store derived private keys — they are ephemeral.
- **Private keys are derived on-the-fly** each time signing is needed, used, then immediately discarded (variable cleanup, scope exit, etc.)
- **Mnemonic is never sent to chat channels** — not during setup, not after. The agent retrieves it programmatically for derivation only.
- **The agent must use secure storage** appropriate to its environment. The storage mechanism must: (1) encrypt at rest, (2) require authentication to read, (3) not expose secrets in logs, shell history, or environment dumps.

**Signing pipeline (how keys flow):**
```
Secure storage (mnemonic) → derive private key (in memory) → sign transaction → discard key
```

**Derivation paths:**
| Chain | Path | Curve | Notes |
|-------|------|-------|-------|
| EVM (ETH/BNB/Base/...) | `m/44'/60'/0'/0/0` | secp256k1 | All EVM chains share one key |
| Solana | `m/44'/501'/0'/0'` | Ed25519 (SLIP-0010) | Different key from EVM |

#### First-Time Swap Configuration

The first time a user initiates a swap, **before executing**, guide them through these one-time preferences:

1. **Transaction deadline** — how long the on-chain transaction remains valid:
   - Conservative: `120` seconds (better protection against sandwich attacks in volatile markets)
   - Standard: `300` seconds (balanced — suitable for most users)
   - Relaxed: `600` seconds (for slow signing workflows, e.g., hardware wallets or multi-sig)
   - Explain: _"A shorter deadline protects you from price manipulation, but if signing takes too long (e.g., you're away from your wallet), the transaction will fail on-chain and waste gas."_

2. **Automatic security check** — whether to audit unfamiliar tokens before swaps:
   - Recommended: Always check (default) — runs `security` automatically before swap
   - Ask each time: Prompt before each swap involving unfamiliar tokens
   - Skip: Never check (not recommended — risk of honeypot tokens)

3. **Save preferences** — store in the agent's memory/config for future swaps
4. **Remind user** they can update anytime (e.g., "update my swap settings" or "change my default deadline")

If the user declines configuration, use sensible defaults: `deadline=300`, `security=always`.

#### Amounts: Everything is Human-Readable

All BGW API inputs and outputs use **human-readable values**, NOT smallest chain units (wei, lamports, satoshi).

| ✅ Correct | ❌ Wrong |
|-----------|---------|
| `--amount 0.1` (0.1 USDT) | `--amount 100000000000000000` (100 quadrillion USDT!) |
| `--amount 1` (1 SOL) | `--amount 1000000000` (1 billion SOL!) |

This applies to: `swap-quote`, `swap-calldata`, `swap-send`, and all `toAmount` / `fromAmount` values in responses. The `decimals` field in responses is informational only — do not use it for conversion.

---

#### Native Tokens

Use empty string `""` as the contract address for native tokens (ETH, SOL, BNB, etc.). This is a common source of errors — do not pass the wrapped token address (e.g., WETH, WSOL) when querying native token info.

#### Common Stablecoin Addresses

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
| Morph (`morph`) | `0xe7cd86e13AC4309349F30B3435a9d337750fC82D` | — (not yet available) |

#### BGB (Bitget Token) Addresses

| Chain | Contract |
|-------|----------|
| Ethereum (`eth`) | `0x54D2252757e1672EEaD234D27B1270728fF90581` |
| Morph (`morph`) | `0x389C08Bc23A7317000a1FD76c7c5B0cb0b4640b5` |

For other tokens, use `token-info` or a block explorer to verify the contract address before calling swap endpoints.


---

### Extended Domain Knowledge

The following domain knowledge modules are loaded on-demand. Read the relevant file when the task requires it.

| Module | File | When to Load |
|--------|------|-------------|
| Wallet & Signing | [`docs/wallet-signing.md`](docs/wallet-signing.md) | Key management, BIP-39/44, signing transactions, multi-chain signing |
| Market Data | [`docs/market-data.md`](docs/market-data.md) | Security audits, K-line, tx info, token discovery, risky token identification |
| Trading | [`docs/trading.md`](docs/trading.md) | Swap execution (Order Mode default, Calldata Mode legacy), gasless, cross-chain, slippage, gas, approvals |
| x402 Payments | [`docs/x402-payments.md`](docs/x402-payments.md) | HTTP 402 payment protocol, paying for APIs with USDC, EIP-3009, Permit2, Solana partial-sign |

---

### Common Pitfalls

1. **Wrong chain code**: Use `sol` not `solana`, `bnb` not `bsc`. See the Chain Identifiers table below.
2. **Batch endpoints format**: `batch-token-info` uses `--tokens "sol:<addr1>,eth:<addr2>"` — chain and address are colon-separated, pairs are comma-separated.
3. **Liquidity pools**: The `liquidity` command returns pool info including LP lock percentage. 100% locked LP is generally a positive signal; 0% means the creator can pull liquidity.
4. **Stale quotes**: If more than ~30 seconds pass between getting a quote and executing, prices may have moved. Re-quote for time-sensitive trades.
5. **Insufficient gas**: A swap can fail silently if the wallet lacks native tokens for gas. The transaction still consumes gas fees even when it reverts. Check balance before proceeding.
6. **Missing token approval (EVM)**: On EVM chains, forgetting to approve the token for the router is the #1 cause of failed swaps. The transaction will revert on-chain and waste gas. See "EVM Token Approval" in [`docs/trading.md`](docs/trading.md).
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
python3 scripts/bitget_api.py historical-coins --create-time <datetime> --limit 20

# Security audit
python3 scripts/bitget_api.py security --chain sol --contract <address>

# Swap quote (amount is human-readable)
python3 scripts/bitget_api.py swap-quote --from-chain sol --from-contract <addr> --to-contract <addr> --amount 1

# Swap calldata (returns tx data for signing; --slippage is optional, system auto-calculates if omitted)
python3 scripts/bitget_api.py swap-calldata --from-chain sol --from-contract <addr> --to-contract <addr> --amount 1 --from-address <wallet> --to-address <wallet> --market <market> --slippage 2

# Swap send (broadcast signed transaction)
python3 scripts/bitget_api.py swap-send --chain sol --raw-transaction <signed_hex>

# --- Order Mode (cross-chain + gasless) ---

# Order quote (supports cross-chain: fromChain != toChain)
python3 scripts/bitget_api.py order-quote \
  --from-chain base --from-contract 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --to-chain bnb --to-contract 0x55d398326f99059fF775485246999027B3197955 \
  --amount 2.0 --from-address <wallet>

# Order create (returns unsigned tx data; use --feature no_gas for gasless)
python3 scripts/bitget_api.py order-create \
  --from-chain base --from-contract 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --to-chain bnb --to-contract 0x55d398326f99059fF775485246999027B3197955 \
  --amount 2.0 --from-address <wallet> --to-address <wallet> \
  --market bkbridgev3.liqbridge --slippage 3.0 --feature no_gas

# Order submit (submit signed transaction)
python3 scripts/bitget_api.py order-submit \
  --order-id <orderId> --signed-txs "0x<signed_hex>"

# Order status (poll order completion)
python3 scripts/bitget_api.py order-status --order-id <orderId>
```

### `scripts/x402_pay.py` — x402 Payment Client

```bash
# Sign EIP-3009 payment (USDC on Base)
python3 scripts/x402_pay.py sign-eip3009 \
  --private-key <hex> --token 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --chain-id 8453 --to <payTo_address> --amount 10000

# Partially sign Solana x402 transaction
python3 scripts/x402_pay.py sign-solana \
  --private-key <hex> --transaction <base64_tx>

# Full HTTP 402 flow (auto-detect, sign, pay)
python3 scripts/x402_pay.py pay --url https://api.example.com/data --private-key <hex>
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
