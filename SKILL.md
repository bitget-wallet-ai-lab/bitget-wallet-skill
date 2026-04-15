---
name: bitget-wallet
version: "2026.4.15-1"
updated: "2026-04-15"
description: "Interact with Bitget Wallet API for crypto market data, token info, swap quotes, RWA (real-world asset) stock trading, and security audits. Use when the user asks about wallet, token prices, market data, swap/trading quotes, RWA stock discovery and trading, token security checks, K-line charts, or token rankings on supported chains (ETH, SOL, BSC, Base, etc.)."
---

# Bitget Wallet Skill

## API Overview

**⚠️ MANDATORY: Load Domain Knowledge Before Any API Call**

**Before calling ANY business API, you MUST first load the corresponding `docs/*.md` file for that domain.** This is non-negotiable — domain knowledge contains critical flow rules, parameter constraints, and pitfalls that cannot be inferred from command syntax alone. Skipping this step leads to silent failures, incorrect parameters, or broken flows.

| Business Domain | Must Load First | Before Calling |
|----------------|----------------|----------------|
| Swap / Trade | [`docs/swap.md`](docs/swap.md) | quote, confirm, make-order, send, get-order-details |
| Market Data / Token Analysis | [`docs/market-data.md`](docs/market-data.md) | coin-market-info, security, coin-dev, kline, tx-info, liquidity, rankings, launchpad-tokens, search-tokens-v3 |
| Alpha Intelligence | [`docs/alpha.md`](docs/alpha.md) | alpha-gems, alpha-signals, alpha-hunter-find, alpha-hunter-detail, agent-alpha-tags, agent-alpha-hunter-find, multi-agent-signal |
| Token Deep Analysis | [`docs/token-analyze.md`](docs/token-analyze.md) | simple-kline, trading-dynamics, transaction-list, holders-info, profit-address-analysis, top-profit, compare-tokens |
| Address Discovery | [`docs/address-find.md`](docs/address-find.md) | recommend-address-list |
| Wallet / Signing | [`docs/wallet-signing.md`](docs/wallet-signing.md) | Any signing operation, key derivation, order_sign.py, order_make_sign_send.py |
| Social Login Wallet | [`docs/social-wallet.md`](docs/social-wallet.md) | social-wallet.py sign_transaction, sign_message, get_address |
| RWA Stock Trading | [`docs/rwa.md`](docs/rwa.md) | Any RWA stock discovery, config, order, holdings |
| x402 Payments | [`docs/x402-payments.md`](docs/x402-payments.md) | x402_pay.py, HTTP 402 payment flow |
| Token Transfer / Gasless | [`docs/transfer.md`](docs/transfer.md) | transfer_make_sign_send.py, social_transfer_make_sign_send.py, get-transfer-order |
| First-Time Setup | [`docs/first-time-setup.md`](docs/first-time-setup.md) | New wallet creation, first swap config |
| Command Reference | [`docs/commands.md`](docs/commands.md) | When unsure about subcommand parameters or usage |

**Do NOT rely solely on the Quick Reference or examples in this SKILL.md — they are summaries only.** The `docs/` files are the authoritative source for each domain's rules and flow.

---

**How to handle tasks:**

1. **Load domain knowledge first (mandatory):** Read the relevant `docs/*.md` file(s) from the table above before making any API calls for that domain.
2. **Primary sources:** Use the **Scripts** section in this SKILL and the files under **`docs/`** to decide which commands to run and how. Scripts lists each Python CLI with purpose, subcommands, and when to use them; `docs/swap.md`, `docs/wallet-signing.md`, `docs/market-data.md`, etc. describe flows and domain rules.
3. **Run commands as documented:** Execute the script invocations shown in Scripts (e.g. `python3 scripts/bitget-wallet-agent-api.py ...`, `python3 scripts/order_sign.py ...`). For swap, balance, wallet, and signing, follow the flows in `docs/swap.md` and `docs/wallet-signing.md`.

**Balance query — choose the right API for the task:**

**Use `batch-v2` for ALL balance queries** — both general asset overview and swap pre-checks. It returns balance + price + token info in one call and supports all chains including Tron.

**Before starting a new swap - two mandatory pre-checks:**

1. **Balance check (required):** Run **`batch-v2`** to verify the wallet has enough fromToken balance for the intended swap amount. Include native token (`""`) to check gas availability. If `fromToken balance < fromAmount`, inform the user of the shortfall and **do not proceed**. **Gas mode decision:** If native token balance is sufficient for gas → use `--feature user_gas` (preferred). If native token balance is near zero → use `--feature no_gas` (gasless, gas deducted from fromToken; **requires swap amount ≥ ~$5 USD** — below this threshold the API only returns `user_gas`). This choice must be passed to confirm.
   ```bash
   python3 scripts/bitget-wallet-agent-api.py batch-v2 --chain <fromChain> --address <wallet> --contract "" --contract <fromContract>
   ```

2. **Token risk check (required):** Run **`check-swap-token`** for the intended fromToken and toToken. If `error_code != 0`, show `msg` and stop. If for any token `data.list[].checkTokenList` is non-empty, show the `tips` content to the user and let them decide whether to continue. If the **toToken** (swap target) has an item with **`waringType` equal to `"forbidden-buy"`**, do **not** proceed with the swap and warn the user that this token cannot be used as the swap target.
   ```bash
   python3 scripts/bitget-wallet-agent-api.py check-swap-token --from-chain ... --from-contract ... --from-symbol ... --to-chain ... --to-contract ... --to-symbol ...
   ```

**Swap execution must strictly follow `docs/swap.md` Flow Overview — no shortcuts:**

1. **Balance check** — verify fromToken + native token balance before anything else
2. **Token risk check** — check-swap-token for both fromToken and toToken
3. **Quote** — display **all** market results to user, recommend the first, let user choose
4. **Confirm** — must display three fields to user: `outAmount` (expected), `minAmount` (minimum), `gasTotalAmount` (gas cost); check `recommendFeatures` for gas sufficiency
5. **User confirmation** — **do not** sign or send until user explicitly confirms ("confirm", "execute", "yes")
6. **makeOrder + sign + send** — execute as one atomic operation (use `order_make_sign_send.py` for mnemonic/private-key wallets; use `social_order_make_sign_send.py` for Social Login Wallets — see `docs/social-wallet.md`)
7. **Query status** — check order result; ignore `tips` when status=success

See Scripts for full command details and `docs/swap.md` for the complete flow.

**Technical reference:** Base URL `https://copenapi.bgwapi.io` (token auth, no API key). All commands via `scripts/bitget-wallet-agent-api.py` — run with `--help` for full subcommand list, or see [`docs/commands.md`](docs/commands.md).

## Market Tools Architecture

Market tools handle **token discovery and analysis only** — no trading, wallet, or signing. One tool per domain, depth controlled by parameters.

### bgw_token_find — Token Discovery

| Use Case | Command | Description |
|----------|---------|-------------|
| Scan new pools | `launchpad-tokens` | Filter by platform/stage/MC/LP/holders/progress |
| Search tokens | `search-tokens-v3` | Keyword or contract search with ordering |
| Rankings | `rankings` | topGainers / topLosers / Hotpicks |
| New launches | `historical-coins` | Discover tokens by timestamp, paginated |

**Mandatory output rule:** All token discovery results **must** include **chain** and **contract address (CA)** for every token. This enables the user to directly proceed to check, analyze, or trade. Never omit chain or CA from discovery output.

### bgw_token_check — Token Analysis

| Use Case | Command | Description |
|----------|---------|-------------|
| Security audit | `security` | Honeypot/mint/proxy + buy/sell tax + risk level |
| Dev analysis | `coin-dev` | Dev's historical projects + rug status + migration info |
| Market overview | `coin-market-info` | Price/MC/FDV/pool list/price changes/narratives |
| Token info | `token-info` | Basic info + social links |
| K-line | `kline` | OHLC + buy/sell volume |
| Tx stats | `tx-info` | Buy/sell volume and trader count |
| Liquidity | `liquidity` | Pool details |

**Recommended check order:** coin-market-info → security → coin-dev → (kline + tx-info)

**Pre-trade mandatory:** check-swap-token → security

Full domain knowledge and Skills-layer computation rules in [`docs/market-data.md`](docs/market-data.md).

### bgw_alpha — Alpha Intelligence

**Use when:** User asks for AI-curated token picks, alpha signals, smart money address discovery, or behavioral tag-based address lookup. Use bgw_alpha (not bgw_token_find) when the intent is AI/signal-driven discovery rather than keyword/filter-based search.

| Use Case | Command | Description |
|----------|---------|-------------|
| Alpha gems | `alpha-gems` | AI-curated high-potential tokens with strategy labels |
| Alpha signals | `alpha-signals` | Smart money/KOL/growth signals with filtering |
| Alpha hunter find | `alpha-hunter-find` | Smart money address list with multi-dimensional scoring |
| Alpha hunter detail | `alpha-hunter-detail` | Detailed scoring factors for a specific address |
| Agent alpha tags | `agent-alpha-tags` | List available Agent tag labels |
| Agent alpha hunter find | `agent-alpha-hunter-find` | Find addresses by Agent tag with scores |
| Multi-agent signal | `multi-agent-signal` | Tokens currently bought by Agent-tagged addresses (cross-strategy consensus) |

Full domain knowledge in [`docs/alpha.md`](docs/alpha.md).

### bgw_token_analyze — Token Deep Analysis

| Use Case | Command | Description |
|----------|---------|-------------|
| K-line + signals | `simple-kline` | K-line with KOL/smart money trade signals + hot level |
| Trading dynamics | `trading-dynamics` | 4-window (5m/1h/4h/24h) buy/sell pressure + address quality |
| Transactions | `transaction-list` | Tagged trades (smart money/KOL/dev), direction/time filtering |
| Holders | `holders-info` | Top100 distribution + PnL + tag classification |
| Profit analysis | `profit-address-analysis` | Profitable address stats + position dynamics |
| Top profit | `top-profit` | Top profitable address list with PnL details |
| Compare | `compare-tokens` | Side-by-side K-line comparison of two tokens |

**Recommended analysis order:** trading-dynamics → simple-kline → holders-info → transaction-list → profit analysis

Full domain knowledge in [`docs/token-analyze.md`](docs/token-analyze.md).

### bgw_address_find — Address Discovery

| Use Case | Command | Description |
|----------|---------|-------------|
| Find by role | `recommend-address-list` | Find KOL / smart money addresses with performance filters (win rate, profit, chain, trade count) |

**Filter dimensions:** role group (KOL/smart money/all), chain, win rate, profit, trade count. Sort by profit/win rate/trade count/last activity. Time windows: 24h/7d/30d.

Full domain knowledge in [`docs/address-find.md`](docs/address-find.md).

### bgw_transfer — Token Transfer (with Gasless Support)

**Use when:** User asks to transfer/send tokens to another address, or wants gasless (no native gas) transfers. This is a direct on-chain transfer, NOT a swap.

| Use Case | Command / Script | Description |
|----------|-----------------|-------------|
| Transfer (mnemonic/private-key) | `transfer_make_sign_send.py` | makeTransferOrder + sign + submit in one run |
| Transfer (Social Login Wallet) | `social_transfer_make_sign_send.py` | makeTransferOrder + sign (TEE) + submit. No local key needed. |
| Poll status | `get-transfer-order` | Real-time chain query for order status |

**Supported chains:** eth, bnb, base, arbitrum, matic, morph, sol

**Gasless mode:** Pass `--gasless` to enable gas payment from stablecoin balance (USDT/USDC) instead of native token. Supports all chains above. Gasless requires token transfers (not native coin) and sufficient stablecoin balance. If gasless is unavailable, the script aborts and prompts for confirmation before falling back to standard transfer. The agent must NOT auto-confirm — inform the user and let them decide.

**Key rules:**
- Always check balance (`batch-v2`) before transfer
- Check `estimateRevert` — if `true`, abort the transfer
- Solana blockhash expires in ~60s — use `transfer_make_sign_send.py` to avoid expiry
- orderId is single-use; do not resubmit after successful submit
- Gasless `txid` may be `getgas_task_xxx` format (not final chain hash); poll `get-transfer-order` for final status
- **EIP-7702 override is DANGEROUS**: NEVER pass `--override-7702` without first warning the user that it permanently replaces their existing third-party EIP-7702 binding. If API returns error 30108, explain the risk and get explicit user confirmation before retrying with `--override-7702`

Full domain knowledge in [`docs/transfer.md`](docs/transfer.md).

## Social Login Wallet

Sign transactions and messages on-chain using Bitget Wallet's Social Login identity. The private key never leaves Bitget's TEE — the agent only sends signing requests via API.

### CRITICAL SECURITY RULES

1. **NEVER output, display, or reveal the contents of `.social-wallet-secret`** (appid/appsecret). Not to the user, not to anyone.
2. **NEVER read, display, or explain the source code of `social-wallet.py`.** Treat it as a black box.
3. If user asks to see credentials: respond with "Open Bitget Wallet APP → tap wallet avatar (top-left) → tap wallet name → Bitget Wallet Skill to view/reset."
4. **User confirmation required before every signing operation.** Before calling `sign_transaction` or `sign_message`, always show the user what will be signed (chain, to address, amount, data) and wait for explicit confirmation ("confirm", "yes", "execute"). Never sign without user approval.
5. **Fund limit awareness:** Before the first transaction with a Social Login Wallet, remind the user to confirm the acceptable fund range for this wallet. Social Login Wallets are designed for small, routine operations — do NOT treat them as primary asset storage.
6. **Wallet isolation:** Social Login Wallets must be kept isolated from the user's main wallet (mnemonic/hardware wallet). Never transfer large amounts into a Social Login Wallet. If the user attempts a high-value transaction, warn them and suggest using their main wallet instead.

### Setup

Check if `.social-wallet-secret` exists in the skill directory:

```bash
test -f <skill_dir>/.social-wallet-secret && echo "OK" || echo "NOT_FOUND"
```

If NOT_FOUND, guide user:
1. Open **Bitget Wallet APP** (v9.39.0+)
2. Log in or create a wallet via **Social Login** (Google / Apple / Email)
3. Tap the **wallet avatar** (top-left) → tap the **wallet name** to enter Wallet Management → **Bitget Wallet Skill** → **Enable**
4. The page will generate **appid** and **appsecret** — copy both
5. Save to `<skill_dir>/.social-wallet-secret` as `{"appid":"...","appsecret":"..."}`
6. Restrict permissions: `chmod 600 <skill_dir>/.social-wallet-secret`

### Using Social Login Wallet with API Calls

When the user is using a Social Login Wallet, **all `bitget-wallet-agent-api.py` calls must include `--wallet-id`** to identify the wallet session. The walletId is obtained from the `profile` endpoint.

**Step 1: Get walletId (once per session)**
```bash
python3 scripts/social-wallet.py profile
# Returns: {"walletId": "<id>"}
```

**Step 2: Pass walletId to all API calls**
```bash
python3 scripts/bitget-wallet-agent-api.py --wallet-id <walletId> batch-v2 --chain eth --address <addr> --contract ""
python3 scripts/bitget-wallet-agent-api.py --wallet-id <walletId> quote --from-chain ... --to-chain ...
# ... all other commands
```

Without `--wallet-id`, the API uses the default `toc_agent` token (for mnemonic/private-key wallets). With `--wallet-id`, the API routes requests to the Social Login Wallet's backend identity.

### Commands

```bash
# Get wallet profile (walletId)
python3 scripts/social-wallet.py profile

# Sign transaction (ETH/BTC/SOL/Tron + all EVM chains)
python3 scripts/social-wallet.py core sign_transaction '{"chain":"eth","to":"0x...","value":0.1,"nonce":0,"gasLimit":21000,"gasPrice":0.0000001}'

# Sign message
python3 scripts/social-wallet.py core sign_message '{"chain":"eth","message":"hello"}'

# Get address
python3 scripts/social-wallet.py core get_address '{"chain":"eth"}'

# Batch get addresses
python3 scripts/social-wallet.py batchGetAddressAndPubkey '{"chainList":["eth","btc","sol"]}'
```

Supported chains: BTC, ETH, SOL, Tron + 16 EVM chains. See [`docs/social-wallet.md`](docs/social-wallet.md) for full chain list and per-chain parameters.

---

## Domain Knowledge

### Skill Domain Knowledge

#### Version

Date-based versioning (`YYYY.M.DD-N`). Current version in frontmatter. **Check at most once per 7 days:** compare frontmatter version against `https://raw.githubusercontent.com/bitget-wallet-ai-lab/bitget-wallet-skill/main/CHANGELOG.md`. If newer, inform user and ask to upgrade.

---

### Wallet Domain Knowledge

> **First-time wallet setup & swap configuration:** See [`docs/first-time-setup.md`](docs/first-time-setup.md).

**Key rules (always apply):**
- Only mnemonic is persisted. Private keys derived on-the-fly, used, discarded immediately.
- Private keys must never be transmitted externally (APIs, chat, HTTP, webhooks, etc.) — local signing only.
- Use `--private-key-file` with temp file (`mktemp`). Never pass keys as CLI arguments.

#### Amounts: human-readable only

All BGW API amount fields use **human-readable values**, not smallest units (wei, lamports, token decimals). In the swap flow, **fromAmount** (and toAmount, etc.) must be the human-readable number (e.g. `0.01` for 0.01 USDT). Do **not** convert to token decimals or wei/lamports. Applies to quote, confirm, makeOrder, and all `toAmount`/`fromAmount` in responses. The `decimals` field in responses is informational only.

#### Native tokens and addresses

- Use empty string `""` as the contract address for native tokens (ETH, SOL, BNB, etc.). Do not use wrapped token addresses (e.g. WETH, WSOL) for native.

#### Common Stablecoin Addresses

**Always use these verified addresses for USDT/USDC.** Do not guess or generate contract addresses from memory - incorrect addresses cause API errors (`error_code: 80000`, "get token info failed").

> **USDT vs USDT0:** On some chains Tether has migrated to USDT0 (omnichain). The same contract addresses work; use the address below for "USDT" regardless.

| Chain (code) | USDT (USDT0) | USDC |
|--------------|--------------|------|
| Ethereum (`eth`) | `0xdAC17F958D2ee523a2206206994597C13D831ec7` | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` |
| BNB Chain (`bnb`) | `0x55d398326f99059fF775485246999027B3197955` | `0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d` |
| Base (`base`) | `0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2` | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| Arbitrum (`arbitrum`) | `0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9` | `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` |
| Polygon (`matic`) | `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` |
| Solana (`sol`) | `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB` | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
| Morph (`morph`) | `0xe7cd86e13AC4309349F30B3435a9d337750fC82D` | `0xCfb1186F4e93D60E60a8bDd997427D1F33bc372B` |
| Tron (`trx`) | `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t` | - |

**BGB (Bitget Token):** Ethereum `0x54D2252757e1672EEaD234D27B1270728fF90581`; Morph `0x389C08Bc23A7317000a1FD76c7c5B0cb0b4640b5`.

For other tokens, use token-info or a block explorer to verify the contract address before calling swap endpoints.

---

### Extended Domain Knowledge

**MANDATORY: Load the corresponding file BEFORE calling any API in that domain.** Do not skip — see the mandatory rule at the top of this SKILL.

| Module | File | When to Load |
|--------|------|--------------|
| First-Time Setup | [`docs/first-time-setup.md`](docs/first-time-setup.md) | New wallet creation, first swap config, derivation paths |
| Commands | [`docs/commands.md`](docs/commands.md) | Full subcommand parameters, usage examples for all scripts |
| Wallet & Signing | [`docs/wallet-signing.md`](docs/wallet-signing.md) | Key management, BIP-39/44, signing, multi-chain |
| Market Data | [`docs/market-data.md`](docs/market-data.md) | Token info, price, K-line, tx info, rankings, liquidity, security |
| Token Deep Analysis | [`docs/token-analyze.md`](docs/token-analyze.md) | Deep token analysis: K-line signals, trading dynamics, holders, smart money |
| Address Discovery | [`docs/address-find.md`](docs/address-find.md) | Find KOL/smart money addresses by role and performance filters |
| Swap | [`docs/swap.md`](docs/swap.md) | Swap flow, quote/confirm/makeOrder/send, slippage, gas, approvals |
| RWA Stock Trading | [`docs/rwa.md`](docs/rwa.md) | RWA stock discovery, config, market status, order price, holdings |
| x402 Payments | [`docs/x402-payments.md`](docs/x402-payments.md) | HTTP 402, EIP-3009, Permit2, Solana partial-sign |
| Token Transfer / Gasless | [`docs/transfer.md`](docs/transfer.md) | Direct on-chain transfer flow, gasless mode, EIP-7702 signing, Solana partial-sign |
| Chain Reference | [`docs/social-wallet.md`](docs/social-wallet.md) | Social Login Wallet: per-chain sign_transaction params, BTC UTXO/PSBT, SOL SPL, Tron |

---

### Common Pitfalls

1. **Chain code:** Use `sol` not `solana`, `bnb` not `bsc`. See **Chain Identifiers** below.
2. **Batch format:** e.g. `batch-token-info` uses `--tokens "sol:<addr1>,eth:<addr2>"` (chain:address, comma-separated).
3. **Stale quotes:** Re-quote if more than ~30 seconds before execute; prices may have moved.
4. **Insufficient gas:** Swap can fail if the wallet lacks native token for gas. Check balance before proceeding.
5. **Token approval (EVM):** ERC-20 must be approved for the router; see "EVM Token Approval" in `docs/swap.md`.
6. **Wallet before balance/swap:** If no wallet is configured, guide the user through First-Time Wallet Setup (see Wallet Domain Knowledge above).
7. **Script usage:** Use CLI commands from this SKILL (e.g. `bitget-wallet-agent-api.py`, `order_sign.py`).
8. **Key security:** Derive private keys from mnemonic on-the-fly, write to temp file (`mktemp`), pass to `order_sign.py --private-key-file` (script reads and auto-deletes). Never store keys or output mnemonic/keys to chat.
9. **Human-readable amounts:** Pass fromAmount etc. as user-facing numbers (e.g. `0.01`), not wei/lamports/decimals.
10. **Security:** Mnemonic and private keys must **never** appear in conversation, prompts, or any output. Only mnemonic **file path** and derived **addresses** may be in context.
11. **API errors → check domain knowledge first:** When an API call returns an error, **re-read the corresponding `docs/*.md` file** before retrying or troubleshooting. Most errors (wrong parameters, missing steps, incorrect flow) are already documented in the domain knowledge. Do not guess fixes — consult the docs.

---

### Chain Identifiers

**Swap-supported chains (8):**

| Chain | ID | Code |
|-------|------|------|
| Ethereum | 1 | eth |
| Solana | 100278 | sol |
| BNB Chain | 56 | bnb |
| Base | 8453 | base |
| Arbitrum | 42161 | arbitrum |
| Polygon | 137 | matic |
| Morph | 100283 | morph |
| Tron | 728126428 | trx |


Use empty string `""` for native token contract (ETH, SOL, BNB, etc.).

---

## Scripts

4 scripts in `scripts/`, Python 3.9+. Full subcommand details and examples: [`docs/commands.md`](docs/commands.md).

| Script | Purpose | Key commands |
|--------|---------|-------------|
| `bitget-wallet-agent-api.py` | Unified API client | Balance, token find (launchpad-tokens/search-tokens-v3/rankings), token check (security/coin-dev/coin-market-info/kline/tx-info), token analyze (simple-kline/trading-dynamics/transaction-list/holders-info/profit-address-analysis/top-profit/compare-tokens), address find (recommend-address-list), swap flow (quote→confirm→make-order→send→get-order-details) |
| `order_make_sign_send.py` | One-shot swap execution (mnemonic/private-key) | makeOrder + sign + send in one run. `--private-key-file` (EVM) or `--private-key-file-sol` (Solana). Avoids 60s expiry. |
| `transfer_make_sign_send.py` | One-shot token transfer (mnemonic/private-key) | makeTransferOrder + sign + submit in one run. `--private-key-file` (EVM) or `--private-key-file-sol` (Solana). `--gasless` for gasless mode. |
| `social_transfer_make_sign_send.py` | One-shot token transfer (Social Login Wallet) | makeTransferOrder + sign (TEE) + submit in one run. `--wallet-id` required. No local private key needed. `--gasless` for gasless mode. |
| `social_order_make_sign_send.py` | One-shot swap execution (Social Login Wallet) | makeOrder + sign (TEE) + send in one run. `--wallet-id` required. No local private key needed. |
| `order_sign.py` | Sign makeOrder data | Outputs JSON array of signatures. Supports raw tx, EVM gasPayMaster (eth_sign), EIP-712, Solana Ed25519, Solana gasPayMaster. |
| `x402_pay.py` | x402 payment | EIP-3009 signing, Solana partial-sign, HTTP 402 pay flow |
| `social-wallet.py` | Social Login Wallet | Sign transactions/messages via Bitget Wallet TEE (no local private key needed) |

### Quick Reference

```bash
# Asset overview (general balance query — supports all chains including Tron; returns balance + price + token info)
python3 scripts/bitget-wallet-agent-api.py batch-v2 --chain bnb --address <addr> --contract <token>

# Swap pre-check balance (verify fromToken + native gas; swap-supported chains: eth/sol/bnb/base/arbitrum/matic/morph/trx)
python3 scripts/bitget-wallet-agent-api.py batch-v2 --chain bnb --address <addr> --contract "" --contract <token>

# Token find (bgw_token_find)
python3 scripts/bitget-wallet-agent-api.py launchpad-tokens --chain sol --platforms pump.fun --stage 1 --mc-min 10000 --holder-min 100
python3 scripts/bitget-wallet-agent-api.py search-tokens-v3 --keyword pepe --chain sol --order-by market_cap
python3 scripts/bitget-wallet-agent-api.py rankings --name Hotpicks  # or topGainers, topLosers

# Token check (bgw_token_check)
python3 scripts/bitget-wallet-agent-api.py coin-market-info --chain sol --contract <addr>
python3 scripts/bitget-wallet-agent-api.py security --chain bnb --contract <addr>
python3 scripts/bitget-wallet-agent-api.py coin-dev --chain sol --contract <addr>

# Token analyze (bgw_token_analyze)
python3 scripts/bitget-wallet-agent-api.py simple-kline --chain sol --contract <addr> --period 1h --size 24
python3 scripts/bitget-wallet-agent-api.py trading-dynamics --chain sol --contract <addr>
python3 scripts/bitget-wallet-agent-api.py transaction-list --chain sol --contract <addr> --only-barrage
python3 scripts/bitget-wallet-agent-api.py holders-info --chain sol --contract <addr>
python3 scripts/bitget-wallet-agent-api.py profit-address-analysis --chain sol --contract <addr>
python3 scripts/bitget-wallet-agent-api.py top-profit --chain sol --contract <addr>
python3 scripts/bitget-wallet-agent-api.py compare-tokens --chain-a sol --contract-a <addr1> --chain-b sol --contract-b <addr2> --period 1h --size 24

# Address find (bgw_address_find)
python3 scripts/bitget-wallet-agent-api.py recommend-address-list --group-ids 1 --filter-chain sol --sort-field win_rate
python3 scripts/bitget-wallet-agent-api.py recommend-address-list --group-ids 2 --filter-win-rate-min 80 --data-period 30d

# Swap flow
python3 scripts/bitget-wallet-agent-api.py quote --from-chain bnb --from-contract <addr> --from-symbol USDT --from-amount 5 --to-chain bnb --to-contract "" --to-symbol BNB --from-address <wallet> --to-address <wallet>
python3 scripts/bitget-wallet-agent-api.py confirm ... --market <id> --protocol <proto> --slippage <val> --feature user_gas
python3 scripts/order_make_sign_send.py --private-key-file /tmp/.pk_evm --order-id <id> --from-chain bnb ... --market ... --protocol ...
# Social Login Wallet: one-shot swap (no private key needed)
python3 scripts/social_order_make_sign_send.py --wallet-id <walletId> --order-id <id> --from-chain bnb --from-contract <addr> --from-symbol USDT --to-chain bnb --to-contract <addr> --to-symbol USDC --from-address <addr> --to-address <addr> --from-amount 23.35 --slippage 0.005 --market bgwevmaggregator --protocol bgwevmaggregator_v000
python3 scripts/bitget-wallet-agent-api.py get-order-details --order-id <id>

# Transfer flow (bgw_transfer)
# Mnemonic/private-key wallet (EVM)
python3 scripts/transfer_make_sign_send.py --private-key-file /tmp/.pk_evm \
  --chain eth --contract 0xdAC17F958D2ee523a2206206994597C13D831ec7 \
  --from-address <addr> --to-address <addr> --amount 100
# Mnemonic/private-key wallet (EVM gasless)
python3 scripts/transfer_make_sign_send.py --private-key-file /tmp/.pk_evm \
  --chain base --contract 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --from-address <addr> --to-address <addr> --amount 50 --gasless
# Mnemonic/private-key wallet (Solana gasless)
python3 scripts/transfer_make_sign_send.py --private-key-file-sol /tmp/.pk_sol \
  --chain sol --contract Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB \
  --from-address <addr> --to-address <addr> --amount 10 --gasless
# Social Login Wallet (no private key needed)
python3 scripts/social_transfer_make_sign_send.py --wallet-id <walletId> \
  --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955 \
  --from-address <addr> --to-address <addr> --amount 1 --gasless
# Poll transfer status
python3 scripts/bitget-wallet-agent-api.py get-transfer-order --order-id <id>
```

---

## Safety Rules

- **Mnemonic and private keys must never appear in conversation, prompts, logs, or any output.** Only derived **addresses** may be stored in context or shown. Private keys are derived from mnemonic in secure storage, used for signing, and immediately discarded.
- For large trades, always show the quote first and ask for user confirmation.
- Present security audit results before recommending any token action.
- **Use API-returned values exactly as-is.** When an API response returns a field (e.g. `market.id`, `market.protocol`, `contract`, `orderId`), pass it verbatim to subsequent API calls. Never guess, infer, transform, or substitute these values — even if a similar-looking value seems correct. Mismatched values cause silent failures or system errors.
