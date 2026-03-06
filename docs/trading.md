# Trading Domain Knowledge

Trading supports two modes: **Order Mode** (default) and **Calldata Mode** (legacy).

| Mode | Use When | Key Features |
|------|----------|-------------|
| **Order Mode** (default) | All swaps, especially cross-chain and gasless | Gasless (EIP-7702), cross-chain, order tracking |
| **Calldata Mode** (legacy) | Direct on-chain tx construction, advanced users | Manual signing, MEV-protected broadcast |

## Pre-Trade Workflow

Before executing any swap, the agent should silently run risk checks and present a **single confirmation summary**.

**Automatic risk checks (both modes):**

```
1. security     → Check highRisk, honeypot, tax
2. token-info   → Get current price, market cap, holder count
3. liquidity    → Check pool depth vs trade size
```

**If any red flags are found** (highRisk, high tax, low liquidity), stop and warn the user immediately.

**Order Mode flow (default):**

```
4. order-quote  → Get price, market, check no_gas support
5. order-create → Create order (returns unsigned data)
6. order-status → Get accurate toAmount
7. PRESENT      → Show confirmation (MANDATORY, wait for user)
8. Sign + Submit → After user confirms
9. Poll once    → Wait 10s, check status
```

**Calldata Mode flow (legacy):**

```
4. swap-quote    → Get route and estimated output
5. PRESENT       → Show confirmation (MANDATORY, wait for user)
6. swap-calldata → Generate unsigned transaction data
7. (wallet signs externally)
8. swap-send     → Broadcast signed transaction
```

**For well-known tokens** (ETH, SOL, BNB, USDT, USDC, DAI, WBTC), risk checks will almost always pass — the single confirmation is sufficient. For unfamiliar tokens, be more verbose about risks.

## Common Trading Knowledge

The following applies to both Order Mode and Calldata Mode.

### EVM Token Approval (Critical)

On EVM chains (Ethereum, BNB Chain, Base, Arbitrum, Optimism), tokens require an **approve** transaction before the router contract can spend them. **Without approval, the swap transaction will fail on-chain and still consume gas fees.**

- Before calling `swap-calldata`, check if the token has sufficient allowance for the BGW router (`0xBc1D9760bd6ca468CA9fB5Ff2CFbEAC35d86c973`).
- If allowance is 0 or less than the swap amount, an approve transaction must be sent first.
- USDT on some chains (notably Ethereum mainnet) requires setting allowance to 0 before setting a new value.
- **Native tokens** (ETH, SOL, BNB) do not need approval — only ERC-20/SPL tokens.
- Approval is a one-time cost per token per router. Once approved with max amount, subsequent swaps of the same token skip this step.
- **Order Mode gasless**: When using Order Mode with `no_gas`, approval is **automatically bundled** into the gasless transaction — the agent does NOT need to handle approval separately. The backend includes the approve call in the EIP-7702 delegated execution.
- **Solana does not use approvals** — this applies only to EVM chains.

Include the approval status in the confirmation summary when relevant:
```
• Token approval: ⚠️ USDC not yet approved for router (one-time gas ~$0.03)
```

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

## Order Mode: Cross-Chain + Gasless Swaps (Default)

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

### Order Flow: 4-Step Process

```
1. order-quote   → Get price, recommended market, check no_gas support
2. order-create  → Create order, receive unsigned tx/signature data
3. (wallet signs the transaction or EIP-712 typed data)
4. order-submit  → Submit signed tx, get orderId confirmation
5. order-status  → Poll until status = success/failed/refunded
```

### Order Quote Response

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

### Gasless Mode (no_gas)

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

### Order Create Response: Two Modes

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

### Signing Order Responses

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

### Order Status Lifecycle

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
| `refunded` | Funds returned | Show refund details (see below) |

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
| `txs` | Array of `{chain, txId, stage, tokens}` | On `success`, `refunding`, `refunded` |
| `createTime` / `updateTime` | Unix timestamps | Always |

**Refund behavior (cross-chain):**

When a cross-chain order fails after the source transaction is already on-chain, the system initiates a refund. Important details:

- **Refund chain may differ from source chain.** If funds already bridged partially, refund happens on the target chain (not the source). Example: Base USDC → Polygon USDT failed → refund as Polygon USDC.
- **Refund token may differ from both fromToken and toToken.** The bridge may convert to a different stablecoin for the refund.
- **Refund amount is less than fromAmount.** Already-incurred fees (gas, bridge fees) are deducted. Expect ~1-2% loss.
- **`txs[]` contains multiple entries with `stage` field:**
  - `source` — the original transaction on the source chain
  - `target` — the delivery transaction on the target chain (on success)
  - `refund` — the refund transaction (on refunding/refunded)
- **`tokens[]` in refund tx** has `type: "receive"` with actual refund amount, symbol, and address.

**Refund notification template:**
```
⚠️ Cross-chain swap refunded
• Original: 2 USDC (Base) → ~1.93 USDT (Polygon)
• Refund: 1.977 USDC received on Polygon
• Refund TX: https://polygonscan.com/tx/0x...
• Fee lost: ~$0.023
```

**Polling strategy:**
- Same-chain: poll at 10s after submit, then every 10s. Max 2 minutes.
- Cross-chain: poll at 10s, then every 15s. Max 5 minutes.
- If still `processing` after max wait, give user the order ID to check later.

### Known Issues & Pitfalls (Order Mode)

1. **Cross-chain minimum amount**: Varies by chain. EVM chains: ~$1-5. Solana: $10 minimum (liqBridge only, no CCTP). Morph: $5 minimum. Below minimum returns `80002 amount too low`.

2. **`no_gas` requires quote support**: Only use `--feature no_gas` when `order-quote` returns `"no_gas"` in the `features` array. The API may accept the flag at create time without validation, but the backend will fail to execute. Solana currently does NOT support `no_gas` (features always `[]`).

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

### Order Mode Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| `80001` | Insufficient balance | Check balance, suggest smaller amount |
| `80002` | Amount too low | Increase amount |
| `80003` | Amount too high | Decrease amount |
| `80004` | Order expired | Re-create order |
| `80005` | Insufficient liquidity | Try different route or smaller amount |
| `80006` | Invalid request | Check parameters |
| `80007` | Signature mismatch | Re-sign with correct data |

### Security Considerations (Order Mode)

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

### Supported Chains (Order Mode)

| Chain | Code | Same-chain | Cross-chain |
|-------|------|-----------|-------------|
| Ethereum | `eth` | ✅ | ✅ |
| Solana | `sol` | ✅ | ✅ (EVM→Sol ✅; Sol→EVM requires SOL for gas) |
| BNB Chain | `bnb` | ✅ | ✅ |
| Base | `base` | ✅ | ✅ |
| Arbitrum | `arbitrum` | ✅ | ✅ |
| Polygon | `matic` | ✅ | ✅ |
| Morph | `morph` | ✅ | ✅ |

### Cross-Chain Limits (Order Mode)

| From Chain | liqBridge | CCTP |
|-----------|----------|------|
| Ethereum | $1 – $200,000 | $0.1 – $500,000 |
| Solana | $10 – $200,000 | ❌ |
| BNB Chain | $1 – $200,000 | ❌ |
| Base | $1 – $200,000 | $0.1 – $500,000 |
| Arbitrum | $1 – $200,000 | $0.1 – $500,000 |
| Polygon | $1 – $50,000 | $0.1 – $500,000 |
| Morph | $5 – $50,000 | — |

### Pre-Trade Workflow (Order Mode)

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
| Solana | ❌ Not supported | Solana as source chain: `no_gas` not available (quote returns `features: []`). EVM→Sol cross-chain works with gasless on the EVM source chain. |

**⚠️ Cross-chain gasless requires source chain 7702 binding.** If the wallet has never done a gasless transaction on the source chain, the first cross-chain order will fall back to normal txs. Do a same-chain gasless swap first to bind 7702, then cross-chain gasless will work.

**Only use gasless when `order-quote` returns `"no_gas"` in `features`.** Do not blindly try — the API accepts the flag but backend execution will fail if unsupported.

**User override:** If the user explicitly says to use their own gas (e.g., "use my gas", "user gas", "不要 gasless", "用自己的 gas"), do NOT pass `--feature no_gas` to order-create. The order will use normal gas mode instead, and gas is paid from the wallet's native token balance. Show "Gas mode: User Gas (native token)" in the confirmation summary.

### toAmount: Three Sources of Truth

| Source | Field | When Available | Accuracy |
|--------|-------|---------------|----------|
| `order-quote` | `toAmount` | Before create | Rough estimate, pre-gas |
| `order-status` (init) | `toAmount` | After create, before submit | **Better estimate** — use this for confirmation |
| `order-status` (success) | `receiveAmount` | After completion | **Actual received amount** |

**Always use `order-status.toAmount` for the confirmation summary**, not the quote's toAmount. The order-status value is calculated after actual routing and is more accurate.

- When using `no_gas` mode, gas is still deducted from the input. Even the order-status `toAmount` may not fully reflect gas deduction.
- The **actual received amount** is only known after completion via `receiveAmount`.
- Always present `toAmount` as an estimate: use "~" prefix (e.g., "~1.94 USDT").

### Gas Mode: Default to Gasless

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
• Market: bgwevmaggregator
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
• Market: bkbridgev3.liqbridge (cross-chain bridge)
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
• Market: bkbridgev3.liqbridge
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
3. Market (aggregator/bridge used, e.g., `bgwAggregator`, `bkbridgev3.liqbridge`)
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



## Calldata Mode (Legacy Swap Flow)

Calldata mode is a multi-step process. These commands must be called in order:

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

### Broadcasting with swap-send (Calldata Mode)

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

