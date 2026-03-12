# Swap (Token Swap) Domain Knowledge

This document describes the **Swap flow**: use `scripts/bitget_agent_api.py` for the new API (no apiKey). Flow: **quote → confirm → makeOrder → sign & send → getOrderDetails**. See [Wallet & Signing](wallet-signing.md) for key management details.

**Wallet before swap:** The agent must have a configured wallet (mnemonic in secure storage, derived addresses in context). If not, guide the user through First-Time Wallet Setup (see SKILL.md). **Mnemonic and private keys must never appear in context.**

**Signing flow:** After makeOrder, derive the private key from mnemonic in secure storage, pass to `order_sign.py --private-key <key>`, fill `txs[].sig`, then send. MakeOrder unsigned data expires in ~60 seconds — sign and send must follow immediately.

## Flow Overview

| Step | Interface / script | Description |
|------|--------------------|-------------|
| 0 | `bitget_agent_api.py check-swap-token` | Check fromToken and toToken for risks **before** quote; if risks or forbidden-buy on toToken, prompt user or stop. |
| 1 | `bitget_agent_api.py quote` | First quote; returns multiple markets in `data.quoteResults`. Agent shows **all** results, recommends the first; user may choose another for confirm. |
| 2 | `bitget_agent_api.py confirm` | Second quote; use market/protocol/slippage from **chosen** quote result (default first); Get latest quoteResult and orderId. The agent should display the `data.quoteResult`. If the `data.tips` are not empty, agent should display and remind user |
| 3+4+5 | **`order_make_sign_send.py`** (recommended) | makeOrder + sign (from mnemonic file) + send in one run |
| 3′ | `bitget_agent_api.py make-order` | Create order; returns unsigned data.txs (~60s expiry) |
| 4′ | `order_sign.py` + fill `txs[].sig` | Sign data.txs with private key (derived from mnemonic, discarded after) |
| 5′ | `bitget_agent_api.py send` | Submit signed order (body: orderId + txs) |
| 6 | `bitget_agent_api.py get-order-details` | Query order status and result |

**Balance and token discovery:** For balance only use `get-processed-balance`. For balance **plus token price** (e.g. portfolio value in USD) use **`batch-v2`** (same request format: `list: [{ chain, address, contract }]`). 
**Search tokens:** To search tokens by keyword or contract address use **`search-tokens --keyword <keyword|contract>`** (optional **`--chain`** to restrict to one chain); use the returned `chain`, `contract`, `symbol` when building quote/confirm args.

## Pre-Trade Checks (All Trades)

Before any swap, the agent **must** run balance and risk checks, then show a **single confirmation summary**.

**1. Balance check (required before every new swap)**

Run **`get-processed-balance`** to verify the wallet has sufficient fromToken balance **and** native token for gas:

```bash
python3 scripts/bitget_agent_api.py get-processed-balance --chain <fromChain> --address <wallet> --contract "" --contract <fromContract>
```

- If **fromToken balance < fromAmount**: inform the user of the shortfall (e.g., "You have 5.85 USDT but requested 6 USDT") and **do not proceed**.
- If **native token balance ≈ 0**: warn the user about insufficient gas. Suggest reducing the swap amount or using gasless mode if available.
- The API error `40001: Demo trading failed` from the confirm step is often caused by insufficient balance, not slippage — always check balance first.

**2. Token risk check (required before every new swap)**

Run **`check-swap-token`** for the intended fromToken and toToken **before** calling quote:

```bash
python3 scripts/bitget_agent_api.py check-swap-token --from-chain <chain> --from-contract <addr> --from-symbol <sym> --to-chain <chain> --to-contract <addr> --to-symbol <sym>
```

Or with JSON stdin: `echo '{"list":[{"chain":"...","contract":"...","symbol":"..."}, ...]}' | python3 scripts/bitget_agent_api.py check-swap-token --json-stdin`.

- If **`error_code != 0`**: show the `msg` field to the user and **do not proceed** with the swap.
- If for any token **`data.list[].checkTokenList`** is **non-empty**: each item may contain `tips` (risk description) and `waringType`. **Show the `tips` content** to the user and let them decide whether to continue. Optionally summarize by token (from/to).
- If the **toToken** (the swap target) has an item with **`waringType === "forbidden-buy"`**: **do not proceed** with the swap. Warn the user that this token cannot be used as the swap target and suggest choosing a different output token.
- If all tokens have **empty `checkTokenList`**: no risk reported; continue with the rest of the risk checks and swap flow.
- For well-known tokens (ETH, SOL, BNB, USDT, USDC, DAI, WBTC), token risk check and other checks usually pass; one confirmation is enough. For unfamiliar tokens, be explicit about risks.

## Swap Flow in Detail

**Amounts in the swap flow:** All amount fields (e.g. **fromAmount**, toAmount) use **human-readable values** only. For example, `0.01` USDT is passed as `"0.01"` or `0.01`, **not** as smallest units (wei, lamports, or token decimals). Do **not** convert user input (e.g. "0.01 USDT") to chain minimum precision — pass the numeric part as-is (e.g. `--from-amount 0.01`).

### 1. First quote (quote)

- **Script:** `python3 scripts/bitget_agent_api.py quote ...`
- **Request:** fromAddress, fromChain, fromSymbol, fromContract, **fromAmount** (human-readable, e.g. `0.01` for 0.01 USDT), toChain, toSymbol, toContract (empty for native), toAddress (default same as fromAddress).
- **Response:** If `error_code != 0`, show `msg` and stop. The response contains **multiple market results** in `data.quoteResults` (each item has e.g. `market.id`, `market.label`, `outAmount`, `minAmount`, `gasFees`, `slippageInfo.recommendSlippage`).
- **Agent — display all results and recommend the first:**
  - **Show all** entries in `data.quoteResults` to the user (e.g. market label, estimated outAmount, minAmount, gas, slippage recommendation per option).
  - **Recommend the first** result (`quoteResults[0]`) as the default choice.
  - **Let the user choose:** If the user wants to use a different market (e.g. "use the second one" or "use LiquidMesh"), use that selected item's `market.id`, `market.protocol`, and `slippageInfo.recommendSlippage` for the **confirm** step. If the user does not specify, proceed with the first result.

### 2. Second quote (confirm)

- **Script:** `python3 scripts/bitget_agent_api.py confirm ...`
- **Request:** `market` and `protocol` from the **chosen** quote result (default: `data.quoteResults[0].market.id` and `.protocol`; if the user picked another, use that item's `market.id` and `market.protocol`). `slippage` from the same chosen result's `slippageInfo.recommendSlippage`. `features` a single-element array: `["user_gas"]` when user pays gas in native token, else gasless (prefer user_gas when balance is enough).
- **Response:** If `error_code != 0`, show `msg` and stop. Show `data.quoteResult.outAmount`, `data.quoteResult.minAmount`, `data.quoteResult.gasFees.gasTotalAmount`. Store `data.orderId` for makeOrder, send, getOrderDetails.
- **Agent — must show in Second quote stage:** In the confirm step, the agent **must** present to the user the following from the confirm response: **`data.quoteResult.outAmount`** (expected output amount), **`data.quoteResult.minAmount`** (minimum output amount), and **`data.quoteResult.gasFees.gasTotalAmount`** (gas cost). Do not skip displaying these three fields before asking for user confirmation.
- **Agent: handle `data.quoteResult.recommendFeatures` (gas payment):**
  - **`user_gas` or empty string** — User can pay gas with their **main-chain native token** balance; proceed with the swap flow.
  - **gasless** — Main-chain balance is insufficient but **gasless** applies; gas will be paid from **fromSymbol**. Proceed with the swap.
  - **Any other value** — Gas is insufficient and gasLess does not apply. **Do not proceed.** Tell the user that gas is insufficient, the swap cannot be executed, and they need to top up main-chain native token; then stop.

### 3–5. makeOrder, sign, send (combined — recommended)

- **Script:** `python3 scripts/order_make_sign_send.py --mnemonic-file <path> --from-address <addr> --to-address <addr> --order-id <from_confirm> --from-chain ... --from-contract ... --from-symbol ... --to-chain ... --to-contract ... --to-symbol ... --from-amount ... --slippage ... --market ... --protocol ...`
- **Behavior:** Reads mnemonic from file, derives keys in memory, calls makeOrder, signs `data.txs`, fills `txs[].sig`, then sends. Never outputs mnemonic or private keys. Use this so the ~60s makeOrder expiry does not run out.

### 3′–5′. makeOrder, sign, send (separate steps)

Use only when not using the combined script (e.g. external signer, or key from secure storage like 1Password).

- **makeOrder:** `bitget_agent_api.py make-order` with orderId, market, protocol, slippage from confirm. Response `data.txs` expires in ~60s.
- **Sign:** Derive private key from mnemonic in secure storage. Pass full makeOrder response to `order_sign.py` (stdin or `--order-json`) with `--private-key <hex>`. Output is an array of signature hex strings. **Discard the private key immediately after signing.**
- **Fill & send:** Set `data.txs[i].sig` from that array, then `bitget_agent_api.py send --json-stdin` or `--json-file` with body `{ "orderId": data.orderId, "txs": data.txs }`.

### 6. Query order (getOrderDetails)

- **Script:** `python3 scripts/bitget_agent_api.py get-order-details --order-id <orderId>`
- **Request:** orderId from send response `data.orderId`; timestamp optional (default current ms).
- **Response:** If `error_code != 0`, show `msg` and stop. `data.details.status`: `success` means success. `data.details.fromTxId` / `data.details.toTxId`: transaction hashes; same for same-chain, may differ for cross-chain.
- **Agent — handling `tips`:** The getOrderDetails response may include a `tips` field even when the order succeeded. **When `data.details.status === "success"`**, ignore the `tips` field and do not show it to the user. **When status is not success**, use the `tips` field (if present) to inform or prompt the user; combine with other error information as appropriate.

## Confirmation and Compliance

**Rule: Show order details first; sign and send only after explicit user confirmation.**

- The agent must **not** sign or send before the user explicitly confirms (e.g. "confirm", "execute", "yes").
- Confirmation summary should include: orderId, amounts (from confirm or makeOrder), market, slippage, gas estimate, and any risk note.

Recommended flow:

```
0. If no wallet configured → guide user through First-Time Wallet Setup (see SKILL.md); derive and store addresses in context
1. get-processed-balance → verify fromToken balance ≥ fromAmount AND native token > 0 for gas; if insufficient, inform user and stop
2. check-swap-token → for from + to tokens; if error_code != 0 show msg and stop; if checkTokenList non-empty show tips; if toToken has waringType "forbidden-buy" do not proceed and warn
3. security / token-info / liquidity (silent, as applicable)
4. quote → show ALL market results (data.quoteResults) to the user; recommend the first; user may choose another for confirm (use addresses from context for --from-address / --to-address)
5. confirm → use market/protocol/slippage from the chosen quote result (default first); get and show latest quoteResult(data.quoteResult), orderId(data.orderId) and gasFee(data.gasFee); also show tips(data.tips) if not empty
6. PRESENT → show confirmation summary (required)
7. WAIT → user explicitly confirms
8. order_make_sign_send.py (recommended) or make-order → order_sign.py → send (must complete within ~60s)
9. get-order-details → show final status and txId / explorer link
```

## General Swap Knowledge

### EVM token approval

On EVM chains, tokens must be **approved** for the router before spending. Without approval, the swap will revert on-chain and still consume gas.

- Only ERC-20 (and similar) need approval; **native** tokens (ETH, BNB, etc.) do not.
- Approval is typically done once with a large amount; later swaps of the same token can reuse it.
- In the confirmation summary, mention if approval is still needed (one-time gas).

### Slippage and price impact

- **Slippage tolerance:** How much worse than the quote you accept; use quote's `slippageInfo.recommendSlippage` in confirm.
- **Price impact:** Large trades move the pool price; combine with liquidity data. For stable pairs, large slippage is unusual — warn the user.

### Gas and fees

- Gas is paid in the chain's native token; the wallet must have enough or the transaction will fail.
- Security audit `buyTax` / `sellTax` are on top of gas; include in the summary when relevant.

## Order status and result display

- **getOrderDetails:** `data.details.status === "success"` means success; show `fromTxId` / `toTxId` and block explorer links. When status is success, ignore the response `tips` field. When status is not success, use the `tips` field to prompt the user and suggest retry or adjusting amount/slippage if appropriate.

## Block explorer URLs

| Chain | Explorer URL |
|-------|---------------|
| eth | `https://etherscan.io/tx/{txId}` |
| bnb | `https://bscscan.com/tx/{txId}` |
| base | `https://basescan.org/tx/{txId}` |
| arbitrum | `https://arbiscan.io/tx/{txId}` |
| matic | `https://polygonscan.com/tx/{txId}` |
| optimism | `https://optimistic.etherscan.io/tx/{txId}` |
| sol | `https://solscan.io/tx/{txId}` |
| trx | `https://tronscan.org/#/transaction/{txId}` |

## Common pitfalls

1. **Always check balance before swap:** Run `get-processed-balance` before quote. The confirm API returns misleading error `40001: Demo trading failed. Please increase slippage.` when the actual issue is insufficient balance — always verify balance first.
2. **Human-readable amounts:** In the swap flow, **fromAmount** (and toAmount, fromAmount in makeOrder, etc.) are always **human-readable** (e.g. `0.01` for 0.01 USDT, `1` for 1 token). Do **not** convert to smallest units (wei, lamports, or token decimals); pass the value as the user would say it (e.g. `--from-amount 0.01`).
3. **Native token contract:** Use empty string `""` for toContract/fromContract when the token is native.
4. **Do not submit twice:** One confirmation, one sign+send; duplicate submit can double-spend.
5. **makeOrder data expiry:** Unsigned txs from makeOrder are valid ~60s; use **order_make_sign_send.py** or sign and send immediately after makeOrder to avoid expiry.
6. **Chain codes:** Use API chain codes (`bnb`, `sol`, `eth`), not aliases (`bsc`, `solana`).

For request/response details, see the script help: `python3 scripts/bitget_agent_api.py <command> --help`.
