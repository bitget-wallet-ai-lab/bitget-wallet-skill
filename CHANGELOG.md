# Changelog

All notable changes to the Bitget Wallet Skill are documented here.

Format: date-based versioning (`YYYY.M.DD`). Each release includes a sequential suffix: `YYYY.M.DD-1`, `YYYY.M.DD-2`, etc. Each entry includes changes, and a security audit summary for transparency.

---

## [2026.4.15-1] - 2026-04-15

### Added — Multi-Agent Signal (bgw_alpha)

- `scripts/bitget-wallet-agent-api.py` — Added `multi-agent-signal` subcommand (`POST /market/v3/agent/signals`). Surfaces tokens where multiple Agent-tagged addresses are buying (cross-strategy consensus), complementing the existing single-strategy `alpha-signals`. Response includes triggering Agent `tags` and per-address `buy_amount` / `order_count`.
- `docs/alpha.md` — Added `multi_agent_signal` section with parameters, response schema, and usage examples. Bumped intro from "Six watch_types" to "Seven watch_types". Added entry to the Alpha discovery flow.
- `SKILL.md` — Added `multi-agent-signal` to the Alpha Intelligence row of the top-level "Before calling" table and to the `bgw_alpha` use-case table.

---

## [2026.4.13-1] - 2026-04-13

### Added — Token Transfer with Gasless Support (bgw_transfer)

- `scripts/transfer_make_sign_send.py` — One-shot transfer (mnemonic/private-key): makeTransferOrder + sign + submit. Supports EVM (legacy/1559/7702) and Solana (raw/partial). `--gasless` flag for gasless mode.
- `scripts/social_transfer_make_sign_send.py` — One-shot transfer (Social Login Wallet): makeTransferOrder + sign (TEE) + submit. No local private key needed. `--gasless` supported.
- `scripts/bitget-wallet-agent-api.py` — Added `get-transfer-order` subcommand for polling order status.
- `docs/transfer.md` — Domain knowledge: flow, gasless mode, signing modes, Morph AltFee, chain notes, error codes.
- Updated `SKILL.md` — Added `bgw_transfer` tool section, domain knowledge table, scripts table, quick reference. Version bumped to 2026.4.13-1.
- Updated `README.md` — Added Token Transfer / Gasless Transfer to core capabilities and usage examples.

---

## [2026.3.27-1] - 2026-03-27

### Added — Token Deep Analysis (bgw_token_analyze)
- **`simple-kline`** — K-line with KOL/smart money trade signals and hot level indicator (`POST /market/v2/coin/SimpleKline`). Supports signal overlays: KOL, smart money, developer. Includes `kolSmartHotLevel` (low/medium/high) and per-candle `tagUserStats`.
- **`trading-dynamics`** — Multi-window trading dynamics (5m/1h/4h/24h) in a single call (`POST /market/v2/coin/GetTradingDynamics`). Returns AI-generated summary, buy/sell pressure, address quality distribution (A/B/C/wash), amount distribution, and tagged address fund flow.
- **`transaction-list`** — Transaction records with tag/direction/time filtering (`POST /market/v2/coin/TransactionList`). Supports `--only-barrage` for tagged-only transactions, `--txnfrom-tags` for fine-grained tag filtering (smart_money/kol/developer/bot/manipulator), direction and time window filters.
- **`holders-info`** — Top 100 holders with classification (CEX/smart money/KOL/manipulator) and PnL (`POST /market/v2/GetHoldersInfo`). Sort by holding or PnL, filter by special holder type or address tags.
- **`profit-address-analysis`** — Profitable address summary statistics (`POST /market/v2/coin/GetProfitAddressAnalysis`). Position dynamics (add/hold/reduce/close) with user type breakdown (kol/smart_money/manipulator), profit distribution ranges.
- **`top-profit`** — Top profitable addresses list with PnL details (`POST /market/v2/coin/GetTopProfit`). Per-address: total profit, profit rate, latest position action, user tags, quality grade.
- **`compare-tokens`** — Side-by-side K-line comparison of two tokens. Calls SimpleKline twice, aligns by timestamp, outputs unified `{ts, price_a, price_b, volume_a, volume_b, marketCap_a, marketCap_b}`.

### Added — Address Discovery (bgw_address_find)
- **`recommend-address-list`** — Find addresses by role (KOL / smart money) with performance filters (`POST /market/v2/monitor/recommend-group/address/list`). Filter by chain, win rate, profit, trade count. Sort by profit/win rate/trade count/last activity. Time windows: 24h/7d/30d. Returns per-address: profit_analysis (win_rate, total_profit, tx_count, daily profit_list), holdings, address_tags, social links.

### Added — Documentation
- `docs/token-analyze.md` — Complete domain knowledge: per-command parameters, response fields, recommended analysis flow, key field reference, trading signal identification matrix.
- `docs/address-find.md` — Domain knowledge: parameters, response fields, role groups, filters, usage examples, key signals.
- Updated `docs/market-data.md` — Added bgw_token_analyze reference section with API mapping table.
- Updated `docs/commands.md` — Added 8 new subcommand references with usage examples (7 token analyze + 1 address find).
- Updated `SKILL.md` — Added bgw_token_analyze to domain knowledge table, market tools architecture, extended knowledge table, scripts table, and quick reference.
- Updated `README.md` — Added 7 new capabilities to core capabilities table (6 token analyze + 1 address find).

### Audit
- No new external dependencies added
- All 8 endpoints are read-only market data APIs (no fund movement, no signing)
- No credentials or secrets involved
- All APIs verified working via live calls against production endpoint

---

## [2026.3.23-1] - 2026-03-23

### Added — Social Login Wallet
- `scripts/social-wallet.py` — 174-line Python CLI for signing transactions and messages via Bitget Wallet TEE (Trusted Execution Environment). Private keys never leave the TEE; agent authenticates with appid/appsecret.
- `docs/social-wallet.md` — Complete integration guide: per-chain parameters (BTC/ETH/SOL/Tron + 16 EVM chains), 3 signing modes for swap flow (gasPayMaster, regular EVM tx, Tron tx), common mistakes table.
- Supports: BTC (Taproot/SegWit/Legacy/PSBT), ETH, SOL (native+SPL+versioned), Tron, and all EVM chains via `evm_custom#` prefix.
- Operations: `sign_transaction`, `sign_message`, `get_address`, `get_public_key`, `validate_address`, `batchGetAddressAndPubkey`.

### Added — Swap Integration with Social Login Wallet
- 3 signing modes documented and verified:
  - **gasPayMaster (gasless):** `EthSign:{hash}` via `sign_message` → `msg["sig"]` → `json.dumps(msgs)` — works for both same-chain and cross-chain gasless swaps
  - **Regular EVM tx:** `sign_transaction` → signed RLP hex
  - **Tron tx:** `sign_transaction` returns raw 65-byte sig hex → must be wrapped in `{"signature":[hex],"txID":...,"raw_data":...}`
- Critical rule: always check `deriveTransaction.msgs` first to detect gasPayMaster mode, even for cross-chain txs

---

## [2026.3.20-1] - 2026-03-20

### Added — Market Tools (bgw_token_find + bgw_token_check)
- **`launchpad-tokens`** — Scan launchpad new pools (pump.fun, four.meme, virtuals, etc.) with 15+ filters: chain, platform, stage, age, MC, LP, volume, holders, bonding progress, sniper %, keywords. Supports 19 platforms across Solana/BNB/Base.
- **`search-tokens-v3`** — Token search with `order_by` support (e.g. market_cap). Returns risk_level, holder stats, dev metrics per token. `POST /market/v3/coin/search`
- **`coin-market-info`** — Full token market overview: price, MC, FDV, liquidity, turnover, holders, age, price changes (5m/1h/4h/24h), all trading pairs with protocol and liquidity, narrative description and tags. `POST /market/v3/coin/getMarketInfo`
- **`coin-dev`** — Dev historical project analysis: returns full list of dev's tokens with rug_status (0=safe, 1=rugged), migration status, MC, LP per project. Supports `--limit` and `--is-migrated` filter. `POST /market/v3/coin/dev`

### Added — Market Tools Architecture
- Defined 7-tool architecture: 5 atomic tools (bgw_token_find, bgw_token_check, bgw_token_analyze, bgw_address_find, bgw_address_analyze) + 2 smart tools (bgw_combo, bgw_monitor)
- bgw_token_find and bgw_token_check fully documented with API mappings, Skills-layer computation rules (Pool TIER rating, Dev trust scoring, liquidity health, risk signal matrix), and common strategies

### Changed — Documentation
- `docs/market-data.md` — Complete rewrite with bgw_token_find and bgw_token_check domain knowledge, labelName reference tables (EVM + Solana), risk signal matrix (12 signals), recommended check flow
- `SKILL.md` — Added Market Tools Architecture section, updated Scripts table and Quick Reference with new commands
- `README.md` — Added Market Tools Architecture diagram and new capabilities
- All skill content converted to English (SKILL.md, docs/market-data.md, README.md)
- Mandatory output rule: all token discovery results must include chain + full contract address

### Fixed
- SKILL.md: `--private-key` → `--private-key-file` in Scripts table and Common Pitfalls (stale after PR #33)
- SKILL.md: Swap-supported chains count 7 → 8 (Tron was missing from count)

### Security
- No new dependencies added
- No credential changes
- 4 new read-only market data endpoints (no fund-moving operations)

---

## [2026.3.17-1] - 2026-03-17

### Added — RWA Stock Trading
- 6 new API commands for Real World Assets (tokenized stocks): `rwa-get-user-ticker-selector`, `rwa-get-config`, `rwa-stock-info` (GET), `rwa-stock-order-price`, `rwa-kline`, `rwa-get-my-holdings`
- `docs/rwa.md` — Complete RWA stock trading guide: ticker discovery, buy/sell flow, market hours, agent rules
- 262 tokenized stocks available (NVDA, TSLA, AAPL, SPY, QQQ, etc.) on BNB and ETH chains
- RWA buy/sell minimum: $20 USD; routed via 1inch Fusion (signTypeData EIP-712)

### Added — Tron Chain Support
- Tron (TRX) transaction signing: `sign_order_txs_tron()` in `order_sign.py`
- `--private-key-tron` CLI argument in `order_make_sign_send.py`
- EIP-712 `signTypeData` support: `_sign_eip712_sign_type_data()` for RWA orders
- Tron chain added to SKILL.md Chain Identifiers (code `trx`, ID `728126428`)
- Tron USDT (`TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`) added to contract table

### Added — New API Method
- `_request_get()` in `bitget-wallet-agent-api.py` — GET requests with BKHmacAuth signing (used by `rwa-stock-info`)

### Changed
- Request headers updated: `brand` → `toc_agent`, `channel` → `0.0.1` (was `IOS` / `9.36.0`)
- `get-processed-balance` description updated: balance query supports EVM and Solana only

### Fixed
- Checksum `to` address in approve tx signing — `eth_account` rejects non-checksum addresses
- Tron signature: use standard low-S form (removed incorrect high-S conversion)

### Documentation
- Tron gasless threshold documented: ≥ $10,000 USD (practically requires `user_gas` with TRX for Energy)
- Tron compatibility added to README.md

### Security Audit
- No new API keys or secrets introduced
- Tron signing uses same secp256k1 curve as EVM; private key handled identically (in-memory only)
- RWA commands use existing BKHmacAuth; no additional authentication required

---

## [2026.3.13-1] - 2026-03-13

### Breaking Changes
- **New API endpoint**: Migrated from `bopenapi.bgwapi.io` (HMAC auth) to `copenapi.bgwapi.io` (token auth, no API key needed)
- **New swap flow**: `quote → confirm → makeOrder → sign+send → getOrderDetails` replaces old `order-quote → order-create → sign → order-submit → order-status`
- **Removed**: `scripts/bitget_api.py` (legacy API client) — replaced by `scripts/bitget-wallet-agent-api.py`
- **Removed**: `docs/trading.md` — replaced by `docs/swap.md`

### Added — New Scripts
- `scripts/bitget-wallet-agent-api.py` — Unified API client: swap flow + balance + token search + market data (no API key required)
- `scripts/order_make_sign_send.py` — One-shot makeOrder + sign + send (EVM `--private-key` + Solana `--private-key-sol`)

### Added — New API Commands
- `check-swap-token` — Pre-swap token risk check (forbidden-buy detection)
- `get-processed-balance` — On-chain balance query per address/chain/token
- `batch-v2` — Balance + token price in one call (portfolio valuation)
- `search-tokens` — Search tokens by keyword or contract address
- `get-token-list` — Popular tokens per chain
- `confirm` — Second quote with locked market, orderId, and gas estimation

### Added — New Documentation
- `docs/swap.md` — Complete new swap flow with pre-trade checks, multi-market quote display, and confirmation rules
- `docs/commands.md` — Full subcommand reference (moved from SKILL.md to reduce token cost)
- `COMPATIBILITY.md` — Platform compatibility guide (tested: OpenClaw, Manus, Bolt.new, Devin, Replit Agent)

### Added — Gasless + Cross-chain
- **Solana gasless fully supported** — same-chain and cross-chain (Sol↔EVM) gasless transactions
  - Solana gasPayMaster mode: partial-sign on `source.serializedTransaction`
  - EVM gasPayMaster mode: `msgs[]` with `eth_sign` hash signing, returns full msgs JSON struct
  - Detection: `chain="sol"` field + `source.serializedTransaction` in deriveTransaction
- **Cross-chain minimum:** $10 USD for cross-chain swaps

### Changed — Swap Flow
- Quote now returns **multiple market results** (`data.quoteResults`); agent must display all and recommend the first
- Confirm step locks one market and returns `orderId` + final `quoteResult`
- `recommendFeatures` in confirm response indicates gas payment mode (`user_gas` / `no_gas` for gasless)
- **Balance check required before swap** — `get-processed-balance` must run before quote to prevent misleading `40001` errors
- **features selection clarified**: `user_gas` when native balance sufficient, `no_gas` when near zero

### Changed — Wallet Management
- Private key from secure storage, used in memory only, discarded after signing
- Mnemonic and private keys never appear in conversation, logs, or output

### Changed — SKILL.md Optimization
- Slimmed from 25KB → 14.5KB (42% reduction); detailed params moved to `docs/commands.md`

### Fixed
- Python 3.9 compatibility: added `from __future__ import annotations` for `str | None` type hints
- Solana chain detection: support `chain="sol"` field and `source.serializedTransaction` when chainId is absent
- EVM gasPayMaster signing: return full msgs JSON struct instead of single sig string

### Tested
- BNB same-chain user_gas: 5 USDT → 4.996 USDC ✅
- BNB same-chain gasless: 6 USDC → 5.96 USDT ✅ (order `b20d32fb`)
- BNB→Base cross-chain user_gas: 5 USDT → 4.983 USDC ✅
- Base→BNB cross-chain gasless: 5 USDC → 4.97 USDT ✅ (order `bab6c9be`)
- BNB→Sol cross-chain user_gas: 10 USDT → 9.96 USDC ✅ (order `7c84e5dc`)
- Sol same-chain gasless: 5.5 USDT → 5.38 USDC ✅ (order `bf6aafd0`)
- Sol→BNB cross-chain gasless: 18 USDC → 17.93 USDT ✅ (order `4483c8ea`)

### Audit
- ✅ New API base `copenapi.bgwapi.io` uses token-based auth (no API key/secret needed)
- ✅ Market data endpoints (`/market/v3/*`) work on new API after whitelist
- ✅ `order_sign.py` supports: raw tx, EVM gasPayMaster (eth_sign), EIP-712, Solana Ed25519, Solana gasPayMaster
- ✅ Full swap flow verified across EVM and Solana, same-chain and cross-chain, user_gas and gasless
- ✅ No new external dependencies beyond existing `eth_account` + `requests`

---

## [2026.3.10-1] - 2026-03-10

### Updated — Sync with Official API Docs
- **Chain identifiers expanded** from 10 → 33 chains, split into Order Mode (7 chains) and Market Data (32 chains) tables
- **Gasless thresholds unified** — all chains $5 USD, Morph $1 USD (previously documented as "~$5-6")
- **Error codes completed** — full 80000-80015 error code table with descriptions and actions
- **Security audit labelName reference** — complete Solana (11 checks) and EVM (17 checks) mapping tables added to market-data.md
- **Token info social fields** documented — twitter, website, telegram, whitepaper, about
- **K-line buy/sell breakdown fields** documented — buyTurnover, sellTurnover, buyAmount, sellAmount
- **fromAmount human-readable** explicitly documented in order quote section
- **fee.gasFee** and EIP-7702 response fields added to order quote docs
- **README updated** — supported chains split (order vs market data), capabilities table expanded, gasless description updated to include Solana

---

## [2026.3.9-3] - 2026-03-09

### Fixed
- **signedTxs double-serialization bug** — `order-submit` now auto-parses JSON array strings
  - Root cause: `order_sign.py` outputs JSON array, but `--signed-txs` treated the entire string as one argument
  - Fix: `cmd_order_submit` detects and flattens JSON array input
  - Updated SKILL.md and trading.md with correct usage examples

---

## [2026.3.9-2] - 2026-03-09

### Added
- **Hotpicks ranking support** — `rankings --name Hotpicks` returns curated trending tokens across chains
  - Complements existing `topGainers` / `topLosers` rankings
  - Updated SKILL.md command examples, market-data.md domain knowledge, and README.md

---

## [2026.3.9-1] - 2026-03-09

### Fixed
- **Solana gasless IS supported** — corrected previous conclusion that Solana didn't support gasless
  - Gasless has a **minimum amount threshold (~$5-6 USD)** — below threshold, `features: []`; above, `features: ["no_gas"]`
  - Same-chain gasless verified: 6 USDC → 5.76 USDT ✅
  - Cross-chain gasless verified: 20 USDC (Sol) → 19.87 USDC (Base) ✅
  - Updated all docs: trading.md, wallet-signing.md, README.md

### Tested
- Solana same-chain gasless (order `6e31ea59`) — pure Python Ed25519 signing ✅
- Sol→Base cross-chain gasless (order `d106d921`) — 20 USDC, ~20s completion ✅
- Pure Python signing (zero external deps) works flawlessly for gasless 2-signer transactions

---

## [2026.3.6-3] - 2026-03-06

### Added
- x402 payment protocol support: domain knowledge (`docs/x402-payments.md`) + payment client (`scripts/x402_pay.py`)
- EIP-3009 (transferWithAuthorization) signing for USDC gasless payments
- Solana partial-sign for x402 payment transactions
- Full HTTP 402 flow: fetch → parse requirements → sign → retry with `PAYMENT-SIGNATURE` header
- Budget & safety controls documentation for agent spending
- Pinata IPFS upload testing guide in x402 domain knowledge
- Design Principles section in README (domain knowledge + tools, zero external deps, API infrastructure)

### Fixed
- EIP-712 signing: replaced `encode_typed_data` with manual hash computation (bytes32 encoding mismatch with facilitators)
- `validAfter` clock skew: now uses `now - 600` (10-minute tolerance, matches official SDK)
- Authorization return values now derived from signed message (prevents signature/payload mismatch)

### Tested
- Pinata IPFS private upload on Base mainnet ✅ — $0.001 USDC, settlement TX `0x5bbfe577d39da850bd29483b859a7edd07f3a0d92701177d3ed889af7fcca556`
- x402.org facilitator verify (Base Sepolia) ✅ — `isValid: true`

### Audit
- ✅ No new external dependencies — uses only `eth_account`, `eth_abi`, `eth_utils`, `requests` (all pre-installed)
- ✅ x402_pay.py is self-contained, independent from bitget_api.py
- ✅ No credential changes
- ✅ Only communicates with user-specified x402 resource servers + facilitators

---

## [2026.3.5-2] - 2026-03-05

### Added
- Morph USDT0 contract address: `0xe7cd86e13AC4309349F30B3435a9d337750fC82D`
- BGB (Bitget Token) addresses: Ethereum `0x54D2252757e1672EEaD234D27B1270728fF90581`, Morph `0x389C08Bc23A7317000a1FD76c7c5B0cb0b4640b5`
- Cross-chain limits reference table (liqBridge + CCTP per chain)
- Market field in order confirmation summary (e.g., `bgwAggregator`, `bkbridgev3.liqbridge`)

### Fixed
- Solana gasless status: changed from "❌ Not working (bug)" to "❌ Not supported" — gasless is not available on Solana (quote returns `features: []`)
- Gasless rule: only use gasless when quote returns `"no_gas"` in `features` array (API accepts flag without validation but execution fails)
- Cross-chain minimum amounts: Solana $10, Morph $5 (previously documented as ~$2 for all)

---

## [2026.3.5-1] - 2026-03-05

### Added
- **Order Mode API**: 4 new commands for the order-based swap model
  - `order-quote` — get swap price with cross-chain and gasless support
  - `order-create` — create order, receive unsigned tx/signature data
  - `order-submit` — submit signed transactions
  - `order-status` — query order lifecycle status
- **Cross-chain swaps**: swap tokens between different chains in one order (e.g., USDC on Base → USDT on Polygon)
- **Gasless mode**: pay gas with input token, no native token needed (EVM only)
- **EIP-7702 support**: EIP-712 typed data signing for gasless execution
- **Order status tracking**: full lifecycle (init → processing → success/failed/refunding/refunded)
- **B2B fee splitting**: `feeRate` parameter for partner commission
- **New chain**: Morph (`morph`) supported in order mode
- Domain Knowledge: order flow, gasless auto-detection, EIP-7702 signing, polling strategy, error codes
- Solana signing support: VersionedTransaction partial signing via solders

### Changed
- Solana gasless marked as not working (order mode submit succeeds but execution always fails)
- Cross-chain to-sol marked as known bug (API team investigating)
- toAddress required in order-quote for non-EVM cross-chain targets (was causing 80000)

### Tested
- Base same-chain gasless ✅ (USDC → USDT, multiple orders)
- Base → Polygon cross-chain gasless ✅
- Base → Solana cross-chain: quote/create/sign/submit flow working, gasless pending API fix
- Solana same-chain: signing verified correct, gasless execution fails
- Polygon same-chain gasless ✅; Polygon cross-chain requires 7702 binding first

### Audit
- ✅ `bitget_api.py`: 4 new functions added, no existing logic changed
- ✅ All new endpoints use same `bopenapi.bgwapi.io` base URL
- ✅ Same auth mechanism (HMAC-SHA256 + Partner-Code)
- ✅ No new dependencies
- ✅ No credential changes

---

## [2026.3.2-1] - 2026-03-02

### Security
- Default swap deadline reduced from 600s to 300s (mitigates sandwich attacks)
- Security checks now **mandatory for unfamiliar tokens**, regardless of user preference
- Addresses SlowMist CISO feedback ([CryptoNews article](https://cryptonews.net/news/security/32491385/))

### Added
- **First-Time Swap Configuration**: Agent guides users through deadline and security check preferences on first swap
- `--deadline` parameter for `swap-calldata` command (custom on-chain transaction expiry)
- Version management with `CHANGELOG.md` and version awareness in Domain Knowledge

### Audit
- ✅ No new dependencies added
- ✅ No credential or authentication changes
- ✅ Script changes: `bitget_api.py` (+3 lines — deadline parameter passthrough only)
- ✅ SKILL.md changes: Domain Knowledge additions only (no tool behavior changes)

---

## [2026.2.27-1] - 2026-02-27

### Changed
- Corrected `historical-coins` parameter documentation (`createTime` format)
- Renamed skill from "Bitget Wallet Trade Skill" to "Bitget Wallet Skill"

### Audit
- ✅ Documentation-only changes
- ✅ No script modifications

---

## [2026.2.20-1] - 2026-02-20

### Added
- Initial release
- Full API coverage: token-info, token-price, batch-token-info, kline, tx-info, batch-tx-info, rankings, liquidity, historical-coins, security, swap-quote, swap-calldata, swap-send
- Domain Knowledge: amounts, swap flow, security audit interpretation, slippage control, gas/fees, EVM approval, common pitfalls
- Built-in public demo API credentials
- Stablecoin address reference table (7 chains)

### Audit
- ✅ No external dependencies beyond Python stdlib + requests
- ✅ Demo API keys are public (non-sensitive)
- ✅ No local file system writes
- ✅ No network calls except to `bopenapi.bgwapi.io`


