# Commands Reference

Full parameters for any command: `python3 scripts/<script>.py <subcommand> --help`

## `scripts/bitget_agent_api.py`

Unified API client. No API key required.

### Subcommands

| Subcommand | Purpose |
|------------|---------|
| `check-swap-token` | Token risk check (from/to). Non-empty `checkTokenList` = risk; `forbidden-buy` = stop |
| `get-processed-balance` | Balance per token (contract `""` = native). EVM and Solana only |
| `batch-v2` | Balance + token price in one call |
| `search-tokens` | Search by keyword or contract. Optional `--chain` filter |
| `get-token-list` | All tokens on a chain |
| `token-info` | Single token info (name, symbol, price, etc.) |
| `token-price` | Single token price |
| `batch-token-info` | Multi-token info (`--tokens "chain:addr,chain:addr"`) |
| `kline` | K-line/OHLC (`--period` 1s/1m/5m/15m/30m/1h/4h/1d/1w; `--size` max 1440) |
| `tx-info` | Recent tx stats (buy/sell volume) |
| `batch-tx-info` | Multi-token tx stats |
| `historical-coins` | Recently launched tokens (`--create-time "YYYY-MM-DD HH:MM:SS"`) |
| `rankings` | Token rankings (`--name topGainers/topLosers/Hotpicks`) |
| `liquidity` | Liquidity pool info |
| `security` | Security audit (highRisk, buyTax/sellTax, etc.) |
| `quote` | First quote — returns multiple markets. Display all, recommend first |
| `confirm` | Second quote — locks one market, returns `orderId` + `quoteResult` |
| `make-order` | Creates unsigned order (expires ~60s). Use combined script instead |
| `send` | Submits signed order (`--json-stdin` or `--json-file`) |
| `get-order-details` | Order status + result |
| **RWA** | |
| `rwa-get-user-ticker-selector` | List available RWA stocks per chain |
| `rwa-get-config` | RWA configuration |
| `rwa-stock-info` | Stock info (GET, `--ticker`) |
| `rwa-stock-order-price` | Real-time order price |
| `rwa-kline` | Stock K-line |
| `rwa-get-my-holdings` | User's RWA holdings |

### Usage Examples

```bash
# Token risk check
python3 scripts/bitget_agent_api.py check-swap-token --from-chain bnb --from-contract <addr> --from-symbol USDT --to-chain bnb --to-contract "" --to-symbol BNB

# Balance
python3 scripts/bitget_agent_api.py get-processed-balance --chain bnb --address <wallet> --contract "" --contract <token>

# Market data
python3 scripts/bitget_agent_api.py token-info --chain bnb --contract <addr>
python3 scripts/bitget_agent_api.py kline --chain bnb --contract <addr> --period 1h --size 24
python3 scripts/bitget_agent_api.py security --chain bnb --contract <addr>
python3 scripts/bitget_agent_api.py rankings --name topGainers

# Swap flow
python3 scripts/bitget_agent_api.py quote --from-address <wallet> --from-chain bnb --from-symbol USDT --from-contract <addr> --from-amount 5 --to-chain bnb --to-symbol BNB --to-contract ""
python3 scripts/bitget_agent_api.py confirm ... --market <id> --protocol <proto> --slippage <val> --features '["user_gas"]'
python3 scripts/bitget_agent_api.py get-order-details --order-id <id>
```

## `scripts/order_make_sign_send.py`

One-shot makeOrder + sign + send. Auto-detects chain. Use after user confirms swap.

```bash
python3 scripts/order_make_sign_send.py --private-key-file <tmpfile> --from-address <addr> --to-address <addr> --order-id <id> --from-chain bnb --from-contract <addr> --from-symbol USDT --to-chain bnb --to-contract "" --to-symbol BNB --from-amount 5 --slippage 0.005 --market <id> --protocol <proto>
```

## `scripts/order_sign.py`

Sign makeOrder data independently. Outputs JSON array of signatures.

```bash
echo '<makeOrder_json>' | python3 scripts/order_sign.py --private-key-file <tmpfile>
python3 scripts/order_sign.py --order-json '<json>' --private-key-file-sol <tmpfile>
```

## `scripts/x402_pay.py`

x402 payment (EIP-3009, Solana partial-sign, HTTP 402).

```bash
python3 scripts/x402_pay.py sign-eip3009 --private-key-file <tmpfile> --token <usdc> --chain-id 8453 --to <payTo> --amount 10000
python3 scripts/x402_pay.py pay --url <url> --private-key-file <tmpfile>
```
