# Changelog

All notable changes to the Bitget Wallet Skill are documented here.

Format: date-based versioning (`YYYY.M.DD`). Each release includes a sequential suffix: `YYYY.M.DD-1`, `YYYY.M.DD-2`, etc. Each entry includes changes, and a security audit summary for transparency.

---

## [2026.3.5-1] - 2026-03-05

### Added
- **Order Mode API**: 4 new commands for the order-based swap model
  - `order-quote` — get swap price with cross-chain and gasless support
  - `order-create` — create order, receive unsigned tx/signature data
  - `order-submit` — submit signed transactions
  - `order-status` — query order lifecycle status
- **Cross-chain swaps**: swap tokens between different chains in one order (e.g., USDC on Base → USDT on Polygon)
- **Gasless mode (no_gas)**: pay gas with input token, no native token needed (EVM only)
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
