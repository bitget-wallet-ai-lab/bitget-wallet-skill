---
name: bitget-wallet
version: "2026.3.12-1"
updated: "2026-03-12"
description: "Wallet Manage, Interact with Bitget Wallet API for crypto market data, token info, swap quotes, and security audits. Use when the user asks about wallet, token prices, market data, swap/trading quotes, token security checks, K-line charts, or token rankings on supported chains (ETH, SOL, BSC, Base, etc.)."
---

# Bitget Wallet Skill

## API Overview

**How to handle tasks:**

1. **Primary sources:** Use the **Scripts** section in this SKILL and the files under **`docs/`** to decide which commands to run and how. Scripts lists each Python CLI with purpose, subcommands, and when to use them; `docs/swap.md`, `docs/wallet-signing.md`, `docs/market-data.md`, etc. describe flows and domain rules.
2. **Run commands as documented:** Execute the script invocations shown in Scripts (e.g. `python3 scripts/bitget_agent_api.py ...`, `python3 scripts/order_sign.py ...`). For swap, balance, wallet, and signing, follow the flows in `docs/swap.md` and `docs/wallet-signing.md`.

**Before starting a new swap — two mandatory pre-checks:**

1. **Balance check (required):** Run **`get-processed-balance`** to verify the wallet has enough fromToken balance for the intended swap amount. Include native token (`""`) to check gas availability. If `fromToken balance < fromAmount`, inform the user of the shortfall and **do not proceed**. If native token balance is near zero, warn about potential gas issues and suggest using gasless mode.
   ```bash
   python3 scripts/bitget_agent_api.py get-processed-balance --chain <fromChain> --address <wallet> --contract "" --contract <fromContract>
   ```

2. **Token risk check (required):** Run **`check-swap-token`** for the intended fromToken and toToken. If `error_code != 0`, show `msg` and stop. If for any token `data.list[].checkTokenList` is non-empty, show the `tips` content to the user and let them decide whether to continue. If the **toToken** (swap target) has an item with **`waringType` equal to `"forbidden-buy"`**, do **not** proceed with the swap and warn the user that this token cannot be used as the swap target.
   ```bash
   python3 scripts/bitget_agent_api.py check-swap-token --from-chain ... --from-contract ... --from-symbol ... --to-chain ... --to-contract ... --to-symbol ...
   ```

See Scripts for full command details and `docs/swap.md` for the complete flow.

**Technical reference (no need to read .py files):**

- **Base URL:** `https://copenapi.bgwapi.io` (token auth, no API key needed).
- **Agent API:** Invoked via `scripts/bitget_agent_api.py`. Covers token risk check (`check-swap-token`), balance (`get-processed-balance`), balance+price (`batch-v2`), token search (`search-tokens`), token list (`get-token-list`); **market data:** token-info, token-price, batch-token-info, kline, tx-info, batch-tx-info, historical-coins, rankings, liquidity, security; swap flow (quote, confirm, make-order, send, get-order-details). Request/response details are in `docs/`.
- **Requests:** POST with JSON body.

## Domain Knowledge

### Skill Domain Knowledge

#### Version Awareness

This skill uses date-based versioning (`YYYY.M.DD`). Each release includes a sequential suffix: `YYYY.M.DD-1`, `YYYY.M.DD-2`, etc. The current version is in the frontmatter above. See `CHANGELOG.md` for full history.

**First-use version check (at most once every 7 days):**

1. Check the installed `version` from frontmatter above.
2. Fetch the latest CHANGELOG from `https://raw.githubusercontent.com/bitget-wallet-ai-lab/bitget-wallet-skill/main/CHANGELOG.md`.
3. Compare with the installed version.

**If a new version is available**, inform the user (installed vs latest, one-line changes, security-related yes/no) and ask "Upgrade? [yes/no]". If the user confirms, re-install the skill from the `main` branch and replace all local skill files; then re-read SKILL.md. Post-upgrade: diff old/new `bitget_agentapi.py`, flag new endpoints/deps/credentials, and run platform security audit if applicable.

**If versions match:** Proceed normally. Check frequency: at most once every 7 days.

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

**Derivation paths:**

| Chain | Path | Curve |
|-------|------|-------|
| EVM (ETH/BNB/Base/...) | `m/44'/60'/0'/0/0` | secp256k1 |
| Solana | `m/44'/501'/0'/0'` | Ed25519 (SLIP-0010) |
| Tron | `m/44'/195'/0'/0/0` | secp256k1 |

#### Amounts: human-readable only

All BGW API amount fields use **human-readable values**, not smallest units (wei, lamports, token decimals). In the swap flow, **fromAmount** (and toAmount, etc.) must be the human-readable number (e.g. `0.01` for 0.01 USDT). Do **not** convert to token decimals or wei/lamports. Applies to quote, confirm, makeOrder, and all `toAmount`/`fromAmount` in responses. The `decimals` field in responses is informational only.

#### Native tokens and addresses

- Use empty string `""` as the contract address for native tokens (ETH, SOL, BNB, etc.). Do not use wrapped token addresses (e.g. WETH, WSOL) for native.

#### Common Stablecoin Addresses

**Always use these verified addresses for USDT/USDC.** Do not guess or generate contract addresses from memory — incorrect addresses cause API errors (`error_code: 80000`, "get token info failed").

> **USDT vs USDT0:** On some chains Tether has migrated to USDT0 (omnichain). The same contract addresses work; use the address below for "USDT" regardless.

| Chain (code) | USDT (USDT0) | USDC |
|--------------|--------------|------|
| Ethereum (`eth`) | `0xdAC17F958D2ee523a2206206994597C13D831ec7` | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` |
| BNB Chain (`bnb`) | `0x55d398326f99059fF775485246999027B3197955` | `0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d` |
| Base (`base`) | `0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2` | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| Arbitrum (`arbitrum`) | `0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9` | `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` |
| Optimism (`optimism`) | `0x94b008aA00579c1307B0EF2c499aD98a8ce58e58` | `0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85` |
| Polygon (`matic`) | `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` |
| Solana (`sol`) | `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB` | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
| Morph (`morph`) | `0xe7cd86e13AC4309349F30B3435a9d337750fC82D` | — (not yet available) |

**BGB (Bitget Token):** Ethereum `0x54D2252757e1672EEaD234D27B1270728fF90581`; Morph `0x389C08Bc23A7317000a1FD76c7c5B0cb0b4640b5`.

For other tokens, use token-info or a block explorer to verify the contract address before calling swap endpoints.

---

### Extended Domain Knowledge

Load the following when the task requires it:

| Module | File | When to Load |
|--------|------|--------------|
| Wallet & Signing | [`docs/wallet-signing.md`](docs/wallet-signing.md) | Key management, BIP-39/44, signing, multi-chain |
| Market Data | [`docs/market-data.md`](docs/market-data.md) | Token info, price, K-line, tx info, rankings, liquidity, security; use `bitget_agent_api.py` subcommands: token-info, token-price, batch-token-info, kline, tx-info, batch-tx-info, historical-coins, rankings, liquidity, security |
| Swap | [`docs/swap.md`](docs/swap.md) | Swap (token swap) flow, quote/confirm/makeOrder/send, slippage, gas, approvals, confirm handling |
| x402 Payments | [`docs/x402-payments.md`](docs/x402-payments.md) | HTTP 402, EIP-3009, Permit2, Solana partial-sign |

---

### Common Pitfalls

1. **Chain code:** Use `sol` not `solana`, `bnb` not `bsc`. See **Chain Identifiers** below.
2. **Batch format:** e.g. `batch-token-info` uses `--tokens "sol:<addr1>,eth:<addr2>"` (chain:address, comma-separated).
3. **Stale quotes:** Re-quote if more than ~30 seconds before execute; prices may have moved.
4. **Insufficient gas:** Swap can fail if the wallet lacks native token for gas. Check balance before proceeding.
5. **Token approval (EVM):** ERC-20 must be approved for the router; see "EVM Token Approval" in `docs/swap.md`.
6. **Wallet before balance/swap:** If no wallet is configured, guide the user through First-Time Wallet Setup (see Wallet Domain Knowledge above).
7. **Script usage:** Use CLI commands from this SKILL (e.g. `bitget_agent_api.py`, `order_sign.py`).
8. **Key security:** Derive private keys from mnemonic on-the-fly, pass to `order_sign.py --private-key`, discard immediately after signing. Never store keys or output mnemonic/keys to chat.
9. **Human-readable amounts:** Pass fromAmount etc. as user-facing numbers (e.g. `0.01`), not wei/lamports/decimals.
10. **Security:** Mnemonic and private keys must **never** appear in conversation, prompts, or any output. Only mnemonic **file path** and derived **addresses** may be in context.

---

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

Use empty string `""` for native token contract (ETH, SOL, BNB, etc.).

---

## Scripts

All scripts are in `scripts/`, Python 3.9+. Each command below states **what it does** and **when to use it**.

---

### `scripts/bitget_agent_api.py` — Balance, token list, swap flow, **market data**, order send, order status

**Purpose:** Calls the Bitget Agent API for: balances and balance+price; token search and token list; **market data** — token info, price, K-line, tx info, rankings, liquidity, security; swap flow (quote → confirm → makeOrder → send); order details. 
**Use for:** Balance checks, balance+price (batch-v2), token search (search-tokens), token list; **when user asks for token info, price, K-line, recent trades, new tokens, rankings, liquidity, or security audit** use the market-data commands below; first/second quote, order create/send, order status.

| Subcommand | What it does | When to use |
|------------|----------------|-------------|
| `check-swap-token` | Checks fromToken and toToken for risks before swap. Pass both tokens via `--from-*`/`--to-*` or `--json-stdin` with `{ "list": [{ chain, contract, symbol }, ...] }`. Returns `data.list[].checkTokenList`; empty = no risk. If any item has `waringType` `"forbidden-buy"`, that token **must not** be used as swap target (toToken). | **Before every new swap:** run this for the intended from and to tokens; if risks are reported, show `tips` to the user; if toToken has `forbidden-buy`, do not proceed and warn. |
| `get-processed-balance` | Returns processed balance(s) for a chain+address, optionally per token (contract `""` = native). Accepts `--chain`/`--address`/`--contract` or JSON body via `--json-stdin`. | User asks for balance; before swap to verify sufficient balance. |
| `batch-v2` | Batch get on-chain balance **and token price** for address(es). Same list format as get-processed-balance: `{ list: [{ chain, address, contract: ["" or contract addrs] }] }`. Returns `data[].list` keyed by contract (empty string = native); each has `balance`, `price`, etc. | When user needs balance **plus** token price in one call (e.g. portfolio value in USD). |
| `search-tokens` | Search on-chain tokens by **keyword or full contract address**. Optional `--chain` to restrict results to one chain (e.g. bnb, eth). Returns `data.list` (name, symbol, chain, contract, price, etc.), `data.showMore`, `data.isContract`. | When user searches for a token by name/symbol or pastes a contract address; use `--chain` when user wants results on a specific chain. |
| `get-token-list` | Returns the list of tokens available for a chain (for swap/quote). | When you need token symbols or contracts for a chain (e.g. to build quote args). |
| **Market data** | | |
| `token-info` | Get single token base info (name, symbol, price, etc.). | User asks for token info by chain+contract. |
| `token-price` | Get single token price (simplified output). | User asks for token price only. |
| `batch-token-info` | Batch get token info. `--tokens` = comma-separated `chain:contract` pairs. | When you need info for multiple tokens in one call. |
| `kline` | Get K-line (OHLC) for a token. `--period` 1s,1m,5m,15m,30m,1h,4h,1d,1w; `--size` max 1440. | User asks for K-line / chart data. See `docs/market-data.md`. |
| `tx-info` | Get recent transaction stats (buy/sell volume, counts) for one token. | User asks for recent trades or tx activity. |
| `batch-tx-info` | Batch get recent tx stats. `--tokens` = comma-separated `chain:contract`. | Multiple tokens' tx stats at once. |
| `historical-coins` | Get recently issued tokens by time. `--create-time` = `YYYY-MM-DD HH:MM:SS`; paginate with response `lastTime`. | User asks for new/launched tokens. |
| `rankings` | Get token rankings. `--name` = e.g. `topGainers`, `topLosers`, or `Hotpicks` (curated trending tokens). | User asks for hot/popular, top gainers/losers, or trending tokens. |
| `liquidity` | Get liquidity pool info for a token. | User asks for liquidity or pool info. |
| `security` | Security audit (highRisk, riskCount, buyTax/sellTax, etc.). | Before swap for unfamiliar tokens; user asks for safety check. See `docs/market-data.md`. |
| `quote` | First quote: returns **multiple market results** in `data.quoteResults`. Agent must **display all** results to the user, **recommend the first**, and allow the user to **choose another** for confirm if they prefer. | Step 1 of swap: show all options; default to first for confirm unless user picks another. |
| `confirm` | Second quote: locks in **one** market (the chosen one from quote), returns `data.orderId` and `data.quoteResult`. Use market/protocol/slippage from the **selected** quote result (default first; or the item user chose). | Step 2 of swap: get orderId and latest quoteResult for makeOrder/send using the user’s chosen market. |
| `make-order` | Creates order; returns unsigned `data.txs` (expires ~60s). | Step 3 of swap: get unsigned txs for signing. |
| `send` | Submits signed order: body is `{ "orderId", "txs" }` with `txs[].sig` filled. Input via `--json-stdin` or `--json-file`. | After signing makeOrder txs via `order_sign.py`. |
| `get-order-details` | Returns order status and result (e.g. `data.details.status`, `fromTxId`, `toTxId`). | After send: show user whether swap succeeded and tx links. |

```bash
# Token risk check before swap (run for from + to tokens; if error_code != 0 show msg and stop; if checkTokenList non-empty show tips; if toToken has waringType "forbidden-buy", do not proceed)
python3 scripts/bitget_agent_api.py check-swap-token --from-chain bnb --from-contract <addr> --from-symbol USDT --to-chain bnb --to-contract "" --to-symbol BNB
# Or: echo '{"list":[{"chain":"bnb","contract":"","symbol":"BNB"},{"chain":"bnb","contract":"0x...","symbol":"AIO"}]}' | python3 scripts/bitget_agent_api.py check-swap-token --json-stdin

# Balance (chain + address; contract "" = native, or pass multiple --contract)
python3 scripts/bitget_agent_api.py get-processed-balance --chain bnb --address <wallet_evm> [--contract "" --contract <token_contract>]
echo '{"list":[{"chain":"bnb","address":"0x...","contract":["","0x..."]}]}' | python3 scripts/bitget_agent_api.py get-processed-balance --json-stdin

# Balance + token price (batch-v2; same list format; data[].list has balance and price per contract)
python3 scripts/bitget_agent_api.py batch-v2 --chain bnb --address <wallet_evm> [--contract "" --contract <token_contract>]
echo '{"list":[{"chain":"bnb","address":"0x...","contract":["","0x55d398326f99059ff775485246999027b3197955"]}]}' | python3 scripts/bitget_agent_api.py batch-v2 --json-stdin

# Search tokens by keyword or contract address (optional --chain to restrict to one chain)
python3 scripts/bitget_agent_api.py search-tokens --keyword USDT
python3 scripts/bitget_agent_api.py search-tokens --keyword USDT --chain bnb
python3 scripts/bitget_agent_api.py search-tokens --keyword 0x55d398326f99059ff775485246999027b3197955

# Token list for a chain
python3 scripts/bitget_agent_api.py get-token-list --chain bnb

# Market data: token info, price, K-line, tx info, rankings, liquidity, security
python3 scripts/bitget_agent_api.py token-info --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955
python3 scripts/bitget_agent_api.py token-price --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955
python3 scripts/bitget_agent_api.py batch-token-info --tokens "bnb:0x55d398326f99059fF775485246999027B3197955,eth:0xdAC17F958D2ee523a2206206994597C13D831ec7"
python3 scripts/bitget_agent_api.py kline --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955 --period 1h --size 24
python3 scripts/bitget_agent_api.py tx-info --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955
python3 scripts/bitget_agent_api.py batch-tx-info --tokens "bnb:0x...,eth:0x..."
python3 scripts/bitget_agent_api.py historical-coins --create-time "2026-02-27 00:00:00" --limit 20
python3 scripts/bitget_agent_api.py rankings --name topGainers    # or topLosers, Hotpicks
python3 scripts/bitget_agent_api.py liquidity --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955
python3 scripts/bitget_agent_api.py security --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955

# 1. First quote (fromAmount human-readable, e.g. 0.01). Show ALL data.quoteResults to user; recommend first; user may choose another for confirm
python3 scripts/bitget_agent_api.py quote --from-address <wallet> --from-chain bnb --from-symbol USDT --from-contract <usdt_addr> --from-amount 0.01 --to-chain bnb --to-symbol BNB --to-contract ""

# 2. Second quote: use market/protocol/slippage from chosen quote result (default quoteResults[0], or the one user selected)
python3 scripts/bitget_agent_api.py confirm --from-chain bnb --from-symbol USDT --from-contract <addr> --from-amount 0.01 --from-address <wallet> --to-chain bnb --to-symbol BNB --to-contract "" --to-address <wallet> --market <chosen market.id> --protocol <chosen market.protocol> --slippage <chosen slippageInfo.recommendSlippage>

# 3–5. makeOrder + sign + send (one run; requires mnemonic path and addresses from context)
# 3. makeOrder → sign → send (separate steps; sign+send must complete within ~60s of makeOrder)
python3 scripts/bitget_agent_api.py make-order --order-id <from_confirm> --from-chain bnb --from-contract <addr> --from-symbol USDT --to-chain bnb --to-contract "" --to-symbol BNB --from-address <wallet> --to-address <wallet> --from-amount 0.01 --slippage 1.00 --market bgwevmaggregator --protocol bgwevmaggregator_v000 > /tmp/makeorder.json
python3 scripts/order_sign.py --order-json "$(cat /tmp/makeorder.json)" --private-key <hex_key> > /tmp/sigs.json
# Fill txs[i].sig from sigs array, then send

# 6. Order status
python3 scripts/bitget_agent_api.py get-order-details --order-id <orderId>
```


---

### `scripts/order_sign.py` — Sign order/makeOrder transaction data

**Purpose:** Takes makeOrder response JSON (stdin or `--order-json`), signs `data.txs` with the given private key, outputs a JSON array of signature hex strings. Agent must then fill `txs[i].sig` and call `bitget_agent_api.py send`.

| When to use | Notes |
|--------------|-------|
| You have makeOrder response and need to sign. | Pipe makeOrder full response into stdin; pass `--private-key` (EVM). Output = list of hex strings; set `data.txs[i].sig` and send. Derive private key from mnemonic in secure storage; discard after signing. |

```bash
echo '<makeOrder_full_response_json>' | python3 scripts/order_sign.py --private-key <hex>
```

---

### `scripts/x402_pay.py` — x402 payment signing and pay flow

**Purpose:** Signs or performs HTTP 402 payment flows (pay for API access with crypto). **Use for:** EIP-3009 USDC payments, Solana partial-sign for x402, or full pay flow when the user pays for a 402-protected URL.

| Subcommand | What it does | When to use |
|------------|----------------|-------------|
| `sign-eip3009` | Signs an EIP-3009 transfer (e.g. USDC on Base) for a given token, chain, recipient, amount. | When the payee expects an EIP-3009 signature for 402 payment. |
| `sign-solana` | Partially signs a Solana transaction (base64) for x402. | When the payee expects a Solana partial signature. |
| `pay` | Auto-detects 402 response, signs appropriately, and pays; then fetches the protected resource. | User wants to "pay and access" a URL that returns HTTP 402. |

```bash
python3 scripts/x402_pay.py sign-eip3009 --private-key <hex> --token <usdc> --chain-id 8453 --to <payTo> --amount 10000
python3 scripts/x402_pay.py sign-solana --private-key <hex> --transaction <base64_tx>
python3 scripts/x402_pay.py pay --url https://api.example.com/data --private-key <hex>
```

---

## Safety Rules

- **Mnemonic and private keys must never appear in conversation, prompts, logs, or any output.** Only derived **addresses** may be stored in context or shown. Private keys are derived from mnemonic in secure storage, used for signing, and immediately discarded.
- Built-in demo keys are public; if using custom keys via env vars, avoid exposing them in output.
- For large trades, always show the quote first and ask for user confirmation.
- Present security audit results before recommending any token action.
