# Transfer (Token Transfer) Domain Knowledge

This document describes the **Transfer flow** for on-chain token transfers via the toc_agent gateway
(`getTransferDataV4` + `send`). The server handles transaction construction, broadcasting, and
on-chain status tracking. The client (B-side) only manages private keys and signing.

**MUST read this file before calling any transfer API** (`transfer_make_sign_send.py` or
`social_transfer_make_sign_send.py`).

## Flow Overview

| Step | Interface / Script | Description |
|------|--------------------|-------------|
| 0 | `batch-v2` | **Pre-check**: verify sender has enough token balance and (if not gasless) enough native gas |
| 1+2+3 | **`transfer_make_sign_send.py`** | One-shot (mnemonic/private-key): `getTransferDataV4` + sign + `send` in one run |
| 1+2+3 | **`social_transfer_make_sign_send.py`** | One-shot (Social Login Wallet): `getTransferDataV4` + sign (TEE) + `send` in one run. No local private key needed. |

`send` broadcasts and returns the final result synchronously (`txid`, `txConfirmTimeTxt`) — there is
no separate order-status polling endpoint.

### One-Shot Script (Recommended)

Use `transfer_make_sign_send.py` to avoid signature expiry issues. It creates the transfer data,
signs locally, and submits immediately.

```bash
# EVM token transfer (server picks gasless vs. standard automatically based on native balance)
python3 scripts/transfer_make_sign_send.py \
  --private-key-file /tmp/.pk_evm \
  --chain eth \
  --contract 0xdAC17F958D2ee523a2206206994597C13D831ec7 \
  --from-address 0xAbC... --to-address 0xDeF... \
  --amount 100

# EVM token transfer on a chain where the sender has no native gas — same command,
# the response will come back with gasAccount.selected=true and the script signs accordingly
python3 scripts/transfer_make_sign_send.py \
  --private-key-file /tmp/.pk_evm \
  --chain base \
  --contract 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --from-address 0xAbC... --to-address 0xDeF... \
  --amount 50

# Solana token transfer
python3 scripts/transfer_make_sign_send.py \
  --private-key-file-sol /tmp/.pk_sol \
  --chain sol \
  --contract Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB \
  --from-address ApPjj... --to-address 7xKXt... \
  --amount 10
```

### One-Shot Script — Social Login Wallet

Use `social_transfer_make_sign_send.py` when the user has a Social Login Wallet. No local private key
needed — signing happens via Bitget Wallet TEE.

```bash
# Social Login Wallet: token transfer
python3 scripts/social_transfer_make_sign_send.py \
  --wallet-id <walletId> \
  --chain bnb --contract 0x55d398326f99059fF775485246999027B3197955 \
  --from-address 0xAbC... --to-address 0xDeF... \
  --amount 1

# Social Login Wallet: Solana transfer
python3 scripts/social_transfer_make_sign_send.py \
  --wallet-id <walletId> \
  --chain sol --contract Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB \
  --from-address ApPjj... --to-address 7xKXt... \
  --amount 10
```

## Pre-Transfer Checks

Before any transfer, the agent **must**:

1. **Balance check**: Run `batch-v2` to verify sender has enough token balance for the transfer amount.
2. **Gas check** (if not gasless): Verify native token balance is sufficient for gas fees.
3. **Status guard**: The one-shot scripts check the `getTransferDataV4` response `status` / error code
   and abort on any non-zero status (e.g. insufficient balance, invalid address — see Error Codes below).
4. **Revert guard**: `estimateRevert` is nested under `data.fee.estimateRevert` (not top-level, unlike
   the old `makeTransferOrder` response). The one-shot scripts check `data.fee.estimateRevert` and abort
   with `data.fee.estimateRevertReason` before signing if it's `true`.
5. **Pending-nonce warning**: if `data.hasPendingTransactionAndOverwriteNonce` is `true`, the server is
   reusing a nonce from a still-pending transaction on this address — the scripts print a warning but
   still proceed, since the server (not the client) owns nonce assignment.

```bash
python3 scripts/bitget-wallet-agent-api.py batch-v2 \
  --chain <chain> --address <sender> --contract "" --contract <tokenContract>
```

## Gasless Transfer

Gasless mode allows token transfers without holding native gas tokens (ETH, SOL, BNB, etc.). Gas fees
are paid from the user's stablecoin balance (USDT/USDC), via one of three server-side payment plans
(`sid`): `transfer_no_gas` (EVM 7702 paymaster / SOL), `transfer_3009_no_gas` (EIP-3009 tokens like
USDC), `transfer_no_gas_trx` (TRX — **not yet supported by this skill's scripts**, see Signing Modes).

### How to Enable

There is no CLI flag — the scripts never send `gasAccountSelected` at all, so the server picks
automatically per its own documented default (§3.3 of the interface spec): if the sender's native-coin
balance is sufficient to cover gas, it builds a standard self-pay transfer; if not, it matches a
gasless plan automatically (`skipWhenUserNativeEnough`). The scripts just sign whatever comes back —
check `data.gasAccount.selected` to see which path was taken (both scripts print it).

This is a deliberate behavior change from the old `makeTransferOrder` API (which required an explicit
`noGas=true` to ever use gasless) — see `CHANGELOG.md` for the migration note.

### Supported Chains and Pay Tokens

Which chains/tokens are eligible for gasless is controlled server-side by Apollo config (`gasAccount`),
shared with the App. The server automatically picks the pay token from the eligible whitelist — there
is **no way to manually specify a pay token** with this API (the old `--gasless-pay-token` flag has
been removed; it has no equivalent in the new interface).

| Chain | USDT | USDC |
|-------|------|------|
| eth | `0xdAC17F958D2ee523a2206206994597C13D831ec7` | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` |
| bnb | `0x55d398326f99059fF775485246999027B3197955` | `0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d` |
| base | `0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2` | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| arbitrum | `0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9` | `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` |
| matic | `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` |
| morph | `0xe7cd86e13AC4309349F30B3435a9d337750fC82D` | `0xCfb1186F4e93D60E60a8bDd997427D1F33bc372B` |
| sol | `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB` | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |

### Gasless Response Fields

When `getTransferDataV4` matches a gasless plan, `data.gasAccount` is present:

| Field | Description |
|-------|-------------|
| `gasAccount.selected` | `true` only if gasless will actually be used for this transfer — only then does the response carry gasless signing data (`signData`/`signDataV2`) |
| `gasAccount.sid` / `gasAccount.pay.sid` | The matched plan: `transfer_no_gas` / `transfer_3009_no_gas` / `transfer_no_gas_trx` |
| `gasAccount.pay.payToken.{contract,symbol,amount}` | The token/amount the user pays gas with |
| `gasAccount.payTotal` / `gasAccount.payAmount` | Gas fee in USD / in on-chain pay-token units |

If `gasAccount` is absent, no gasless plan matched this chain/token — the scripts proceed with a
standard transfer, which will fail on broadcast if the sender also has no native gas.

**Observed in live testing (2026-10-29)**: BSC USDT (`0x55d398326f99059fF775485246999027B3197955`),
sender with 0 BNB — a 1 USDT transfer matched gasless (`gasAccount.selected=true`, actual fee charged
≈0.016 USDT, noticeably higher than the fee preview shown before signing); several earlier attempts at
0.1/1/5/11 USDT (back when the scripts still sent an explicit `gasAccountSelected`) returned no
`gasAccount` at all. Gasless availability for a given chain/token/amount appears to vary and should not
be assumed reliable — the agent should always check `data.gasAccount` on each call rather than assuming
a prior result still holds, and warn the user that the actual fee can exceed the preview.

**Agent rule:** If `gasAccount` is absent and the sender's native-gas balance is also insufficient,
inform the user before letting the standard-transfer signing/broadcast fail — suggest topping up native
gas or retrying with a different amount. Do NOT silently retry with different parameters.


> **Removed capability**: the old EIP-7702 third-party-binding override (`--override-7702`, error code
> `30108`) has no equivalent in the new interface and has been removed. If a sender address already has
> a third-party EIP-7702 binding, gasless transfers on that address may simply fail — there is currently
> no agent-side override path; this needs backend confirmation if it blocks real users.

## Signing Modes

`getTransferDataV4` no longer returns a `source.type` discriminator. The signing path is determined by
whether `data.gasAccount.selected` is `true`, and which of `signData` / `signDataV2` is present:

| Condition | Signing Method | Applicable |
|-----------|----------------|-----------|
| No `gasAccount`, or `gasAccount.selected != true` | Build and sign a standard raw tx from the flat top-level fields (`to`/`data`/`nonce`/`gasLimit`/`chainId`/`value` + `gasPrice` or `maxFeePerGas`/`maxPriorityFeePerGas`) | EVM standard self-pay |
| Same as above | Full Ed25519 sign of the Solana transaction | sol standard self-pay |
| `gasAccount.selected == true` and `data.signData.sign_type == "sign_7702_msgs"` | Sign each `signData.data[i].hash` via `unsafe_sign_hash`, write back `sig`, `JSON.stringify(signData.data)` | EVM gasless (legacy `signData` format) |
| `gasAccount.selected == true` and `data.signDataV2` present | Sign each `signDataV2[i].data` as EIP-712 typed data, collect `[{domain, message, signature}, ...]`, `JSON.stringify(...)` | EVM gasless (EIP-712, incl. EIP-3009 tokens) |
| `gasAccount.selected == true` and `gasAccount.sid/pay.sid == "transfer_no_gas_trx"` | **Not implemented** — the scripts abort with an error | TRX gasless (out of scope for this round) |

✅ **Live-confirmed** (2026-10-29, BSC USDT standard transfer): the flattened field layout is correct
— `to`/`data`/`nonce`/`gasLimit`/`chainId`/`gasPrice`/`value` all appear at the top level of `data` as
assumed. Two things differ from the old API and from a naive hex-wei assumption, now handled correctly
by the scripts:

- **`gasPrice` / `maxFeePerGas` / `maxPriorityFeePerGas` are plain decimal strings in native-coin units**
  (e.g. `"0.0000000001"` BNB), not `0x`-prefixed wei hex like `nonce`/`gasLimit`/`chainId`. This is the
  same quirk `order_sign.py` already works around for the swap flow. `nonce`/`gasLimit`/`chainId`/`value`
  came back as plain ints in the observed response, not hex strings either — but the scripts still
  accept `0x`-hex for all of these for forward compatibility.
- **The top-level `to` field is the on-chain tx target, not the recipient.** For a token transfer this
  is the token contract address (matching `contract`); the human-entered recipient comes back separately
  as `receiver`. The scripts always use the original `--to-address` CLI argument when calling `send`,
  never `data.get("to")`, to avoid sending the wrong recipient.

### EVM Gasless Legacy (`signData`) Signing Detail

`data.signData.data` contains 1-2 items (same msg shape as before):

1. **`msgType=auth`** (first-time only): Authorization to bind the 7702 contract. Sign `hash` with ECDSA secp256k1 (`unsafe_sign_hash`).
2. **`msgType=call`**: Transfer execution call. Sign `hash` with eth_sign (`unsafe_sign_hash`).

Fill each item's `sig` field, then `JSON.stringify(signData.data)` is submitted as the `sig` parameter.
Both auth + call signing and the transfer itself are bundled into **one on-chain transaction**
(EIP-7702 Type-4 tx) by the server.

### Solana Signing Detail

`getTransferDataV4` does not give an explicit field name for the Solana pending transaction in its
documented response fields — the scripts probe `data.rawTx`, then `data.serializedTx`, then
`data.serializedTransaction`, in that order, and raise a clear error if none is present.
⚠️ **Pending live confirmation** — this field name has not been verified against a real API response.

For gasless Solana transfers specifically: the server pre-signs the feePayer slot, the client signs
its own slot (Ed25519 partial-sign, same `sign_solana_tx` helper handles both full-sign and
partial-sign automatically by locating the signer's own slot).

**blockhash expiry**: Solana `recentBlockhash` expires after ~60 seconds (~150 slots). Sign and submit
promptly — use `transfer_make_sign_send.py` to avoid expiry.

⚠️ **Pending live confirmation**: the EIP-712 signing output format for non-EIP-3009 EVM gasless
(`signDataV2` without a 3009 token) is documented by the upstream interface spec itself as "matches the
App (core-js), to be confirmed via joint debugging." This implementation uses the same
`[{domain, message, signature}, ...]` output shape as the confirmed EIP-3009 case; verify against a
real joint-debug session before relying on it in production. Both scripts fail closed rather than
guess on ambiguity: `social_transfer_make_sign_send.py` prints an explicit unverified-path warning
before attempting the TEE's non-dedicated `signTypeData` call, and `transfer_make_sign_send.py`'s
`_infer_primary_type` raises instead of falling back to an arbitrary candidate when the EIP-712
`primaryType` can't be unambiguously inferred from `types`.

## Chain-Specific Notes

### EVM (eth/bnb/base/arbitrum/matic/morph)
- **Native token transfer**: `contract=""`, top-level `to` = receiver, `data="0x"`
- **Token transfer**: `contract` = ERC-20 address, top-level `to` = contract, `data` = `transfer(address,uint256)` calldata
- **EIP-1559** (eth/base/arbitrum/matic/morph): response carries `maxFeePerGas`/`maxPriorityFeePerGas`
- **Gasless**: Only for token transfers (`contract` must be non-empty; native token gasless is not supported)

### Solana (sol)
- **Native SOL transfer**: `contract=""`
- **SPL Token transfer**: `contract` = SPL Token Mint address
- **blockhash expiry**: ~60 seconds. Use `transfer_make_sign_send.py` to avoid expiry.

## Order Status

`send` broadcasts and returns the final result **synchronously** — `data.txid` is the on-chain
transaction hash and `data.txConfirmTimeTxt` is an estimated confirmation-time message. There is no
async order record and no separate status-polling endpoint to call after `send` succeeds.

## Error Codes

| Scenario | status | data |
|----------|--------|------|
| Request carries `source` (DApp transaction) | `1` | `toc_agent does not support dapp transactions` |
| `send`'s `gasAccount` is not an enabled gasless plan | `1` | `toc_agent only supports no-gas payment or native coin payment` |
| Receiver address is transfer-restricted | `1` | `当前地址不支持转账` (localized) |
| Transaction construction failed (insufficient balance, invalid address, etc.) | `27xxx` | Localized error text |
| Token is in a split/merge blackout window | `26060` | Localized error text (includes recovery time) |
| Token info lookup failed (`send` step, fail-close) | `26061` | Localized error text |
| Invalid EIP-3009 signature format, token doesn't support EIP-3009, or TRX gasless has fewer than 2 signed txs | `1` | `System error please wait` |

## Timing Constraints

- **EVM**: no hard expiry documented for the constructed data, but nonce may be consumed by other
  activity — submit promptly.
- **Solana blockhash**: Expires in ~**60 seconds**. Must sign and submit promptly (use
  `transfer_make_sign_send.py`).
- `amount` sent to `send` must match the value returned by `getTransferDataV4` exactly (it may be
  server-adjusted for full-balance transfers or EIP-3009 tokens).
