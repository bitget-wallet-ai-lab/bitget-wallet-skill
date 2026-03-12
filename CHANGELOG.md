# Changelog

All notable changes to the Bitget Wallet Skill are documented here.

Format: date-based versioning (`YYYY.M.DD`). Each release includes a sequential suffix: `YYYY.M.DD-1`, `YYYY.M.DD-2`, etc. Each entry includes changes, and a security audit summary for transparency.

---

## [2026.3.12-1] - 2026-03-12

### Breaking Changes
- **New API endpoint**: Migrated from `bopenapi.bgwapi.io` (HMAC auth) to `copenapi.bgwapi.io` (token auth, no API key needed)
- **New swap flow**: `quote → confirm → makeOrder → sign+send → getOrderDetails` replaces old `order-quote → order-create → sign → order-submit → order-status`
- **Removed**: `scripts/bitget_api.py` (legacy API client) — replaced by `scripts/bitget_agent_api.py`
- **Removed**: `docs/trading.md` — replaced by `docs/swap.md`

### Added — New Scripts
- `scripts/bitget_agent_api.py` — Unified API client: swap flow + balance + token search + market data (no API key required)

### Added — New API Commands
- `check-swap-token` — Pre-swap token risk check (forbidden-buy detection)
- `get-processed-balance` — On-chain balance query per address/chain/token
- `batch-v2` — Balance + token price in one call (portfolio valuation)
- `search-tokens` — Search tokens by keyword or contract address
- `get-token-list` — Popular tokens per chain
- `confirm` — Second quote with locked market, orderId, and gas estimation

### Added — New Documentation
- `docs/swap.md` — Complete new swap flow with pre-trade checks, multi-market quote display, and confirmation rules
- `COMPATIBILITY.md` — Platform compatibility guide (tested: OpenClaw, Manus, Bolt.new, Devin, Replit Agent)

### Changed — Swap Flow
- Quote now returns **multiple market results** (`data.quoteResults`); agent must display all and recommend the first
- Confirm step locks one market and returns `orderId` + final `quoteResult`
- `recommendFeatures` in confirm response indicates gas payment mode (`user_gas` / `no_gas` for gasless)
- **Balance check required before swap** — `get-processed-balance` must run before quote to prevent misleading `40001` errors

### Changed — Wallet Management
- Mnemonic file-based key management: user provides file path, keys derived in memory
- Mnemonic and private keys never appear in conversation, logs, or output

### Fixed
- Python 3.9 compatibility: added `from __future__ import annotations` for `str | None` type hints

### Audit
- ✅ New API base `copenapi.bgwapi.io` uses token-based auth (no API key/secret needed)
- ✅ Market data endpoints (`/market/v3/*`) work on new API after whitelist
- ✅ `order_sign.py` updated to support new makeOrder `deriveTransaction` format
- ✅ Full swap flow verified: quote → confirm → makeOrder → sign → send → getOrderDetails (BNB USDT→USDC, success)
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


