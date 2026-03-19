---
name: bitget-wallet
version: "2026.3.12-1"
updated: "2026-03-12"
description: "Interact with Bitget Wallet API for crypto market data, token info, swap quotes, RWA (real-world asset) stock trading, and security audits. Use when the user asks about wallet, token prices, market data, swap/trading quotes, RWA stock discovery and trading, token security checks, K-line charts, or token rankings on supported chains (ETH, SOL, BSC, Base, etc.)."
---

# Bitget Wallet Skill

## API Overview

**How to handle tasks:**

1. **Primary sources:** Use the **Scripts** section in this SKILL and the files under **`docs/`** to decide which commands to run and how. Scripts lists each Python CLI with purpose, subcommands, and when to use them; `docs/swap.md`, `docs/wallet-signing.md`, `docs/market-data.md`, etc. describe flows and domain rules.
2. **Run commands as documented:** Execute the script invocations shown in Scripts (e.g. `python3 scripts/bitget_agent_api.py ...`, `python3 scripts/order_sign.py ...`). For swap, balance, wallet, and signing, follow the flows in `docs/swap.md` and `docs/wallet-signing.md`.

**Before starting a new swap - two mandatory pre-checks:**

1. **Balance check (required):** Run **`get-processed-balance`** to verify the wallet has enough fromToken balance for the intended swap amount. Include native token (`""`) to check gas availability. If `fromToken balance < fromAmount`, inform the user of the shortfall and **do not proceed**. **Gas mode decision:** If native token balance is sufficient for gas → use `--feature user_gas` (preferred). If native token balance is near zero → use `--feature no_gas` (gasless, gas deducted from fromToken; **requires swap amount ≥ ~$5 USD** — below this threshold the API only returns `user_gas`). This choice must be passed to confirm.
   ```bash
   python3 scripts/bitget_agent_api.py get-processed-balance --chain <fromChain> --address <wallet> --contract "" --contract <fromContract>
   ```

2. **Token risk check (required):** Run **`check-swap-token`** for the intended fromToken and toToken. If `error_code != 0`, show `msg` and stop. If for any token `data.list[].checkTokenList` is non-empty, show the `tips` content to the user and let them decide whether to continue. If the **toToken** (swap target) has an item with **`waringType` equal to `"forbidden-buy"`**, do **not** proceed with the swap and warn the user that this token cannot be used as the swap target.
   ```bash
   python3 scripts/bitget_agent_api.py check-swap-token --from-chain ... --from-contract ... --from-symbol ... --to-chain ... --to-contract ... --to-symbol ...
   ```

**Swap execution must strictly follow `docs/swap.md` Flow Overview — no shortcuts:**

1. **Balance check** — verify fromToken + native token balance before anything else
2. **Token risk check** — check-swap-token for both fromToken and toToken
3. **Quote** — display **all** market results to user, recommend the first, let user choose
4. **Confirm** — must display three fields to user: `outAmount` (expected), `minAmount` (minimum), `gasTotalAmount` (gas cost); check `recommendFeatures` for gas sufficiency
5. **User confirmation** — **do not** sign or send until user explicitly confirms ("confirm", "execute", "yes")
6. **makeOrder + sign + send** — execute as one atomic operation (use `order_make_sign_send.py`)
7. **Query status** — check order result; ignore `tips` when status=success

See Scripts for full command details and `docs/swap.md` for the complete flow.

**Technical reference:** Base URL `https://copenapi.bgwapi.io` (token auth, no API key). All commands via `scripts/bitget_agent_api.py` — run with `--help` for full subcommand list, or see [`docs/commands.md`](docs/commands.md).

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

Load the following when the task requires it:

| Module | File | When to Load |
|--------|------|--------------|
| First-Time Setup | [`docs/first-time-setup.md`](docs/first-time-setup.md) | New wallet creation, first swap config, derivation paths |
| Commands | [`docs/commands.md`](docs/commands.md) | Full subcommand parameters, usage examples for all scripts |
| Wallet & Signing | [`docs/wallet-signing.md`](docs/wallet-signing.md) | Key management, BIP-39/44, signing, multi-chain |
| Market Data | [`docs/market-data.md`](docs/market-data.md) | Token info, price, K-line, tx info, rankings, liquidity, security |
| Swap | [`docs/swap.md`](docs/swap.md) | Swap flow, quote/confirm/makeOrder/send, slippage, gas, approvals |
| RWA Stock Trading | [`docs/rwa.md`](docs/rwa.md) | RWA stock discovery, config, market status, order price, holdings |
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

**Swap-supported chains (7):**

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
| `bitget_agent_api.py` | Unified API client | Balance, token search, market data (info/price/kline/tx/rankings/liquidity/security), swap flow (quote→confirm→make-order→send→get-order-details) |
| `order_make_sign_send.py` | One-shot swap execution | makeOrder + sign + send in one run. `--private-key` (EVM) or `--private-key-sol` (Solana). Avoids 60s expiry. |
| `order_sign.py` | Sign makeOrder data | Outputs JSON array of signatures. Supports raw tx, EVM gasPayMaster (eth_sign), EIP-712, Solana Ed25519, Solana gasPayMaster. |
| `x402_pay.py` | x402 payment | EIP-3009 signing, Solana partial-sign, HTTP 402 pay flow |

### Quick Reference

```bash
# Balance (include native token "" to check gas)
python3 scripts/bitget_agent_api.py get-processed-balance --chain bnb --address <addr> --contract "" --contract <token>

# Market data
python3 scripts/bitget_agent_api.py token-price --chain bnb --contract <addr>
python3 scripts/bitget_agent_api.py rankings --name Hotpicks  # or topGainers, topLosers
python3 scripts/bitget_agent_api.py security --chain bnb --contract <addr>

# Swap flow
python3 scripts/bitget_agent_api.py quote --from-chain bnb --from-contract <addr> --from-symbol USDT --from-amount 5 --to-chain bnb --to-contract "" --to-symbol BNB --from-address <wallet> --to-address <wallet>
python3 scripts/bitget_agent_api.py confirm ... --market <id> --protocol <proto> --slippage <val> --feature user_gas
python3 scripts/order_make_sign_send.py --private-key-file /tmp/.pk_evm --order-id <id> --from-chain bnb ... --market ... --protocol ...
python3 scripts/bitget_agent_api.py get-order-details --order-id <id>
```

---

## Safety Rules

- **Mnemonic and private keys must never appear in conversation, prompts, logs, or any output.** Only derived **addresses** may be stored in context or shown. Private keys are derived from mnemonic in secure storage, used for signing, and immediately discarded.
- For large trades, always show the quote first and ask for user confirmation.
- Present security audit results before recommending any token action.
