---
name: bitget-wallet
version: "2026.3.5-1"
updated: "2026-03-04"
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

### Version Awareness

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

### First-Time Swap Configuration

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
- **Transaction deadline**: The calldata response includes a `deadline` field (default: 600 seconds = 10 minutes). After this time, the on-chain transaction will revert even if broadcast. The `--deadline` parameter in `swap-calldata` allows customization (in seconds). **Use the user's configured deadline preference** (see "First-Time Swap Configuration"). If not yet configured, default to 300 seconds and inform the user.

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

**Best practice:** Run `security` before any swap involving an unfamiliar token. This should follow the user's configured security preference (see "First-Time Swap Configuration"). If set to "Always check" (default), run automatically and silently — only surface results if risks are found. **Never skip security checks for tokens the user has not traded before, regardless of preference.**

### K-line: Valid Parameters

- **Periods**: `1s`, `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`
- **Max entries**: 1440 per request
- Other period values will return an error or empty data.

### Transaction Info: Valid Intervals

- **Intervals**: `5m`, `1h`, `4h`, `24h` only
- These return buy/sell volume, buyer/seller count for the given time window.
- Other interval values are not supported.

### Historical Coins: Pagination

- `createTime` is a **datetime string** in format `"YYYY-MM-DD HH:MM:SS"` (NOT a Unix timestamp).
- `limit` is a number (max results per page).
- Response contains `lastTime` field (also a datetime string) — pass it as `createTime` in the next request to paginate.
- Example: `--create-time "2026-02-27 00:00:00" --limit 20`
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
• Deadline: [user's configured preference, default 300s]

Proceed? [yes/no]
```

**After user confirms:**

```
5. swap-calldata → Generate unsigned transaction
6. (wallet signs the transaction)
7. swap-send    → Broadcast via MEV-protected endpoint
```

**For well-known tokens** (ETH, SOL, BNB, USDT, USDC, DAI, WBTC), the risk checks will almost always pass — the single confirmation is sufficient. For unfamiliar or new tokens, be more verbose about the risks.

### Order Mode: Cross-Chain + Gasless Swaps

The Order Mode API (`order-*` commands) is the **recommended** way to execute swaps. It supports everything the legacy `swap-*` flow does, plus:

- **Cross-chain swaps** — swap tokens between different chains in one order (e.g., USDC on Base → USDT on BNB Chain)
- **Gasless transactions (no_gas)** — pay gas fees using the input token instead of requiring native tokens
- **Order tracking** — full order lifecycle with status updates, refund handling
- **EIP-7702 support** — advanced signature mode for gasless execution
- **B2B fee splitting** — partners can set custom fee rates (`feeRate`)

**When to use Order Mode vs Legacy Swap:**

| Scenario | Use |
|----------|-----|
| Cross-chain swap | Order Mode (only option) |
| No native token for gas | Order Mode with `no_gas` |
| Same-chain swap | Either (Order Mode recommended) |
| Need order tracking/refunds | Order Mode |

#### Order Flow: 4-Step Process

```
1. order-quote   → Get price, recommended market, check no_gas support
2. order-create  → Create order, receive unsigned tx/signature data
3. (wallet signs the transaction or EIP-712 typed data)
4. order-submit  → Submit signed tx, get orderId confirmation
5. order-status  → Poll until status = success/failed/refunded
```

#### Order Quote Response

Key fields to check:

| Field | Meaning |
|-------|---------|
| `toAmount` | Estimated output (human-readable) |
| `market` | Required for `order-create` — pass it exactly |
| `slippage` | Recommended slippage tolerance |
| `priceImpact` | Price impact percentage |
| `fee.totalAmountInUsd` | Total fee in USD |
| `fee.appFee` | Partner's fee portion |
| `fee.platformFee` | Platform fee portion |
| `features: ["no_gas"]` | If present, gasless mode is available |
| `eip7702Bindend` | Whether address has EIP-7702 binding |

#### Gasless Mode (no_gas)

Gasless mode uses EIP-7702 delegation — a backend relayer constructs and pays for the transaction on your behalf. The gas cost is deducted from the input token amount.

1. Call `order-quote` — check if `features` contains `"no_gas"`
2. Pass `--feature no_gas` to `order-create`
3. Response returns `signatures` (not `txs`) — EIP-712 + EIP-7702 auth
4. Sign using API-provided `hash` fields, submit signatures
5. Backend relayer constructs full EIP-7702 tx, pays gas, broadcasts
6. **No native token balance needed** — ideal for Agent wallets

**Auto-detection logic:**
```
Default: always use no_gas when available.

if order-quote returns features: ["no_gas"]:
    auto-apply --feature no_gas to order-create
elif user has no native token for gas:
    warn: "Insufficient gas. This route does not support gasless mode."
else:
    proceed without no_gas (normal tx mode)
```

**⚠️ Important: `features` in order-quote is not always reliable.**
In testing, some routes return `features: []` in the quote but still accept `--feature no_gas` in order-create. When the wallet has zero native token balance, always try `no_gas` regardless of the quote's `features` field. If order-create rejects it, fall back to informing the user they need gas.

#### Order Create Response: Two Modes

The response contains either `txs` (normal transaction) or `signatures` (EIP-7702 gasless):

**Mode 1: Normal Transaction (`txs`)**
```json
{
  "orderId": "...",
  "txs": [{
    "kind": "transaction",
    "chainName": "base",
    "chainId": "8453",
    "data": {
      "to": "0x...",
      "calldata": "0x...",
      "gasLimit": "54526",
      "nonce": 308,
      "value": "0",
      "supportEIP1559": true,
      "maxFeePerGas": "...",
      "maxPriorityFeePerGas": "..."
    }
  }]
}
```
→ Build transaction from `data` fields, sign with wallet, submit raw tx hex.

**Mode 2: EIP-7702 Signature (`signatures`) — Gasless**

Returned when `--feature no_gas` is used. Contains 2 signatures to sign:

```json
{
  "orderId": "...",
  "signatures": [
    {
      "kind": "signature",
      "chainName": "base",
      "chainId": "8453",
      "hash": "0x...",          // ← Sign THIS hash directly
      "data": {
        "signType": "eip712",   // EIP-712: approve + swap bundled
        "types": { "Aggregator": [...], "Call": [...] },
        "domain": { "name": "BW7702Admin", "verifyingContract": "0x8C80e4d1..." },
        "message": {
          "calls": [
            { "target": "0x8335...", "callData": "0x095ea7b3..." },  // approve
            { "target": "0xBc1D...", "callData": "0xd984396a..." }   // swap
          ]
        }
      }
    },
    {
      "kind": "signature",
      "chainName": "base",
      "chainId": "8453",
      "hash": "0x...",          // ← Sign THIS hash directly
      "data": {
        "signType": "eip7702_auth",   // EIP-7702: delegate to smart contract
        "contract": "0xa845C743...",   // delegation target
        "nonce": "0"
      }
    }
  ]
}
```

**What each signature does:**
1. **EIP-712 (Aggregator)** — authorizes the bundled calls (approve + swap) via the BW7702Admin contract
2. **EIP-7702 auth** — delegates your EOA to the EIP-7702 smart contract, enabling batched execution

→ Sign each item's `hash` field with `unsafe_sign_hash`. Do NOT recompute hashes.
→ Backend relayer receives signatures, constructs full EIP-7702 type-4 tx, pays gas, broadcasts.

#### Signing Order Responses

**Critical: Use the API-provided `hash` field to sign. Do NOT recompute EIP-712 hashes yourself.**

The `encode_typed_data` implementations in common libraries (eth-account, ethers.js) may produce different hashes for complex nested structs (`Call[]` with `bytes` callData). The API pre-computes the correct hash and returns it in each signature item's `hash` field.

**Signing logic (for `signatures` mode — gasless/EIP-7702):**
```python
from eth_account import Account

acct = Account.from_key(private_key)
signed_list = []
for sig_item in order_data["signatures"]:
    hash_bytes = bytes.fromhex(sig_item["hash"][2:])
    signed = acct.unsafe_sign_hash(hash_bytes)
    signed_list.append("0x" + signed.signature.hex())
# Submit: order-submit --order-id <id> --signed-txs <signed_list>
```

**Signing logic (for `txs` mode — normal gas):**
```python
for tx_item in order_data["txs"]:
    tx_dict = {
        "to": tx_item["data"]["to"],
        "data": tx_item["data"]["calldata"],
        "gas": int(tx_item["data"]["gasLimit"]),
        "nonce": int(tx_item["data"]["nonce"]),
        "chainId": int(tx_item["chainId"]),
        "gasPrice": int(tx_item["data"]["gasPrice"]),
        "value": <parse tx_item["data"]["value"]>,
    }
    signed_tx = acct.sign_transaction(tx_dict)
    signed_list.append("0x" + signed_tx.raw_transaction.hex())
```

**Helper script:** `python3 scripts/order_sign.py --private-key <key>` accepts order-create JSON from stdin and outputs signed hex array.

**Backend flow after submit:**
```
Agent signs → submits signatures → Backend relayer receives →
Constructs full EIP-7702 tx (embeds our signatures) →
Relayer pays gas → Broadcasts to chain
```
The Agent never constructs the full EIP-7702 transaction. The backend relayer handles tx construction, gas payment, and broadcasting. We only provide signatures.

**Important notes:**
- Signature format: 65 bytes (r + s + v), v is 27 or 28 (not y_parity 0/1)
- Order of signedTxs must match order of signatures/txs in the response

**EIP-7702 binding state affects signature count:**

| State | `eip7702Bindend` | Signatures | What's signed |
|-------|-------------------|-----------|---------------|
| First gasless tx | `false` | 2 | EIP-712 (approve + swap) + EIP-7702 auth (delegation) |
| Subsequent gasless tx | `true` | 1 | EIP-712 (swap only, approve already done) |

The binding persists on-chain. Once bound, future gasless transactions on the same chain are faster (1 signature, ~5 seconds).

#### Order Status Lifecycle

```
init → processing → success
                  → failed
                  → refunding → refunded
```

| Status | Meaning | Action |
|--------|---------|--------|
| `init` | Order created, not yet submitted | Use toAmount for confirmation |
| `processing` | Transaction in progress | Poll, show "等待确认..." |
| `success` | Completed successfully | Show receiveAmount + txId + explorer link |
| `failed` | Transaction failed | Show error, suggest retry |
| `refunding` | Refund in progress | Wait, notify user |
| `refunded` | Funds returned | Show refund tx details |

**order-status response fields (all statuses):**

| Field | Description | Available |
|-------|-------------|-----------|
| `orderId` | Order identifier | Always |
| `status` | Current status | Always |
| `fromChain` / `toChain` | Source / destination chain | Always |
| `fromContract` / `toContract` | Token contracts | Always |
| `fromAmount` | Input amount | Always |
| `toAmount` | Estimated output (more accurate than quote) | Always (after create) |
| `receiveAmount` | **Actual received amount** | Only on `success` |
| `txs` | Array of `{chain, txId, stage, tokens}` | Only on `success` |
| `createTime` / `updateTime` | Unix timestamps | Always |

**Polling strategy:**
- Same-chain: poll at 10s after submit, then every 10s. Max 2 minutes.
- Cross-chain: poll at 10s, then every 15s. Max 5 minutes.
- If still `processing` after max wait, give user the order ID to check later.

#### Known Issues & Pitfalls (Order Mode)

1. **Cross-chain minimum amount**: Cross-chain swaps (e.g., Base USDC → BNB USDT) have a minimum of ~$2. Below that returns `80002 amount too low`.

2. **`features` field unreliable for gasless**: `order-quote` may return `features: []` but `order-create` still accepts `--feature no_gas`. When wallet has zero native token, always try `no_gas` first.

3. **Base same-chain without no_gas**: `order-create` on Base without `--feature no_gas` returns `80000 system error` when the wallet has no ETH. This is because the API can't construct a normal tx for an account with no gas. Solution: use `no_gas`.

4. **EIP-712 hash mismatch**: Do NOT use `encode_typed_data` from eth-account or similar libraries. Their encoding of nested `Call[]` with `bytes callData` differs from the API/contract implementation. Always sign the API-provided `hash` directly.

5. **Signature format**: 65 bytes `r + s + v` where v is 27 or 28 (not y_parity 0/1). This is the standard output of `unsafe_sign_hash`.

6. **Order expiry**: Orders have a deadline (typically 2 minutes from creation). Sign and submit promptly after `order-create`. If expired, create a new order.

7. **No approve needed for gasless**: EIP-7702 gasless mode bundles approve + swap into one atomic operation via the Aggregator contract. No separate approve transaction needed.

8. **Never duplicate order execution**: Signed and submitted orders are **irreversible**. Before creating a new order for the same trade, always check the previous order's status via `order-status`. If a previous script/process might still be running, verify it's truly dead before retrying. Creating and submitting two orders for the same trade will execute both and spend double the funds.

9. **Cross-chain orders return multiple TXs**: A successful cross-chain `order-status` returns 2 entries in `txs[]` — `stage: "source"` (origin chain) and `stage: "target"` (destination chain). Show both explorer links to the user.

10. **Cross-chain toAddress MUST use target chain's native address format**: When swapping cross-chain, the `toAddress` must be a valid address on the **destination chain**, not the source chain. **This applies to BOTH `order-quote` and `order-create`** — the quote will return 80000 without it for non-EVM targets.
    - EVM → EVM (e.g., Base → Polygon): same EVM address works ✅
    - EVM → Solana: `toAddress` must be a Solana address (Base58, Ed25519) — **must be passed in quote too**
    - EVM → Tron: `toAddress` must be a Tron address (T... Base58Check)
    - **Missing or wrong toAddress causes 80000 at quote stage for non-EVM targets, or stuck funds at execution.**

#### Order Mode Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| `80001` | Insufficient balance | Check balance, suggest smaller amount |
| `80002` | Amount too low | Increase amount |
| `80003` | Amount too high | Decrease amount |
| `80004` | Order expired | Re-create order |
| `80005` | Insufficient liquidity | Try different route or smaller amount |
| `80006` | Invalid request | Check parameters |
| `80007` | Signature mismatch | Re-sign with correct data |

#### Security Considerations (Order Mode)

**Trust model:** We sign hashes provided by the API. Verification layers:

| Layer | Verified | Method |
|-------|----------|--------|
| DOMAIN_SEPARATOR | ✅ | Matches on-chain contract `0x8C80e4d1...` |
| AGGREGATOR_TYPE_HASH | ✅ | Found in contract bytecode |
| CALL_TYPE_HASH | ✅ | Found in contract bytecode |
| Message content | ✅ Readable | EIP-712 `message.calls` shows approve/swap targets & calldata |
| Hash correctness | ⚠️ Trusted | Cannot independently recompute due to encoding differences |
| Response integrity | ⚠️ TLS only | No server-side signature on response (enhancement pending) |

**Pre-sign verification checklist:**
1. Read `message.calls` — verify targets are known contracts (router, token)
2. Verify `message.msgSender` matches your wallet address
3. Verify `domain.verifyingContract` is the known BW7702Admin contract
4. Verify `domain.chainId` matches expected chain
5. After completion, verify on-chain tx matches expected token transfer

**Planned enhancement:** API response signing with server public key for MITM protection.

#### Supported Chains (Order Mode)

| Chain | Code | Same-chain | Cross-chain |
|-------|------|-----------|-------------|
| Ethereum | `eth` | ✅ | ✅ |
| Solana | `sol` | ✅ | ❌ (to-sol bug) |
| BNB Chain | `bnb` | ✅ | ✅ |
| Base | `base` | ✅ | ✅ |
| Arbitrum | `arbitrum` | ✅ | ✅ |
| Polygon | `matic` | ✅ | ✅ |
| Morph | `morph` | ✅ | ✅ |

#### Pre-Trade Workflow (Order Mode)

**Key principle: order-create before present, present before sign.**

The order is a contract — the user sees the actual order details, confirms, THEN the agent signs and submits. **The agent MUST NOT sign or submit without explicit user confirmation.**

```
1. security       → Check token safety (automatic, silent unless issues found)
2. order-quote    → Get price, market, check no_gas + eip7702Bindend
3. order-create   → Create order (auto-apply no_gas if available)
                     Returns orderId + unsigned tx/signature data
4. order-status   → Get order details (toAmount is more accurate than quote)
5. PRESENT        → Show confirmation summary to user (MANDATORY)
                     Use toAmount from order-status, NOT from quote
                     Include: order ID, amounts, fees, gas mode, signatures, safety
                     Include: EIP-712 verification (domain, msgSender, calls)
                     Include: small amount gasless warning if < $1
6. WAIT           → User must explicitly say "yes" / "confirm" / "执行"
                     If user says "no" → abort, do not sign
7. Sign + Submit  → Sign using API-provided hash fields, then order-submit
8. Poll once      → Wait 10s, then order-status once
                     If success → show receiveAmount + txId + explorer link
                     If still processing → show order ID + status, tell user to check later
                     DO NOT loop/block waiting for completion — return control to user immediately
```

**Why this order matters:**
- order-create before present: user sees real order data, not just estimates
- order-status for toAmount: more accurate than quote (accounts for actual routing)
- present before sign: user controls their funds, agent doesn't auto-execute
- **Skipping the confirmation step is a violation of the agent's operating rules**

**Completion message (same-chain):**
```
✅ Swap Complete
• Order: f347d76e...
• 1 USDC → 0.98382 USDT (Base)
• Gas mode: Gasless
• Tx: 0x786eff3d...
• Explorer: https://basescan.org/tx/0x786eff3d...
```

**Completion message (cross-chain):**
```
✅ Swap Complete
• Order: 861d8427...
• 2 USDC (Base) → 1.877485 USDT (Polygon)
• Gas mode: Gasless
• Source TX (Base): 0x2954bb0d...
  https://basescan.org/tx/0x2954bb0d...
• Target TX (Polygon): 0xd72483c8...
  https://polygonscan.com/tx/0xd72483c8...
```

**If failed:**
```
❌ Swap Failed
• Order: f365ba3d...
• 0.1 USDC → USDT (Base)
• Status: failed
• Possible causes: relayer error, insufficient liquidity, expired
```

**Block explorer URLs by chain:**

| Chain | Explorer URL |
|-------|-------------|
| eth | `https://etherscan.io/tx/{txId}` |
| bnb | `https://bscscan.com/tx/{txId}` |
| base | `https://basescan.org/tx/{txId}` |
| arbitrum | `https://arbiscan.io/tx/{txId}` |
| matic | `https://polygonscan.com/tx/{txId}` |
| optimism | `https://optimistic.etherscan.io/tx/{txId}` |
| sol | `https://solscan.io/tx/{txId}` |
| trx | `https://tronscan.org/#/transaction/{txId}` |

**Poll timing: ONE poll only.**
- Wait 10 seconds after submit, then call order-status once.
- If `success` → show completion message (receiveAmount + txId + explorer link).
- If `processing` or `init` → show "已提交" message with order ID and source TX if available. Do NOT keep polling. Return control to the user.
- User can ask "check order {orderId}" later to get the final status.
- **Never block the agent waiting for order completion.** Cross-chain orders can take 5-15 minutes.

**Gas mode strategy: ALWAYS try gasless first.**

```
1. Always pass --feature no_gas to order-create (regardless of quote features field)
2. Check response:
   a. Returns `signatures` array → Gasless ✅ proceed with EIP-712 signing
   b. Returns `txs` array (normal transactions) → Gasless NOT supported on this chain
      → Warn user: "⚠️ This chain does not support gasless. Need native token for gas."
      → Check if wallet has native token balance
      → If no balance: "❌ Cannot execute: no [MATIC/ETH/...] for gas and gasless unavailable"
      → If has balance: proceed with normal tx signing, show "Gas mode: Normal"
```

**Why always try gasless:**
- The `features` field in `order-quote` is unreliable (often returns `[]` even when gasless works)
- The `eip7702Bindend` / `eip7702Contract` fields are more reliable but still not definitive
- The only sure way to know: pass `no_gas` and check if response has `signatures` or `txs`
- Cost of trying: zero (order-create with no_gas that falls back to txs is not an error)

**Gasless support by chain (as of 2026-03-04):**

| Chain | Gasless (EIP-7702) | Notes |
|-------|-------------------|-------|
| Base | ✅ Supported | Tested, confirmed |
| Ethereum | ✅ Supported | — |
| BNB Chain | ✅ Supported | — |
| Polygon | ✅ Supported | Same-chain confirmed; cross-chain requires 7702 binding first |
| Arbitrum | ✅ Supported | — |
| Morph | ✅ Supported | — |
| Solana | ❌ Not working | Order mode gasless submit succeeds but execution always fails; pending API team fix |

**⚠️ Cross-chain gasless requires source chain 7702 binding.** If the wallet has never done a gasless transaction on the source chain, the first cross-chain order will fall back to normal txs. Do a same-chain gasless swap first to bind 7702, then cross-chain gasless will work.

**Always try gasless first rather than relying on this table.**

**User override:** If the user explicitly says to use their own gas (e.g., "use my gas", "user gas", "不要 gasless", "用自己的 gas"), do NOT pass `--feature no_gas` to order-create. The order will use normal gas mode instead, and gas is paid from the wallet's native token balance. Show "Gas mode: User Gas (native token)" in the confirmation summary.

#### toAmount: Three Sources of Truth

| Source | Field | When Available | Accuracy |
|--------|-------|---------------|----------|
| `order-quote` | `toAmount` | Before create | Rough estimate, pre-gas |
| `order-status` (init) | `toAmount` | After create, before submit | **Better estimate** — use this for confirmation |
| `order-status` (success) | `receiveAmount` | After completion | **Actual received amount** |

**Always use `order-status.toAmount` for the confirmation summary**, not the quote's toAmount. The order-status value is calculated after actual routing and is more accurate.

- When using `no_gas` mode, gas is still deducted from the input. Even the order-status `toAmount` may not fully reflect gas deduction.
- The **actual received amount** is only known after completion via `receiveAmount`.
- Always present `toAmount` as an estimate: use "~" prefix (e.g., "~1.94 USDT").

#### Gas Mode: Default to Gasless

**Always default to gasless** — pass `--feature no_gas` to `order-create` on every trade. Do not check `features` field first, do not ask the user to choose.

**How to detect gasless success vs fallback:**
- Response has `signatures` array (non-empty) → gasless mode active ✅
- Response has `txs` array (non-empty) → chain doesn't support gasless, fell back to normal mode
- If fell back to normal and wallet has no native token → **stop and warn user**

**Rationale:** Gasless mode eliminates the need for users/agents to maintain native token balances on every chain. The gas cost is minimal compared to convenience. Trying gasless has zero cost — if the chain doesn't support it, the API silently falls back to normal txs.

**⚠️ MANDATORY: The agent MUST present the confirmation summary and wait for explicit user approval before signing and submitting. Never skip this step. No exceptions.**

**Confirmation summary (gasless, same-chain):**
```
Order Created ✅
• Order: f347d76e4b7e434897c2c699b7a588b9
• 0.1 USDC → ~0.086 USDT (Base)
• ⚠️ Gasless: gas 从输入金额扣除，小额交易 gas 占比较高
• Route: bgwevmaggregator
• Price impact: 0.009%
• Fees: $0.0003 (app fee)
• Gas mode: Gasless ✅ (EIP-7702 已绑定)
• Signatures to sign: 1 (EIP-712)
• Token safety: ✅ Both verified

EIP-712 Verification:
• domain: BW7702Admin @ 0x8C80e4d1... ✅
• msgSender: matches our wallet ✅
• calls: 1 (swap via router 0xBc1D9760...)

Confirm and sign? [yes/no]
```

**Cross-chain gasless example:**
```
Order Created ✅
• Order: 9c3f5bcab4a2449ea5e66a9770ea7169
• 2 USDC (Base) → ~1.94 USDT (Polygon)
• ⚠️ Gasless: gas 从输入金额扣除
• Route: bkbridgev3.liqbridge (cross-chain bridge)
• Price impact: 0.024%
• Fees: $0.014 (app $0.006 + platform $0.006 + gas $0.002)
• Gas mode: Gasless ✅ (EIP-7702 已绑定)
• Signatures to sign: 1 (EIP-712)
• Token safety: ✅ Both verified

Confirm and sign? [yes/no]
```

**Normal gas example:**
```
Order Created ✅
• Order: a1b2c3d4e5f6...
• 2.0 USDC (Base) → ~1.95 USDT (BNB Chain)
• Route: bkbridgev3.liqbridge
• Price impact: 0.057%
• Fees: $0.114 total
• Gas mode: Normal (native token)
• Transactions to sign: 1
• Token safety: ✅ Both verified

Confirm and sign? [yes/no]
```

**⚠️ toAmount in confirmation uses `order-status` (init), not quote.** This is more accurate because it reflects actual routing. However, gasless gas deduction may still reduce the final `receiveAmount` further.

**Confirmation summary MUST include:**
1. Order ID
2. Input → output with ~ estimate
3. Route and price impact
4. Fees breakdown
5. Gas mode (Gasless/Normal/User Gas)
6. Number and type of signatures
7. Small amount warning if applicable
8. Token safety status
9. EIP-712 verification (domain, msgSender, calls summary)

**Gas mode display rules:**
- Gasless with 7702 bound → "Gasless ✅ (EIP-7702 已绑定)"
- Gasless first time → "Gasless ✅ (EIP-7702 首次绑定, 2 signatures)"
- User override → "User Gas (native token)"
- Not available → "Normal (requires native token for gas)"

**Small amount gasless warning:**
When input amount < $1 USD, show warning: gasless gas cost is fixed (~$0.01-0.02) regardless of trade size. For small trades this can be 10-15% of the input. For amounts > $10 the gas overhead is < 0.2% and negligible.

| Input Amount | Estimated Gas Overhead |
|-------------|----------------------|
| $0.10 | ~15% ⚠️ |
| $1.00 | ~1.5% |
| $10.00 | ~0.15% |
| $100.00 | ~0.015% |

### Wallet & Signing Domain Knowledge

#### Key Hierarchy (BIP-39 / BIP-44)

```
Mnemonic (12/24 words)
  └→ Seed (512 bits via PBKDF2)
      └→ Master Key
          └→ Derivation Path (BIP-44)
              ├→ m/44'/60'/0'/0/0   → EVM private key → ETH/BNB/Base/Arbitrum/Polygon address
              ├→ m/44'/60'/0'/0/1   → EVM account #2
              ├→ m/44'/501'/0'/0'   → Solana private key (Ed25519)
              └→ m/44'/195'/0'/0/0  → Tron private key
```

**Critical facts:**
- **One mnemonic → all chains.** The same 12/24 words derive keys for every supported chain.
- **EVM chains share one key.** ETH, BNB, Base, Arbitrum, Polygon, Optimism all use the same private key and address at `m/44'/60'/0'/0/0`.
- **Solana uses a different key.** Ed25519 (not secp256k1). Different address, different signing algorithm.
- **Private key ≠ mnemonic.** A private key is one specific key derived from the mnemonic. Losing the mnemonic means losing access to all derived keys.

#### Key Management for Agents

**Principle: minimal privilege, no persistence.**

```
Storage:     1Password only (never local files, env vars, or code)
Injection:   Fetch → use → destroy in same script execution
Scope:       Single private key, not full mnemonic
Derivation:  Done once during setup, only the derived key is stored
```

**Why agents hold a private key, not a mnemonic:**
- Mnemonic = master access to all chains and accounts
- Private key = access to one account on EVM chains (or one Solana account)
- If compromised, blast radius is limited to one key's assets
- Agent only needs to sign transactions, not derive new accounts

**Key retrieval pattern (Python):**
```python
# Fetch from 1Password, use, discard
import subprocess
key = subprocess.run(
    ["python3.13", "scripts/op_sdk.py", "get", "Agent Wallet", "--field", "evm_key", "--reveal"],
    capture_output=True, text=True
).stdout.strip()
# ... use key for signing ...
del key  # explicit cleanup
```

#### Signature Types (EVM)

| Type | Use Case | How to Sign |
|------|----------|-------------|
| **Raw Transaction** (type 0/2) | Normal transfers, swaps | `Account.sign_transaction(tx_dict)` → full signed tx hex |
| **EIP-191** (personal_sign) | Message signing, off-chain auth | `Account.sign_message(encode_defunct(msg))` |
| **EIP-712** (typed data) | Structured data (permits, orders) | `Account.sign_message(encode_typed_data(...))` or `unsafe_sign_hash(hash)` |
| **EIP-7702** (delegation auth) | Delegate EOA to smart contract | `unsafe_sign_hash(keccak(0x05 \|\| rlp([chainId, addr, nonce])))` |

**When to use which:**
- API returns `txs` with `kind: "transaction"` → Raw Transaction signing
- API returns `signatures` with `signType: "eip712"` → EIP-712 (use API hash)
- API returns `signatures` with `signType: "eip7702_auth"` → EIP-7702 delegation

**⚠️ `unsafe_sign_hash` vs `sign_message`:**
- `sign_message` adds the EIP-191 prefix (`\x19Ethereum Signed Message:\n32`)
- `unsafe_sign_hash` signs the raw hash directly (no prefix)
- For API-provided hashes, **always use `unsafe_sign_hash`** — the hash is already the final digest
- Using `sign_message` on a pre-computed hash produces a wrong signature

#### Multi-Chain Signing

| Chain Family | Curve | Signing Library | Address Format |
|-------------|-------|----------------|----------------|
| EVM (ETH/BNB/Base/...) | secp256k1 | eth-account | 0x... (20 bytes, checksummed) |
| Solana | Ed25519 | solders / solana-py | Base58 (32 bytes) |
| Tron | secp256k1 | Same as EVM, Base58Check address | T... |

**EVM all-chain:** Sign once, broadcast to any EVM chain. The chainId in the tx prevents replay across chains.

#### Transaction Anatomy (EVM)

```
Type 0 (Legacy):     {nonce, gasPrice, gasLimit, to, value, data}
Type 2 (EIP-1559):   {nonce, maxFeePerGas, maxPriorityFeePerGas, gasLimit, to, value, data, chainId}
Type 4 (EIP-7702):   {... + authorizationList: [{chainId, address, nonce, y_parity, r, s}]}
```

**Key fields for swap transactions:**
- `to`: Router contract (not the destination token)
- `data`: Encoded swap calldata from API
- `value`: Amount of native token to send (0 for ERC-20 swaps, >0 for native → token)
- `nonce`: Must match account's current nonce (API provides this)
- `gasLimit` / `gasPrice`: API provides estimates

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
