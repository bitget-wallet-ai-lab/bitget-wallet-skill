# Commands Reference

Detailed subcommand parameters and usage examples for all scripts.

## `scripts/bitget_agent_api.py`

Unified API client: swap flow + balance + token search + market data. No API key required.

### Subcommand Table

| Subcommand | What it does | When to use |
|------------|----------------|-------------|
| `check-swap-token` | Checks fromToken and toToken for risks before swap. Pass both tokens via `--from-*`/`--to-*` or `--json-stdin` with `{ "list": [{ chain, contract, symbol }, ...] }`. Returns `data.list[].checkTokenList`; empty = no risk. If any item has `waringType` `"forbidden-buy"`, that token **must not** be used as swap target (toToken). | **Before every new swap:** run this for the intended from and to tokens; if risks are reported, show `tips` to the user; if toToken has `forbidden-buy`, do not proceed and warn. |
| `get-processed-balance` | Returns processed balance(s) for a chain+address, optionally per token (contract `""` = native). Accepts `--chain`/`--address`/`--contract` or JSON body via `--json-stdin`. | User asks for balance; before swap to verify sufficient balance; Only evm and Solana. |
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
| `confirm` | Second quote: locks in **one** market (the chosen one from quote), returns `data.orderId` and `data.quoteResult`. Use market/protocol/slippage from the **selected** quote result (default first; or the item user chose). | Step 2 of swap: get orderId and latest quoteResult for makeOrder/send using the user's chosen market. |
| `make-order` | Creates order; returns unsigned `data.txs` (expires ~60s). | Only if not using `order_make_sign_send.py`; otherwise use combined script. |
| `send` | Submits signed order: body is `{ "orderId", "txs" }` with `txs[].sig` filled. Input via `--json-stdin` or `--json-file`. | After signing makeOrder txs (e.g. via `order_sign.py`); or use `order_make_sign_send.py` for combined flow. |
| `get-order-details` | Returns order status and result (e.g. `data.details.status`, `fromTxId`, `toTxId`). | After send: show user whether swap succeeded and tx links. |

### Usage Examples

```bash
# Token risk check before swap
python3 scripts/bitget_agent_api.py check-swap-token --from-chain bnb --from-contract <addr> --from-symbol USDT --to-chain bnb --to-contract "" --to-symbol BNB
# Or via JSON stdin:
echo '{"list":[{"chain":"bnb","contract":"","symbol":"BNB"},{"chain":"bnb","contract":"0x...","symbol":"AIO"}]}' | python3 scripts/bitget_agent_api.py check-swap-token --json-stdin

# Balance (chain + address; contract "" = native, or pass multiple --contract); Only evm and Solana
python3 scripts/bitget_agent_api.py get-processed-balance --chain bnb --address <wallet_evm> [--contract "" --contract <token_contract>]
echo '{"list":[{"chain":"bnb","address":"0x...","contract":["","0x..."]}]}' | python3 scripts/bitget_agent_api.py get-processed-balance --json-stdin

# Balance + token price (batch-v2)
python3 scripts/bitget_agent_api.py batch-v2 --chain bnb --address <wallet_evm> [--contract "" --contract <token_contract>]

# Search tokens
python3 scripts/bitget_agent_api.py search-tokens --keyword USDT
python3 scripts/bitget_agent_api.py search-tokens --keyword USDT --chain bnb

# Token list for a chain
python3 scripts/bitget_agent_api.py get-token-list --chain bnb

# Market data
python3 scripts/bitget_agent_api.py token-info --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955
python3 scripts/bitget_agent_api.py token-price --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955
python3 scripts/bitget_agent_api.py batch-token-info --tokens "bnb:0x55d3...,eth:0xdAC1..."
python3 scripts/bitget_agent_api.py kline --chain bnb --contract 0x55d3... --period 1h --size 24
python3 scripts/bitget_agent_api.py tx-info --chain bnb --contract 0x55d3...
python3 scripts/bitget_agent_api.py batch-tx-info --tokens "bnb:0x...,eth:0x..."
python3 scripts/bitget_agent_api.py historical-coins --create-time "2026-02-27 00:00:00" --limit 20
python3 scripts/bitget_agent_api.py rankings --name topGainers    # or topLosers, Hotpicks
python3 scripts/bitget_agent_api.py liquidity --chain bnb --contract 0x55d3...
python3 scripts/bitget_agent_api.py security --chain bnb --contract 0x55d3...

# Swap flow
# 1. Quote
python3 scripts/bitget_agent_api.py quote --from-address <wallet> --from-chain bnb --from-symbol USDT --from-contract <addr> --from-amount 0.01 --to-chain bnb --to-symbol BNB --to-contract ""
# 2. Confirm
python3 scripts/bitget_agent_api.py confirm --from-chain bnb --from-symbol USDT --from-contract <addr> --from-amount 0.01 --from-address <wallet> --to-chain bnb --to-symbol BNB --to-contract "" --to-address <wallet> --market <market.id> --protocol <market.protocol> --slippage <recommendSlippage>
# 3. makeOrder (separate)
python3 scripts/bitget_agent_api.py make-order --order-id <orderId> --from-chain bnb --from-contract <addr> --from-symbol USDT --to-chain bnb --to-contract "" --to-symbol BNB --from-address <wallet> --to-address <wallet> --from-amount 0.01 --slippage 1.00 --market bgwevmaggregator --protocol bgwevmaggregator_v000 > /tmp/makeorder.json
# 4. Sign
python3 scripts/order_sign.py --order-json "$(cat /tmp/makeorder.json)" --private-key-file <key_file> > /tmp/sigs.json
# 5. Send (fill txs[i].sig from sigs, then send)
# 6. Order status
python3 scripts/bitget_agent_api.py get-order-details --order-id <orderId>
```

---

## `scripts/order_make_sign_send.py`

One-shot makeOrder + sign + send. Supports EVM and Solana. Auto-detects chain from makeOrder response.

| When to use | When NOT to use |
|-------------|-----------------|
| After user confirms swap: run with orderId and params from confirm. | If signing with an external signer (e.g. hardware wallet), use make-order → sign externally → send instead. |

```bash
# EVM
python3 scripts/order_make_sign_send.py --private-key-file /tmp/.pk_evm --from-address <addr> --to-address <addr> --order-id <from_confirm> --from-chain bnb --from-contract <addr> --from-symbol USDT --to-chain bnb --to-contract "" --to-symbol BNB --from-amount 0.01 --slippage 1.00 --market bgwevmaggregator --protocol bgwevmaggregator_v000
# Solana
python3 scripts/order_make_sign_send.py --private-key-file-sol /tmp/.pk_sol --from-address <sol_addr> --to-address <sol_addr> --order-id <from_confirm> --from-chain sol --from-contract <mint> --from-symbol USDC --to-chain sol --to-contract <mint> --to-symbol USDT --from-amount 5 --slippage 0.01 --market ... --protocol ...
```

---

## `scripts/order_sign.py`

Sign order/makeOrder transaction data. Takes makeOrder response JSON, signs `data.txs`, outputs JSON array of signature hex strings.

Supports: EVM raw tx signing, EVM gasPayMaster (gasless msgs eth_sign), EIP-712 typed data, Solana Ed25519, Solana gasPayMaster (partial-sign on serializedTransaction).

```bash
# EVM
echo '<makeOrder_json>' | python3 scripts/order_sign.py --private-key-file <key_file>
python3 scripts/order_sign.py --order-json "$(cat /tmp/makeorder.json)" --private-key-file <key_file>
# Solana
echo '<makeOrder_json>' | python3 scripts/order_sign.py --private-key-sol <base58>
```

---

## `scripts/x402_pay.py`

x402 payment signing and pay flow (EIP-3009 USDC payments, Solana partial-sign).

| Subcommand | What it does |
|------------|----------------|
| `sign-eip3009` | Signs an EIP-3009 transfer (e.g. USDC on Base) |
| `sign-solana` | Partially signs a Solana transaction for x402 |
| `pay` | Auto-detects 402 response, signs, pays, fetches resource |

```bash
python3 scripts/x402_pay.py sign-eip3009 --private-key-file <key_file> --token <usdc> --chain-id 8453 --to <payTo> --amount 10000
python3 scripts/x402_pay.py sign-solana --private-key-file <key_file> --transaction <base64_tx>
python3 scripts/x402_pay.py pay --url https://api.example.com/data --private-key-file <key_file>
```
