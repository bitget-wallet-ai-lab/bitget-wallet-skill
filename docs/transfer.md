# Transfer (Token Transfer) Domain Knowledge

This document describes the **Transfer flow** for on-chain token transfers via the ToB Transfer API (`ms-user-go`). The server handles transaction construction, broadcasting, and on-chain status tracking. The client (B-side) only manages private keys and signing.

**MUST read this file before calling any transfer API** (`make-transfer-order`, `submit-transfer-order`, `get-transfer-order`, or `transfer_make_sign_send.py`).

## Flow Overview

| Step | Interface / Script | Description |
|------|--------------------|-------------|
| 0 | `batch-v2` | **Pre-check**: verify sender has enough token balance and (if not gasless) enough native gas |
| 1 | `make-transfer-order` | Create transfer order; returns unsigned source data + fee info + orderId |
| 2 | Local signing | Sign the source data using the appropriate method (see Signing Modes) |
| 3 | `submit-transfer-order` | Submit signed tx; server broadcasts to chain |
| 4 | `get-transfer-order` | Poll order status until SUCCESS or FAILED |
| 1+2+3 | **`transfer_make_sign_send.py`** | One-shot: make + sign + submit in one run (recommended) |

### One-Shot Script (Recommended)

Use `transfer_make_sign_send.py` to avoid signature expiry issues. It creates the order, signs locally, and submits immediately.

```bash
# EVM token transfer (standard)
python3 scripts/transfer_make_sign_send.py \
  --private-key-file /tmp/.pk_evm \
  --chain eth \
  --contract 0xdAC17F958D2ee523a2206206994597C13D831ec7 \
  --from-address 0xAbC... --to-address 0xDeF... \
  --amount 100

# EVM gasless transfer
python3 scripts/transfer_make_sign_send.py \
  --private-key-file /tmp/.pk_evm \
  --chain base \
  --contract 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --from-address 0xAbC... --to-address 0xDeF... \
  --amount 50 --gasless

# Solana gasless transfer
python3 scripts/transfer_make_sign_send.py \
  --private-key-file-sol /tmp/.pk_sol \
  --chain sol \
  --contract Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB \
  --from-address ApPjj... --to-address 7xKXt... \
  --amount 10 --gasless
```

### Step-by-Step (Diagnostic)

```bash
# Step 1: Create order
python3 scripts/bitget-wallet-agent-api.py make-transfer-order \
  --chain eth --contract 0xdAC17F958D2ee523a2206206994597C13D831ec7 \
  --from-address 0xAbC... --to-address 0xDeF... --amount 100

# Step 2: Sign externally (using source data from step 1)

# Step 3: Submit signed tx
python3 scripts/bitget-wallet-agent-api.py submit-transfer-order \
  --order-id <orderId> --sig <signed_hex>

# Step 4: Poll status
python3 scripts/bitget-wallet-agent-api.py get-transfer-order --order-id <orderId>
```

## Pre-Transfer Checks

Before any transfer, the agent **must**:

1. **Balance check**: Run `batch-v2` to verify sender has enough token balance for the transfer amount.
2. **Gas check** (if not gasless): Verify native token balance is sufficient for gas fees.
3. **estimateRevert guard**: After `make-transfer-order`, check `data.estimateRevert`. If `true`, **abort** — the transaction is predicted to fail (insufficient balance, contract revert, etc.).

```bash
python3 scripts/bitget-wallet-agent-api.py batch-v2 \
  --chain <chain> --address <sender> --contract "" --contract <tokenContract>
```

## Gasless Transfer

Gasless mode allows token transfers without holding native gas tokens (ETH, SOL, BNB, etc.). Gas fees are paid from the user's stablecoin balance (USDT/USDC).

### How to Enable

Pass `--gasless` to `transfer_make_sign_send.py` or `make-transfer-order`. The API parameter `noGas=true` is sent automatically.

### Supported Chains and Pay Tokens

| Chain | USDT | USDC |
|-------|------|------|
| eth | `0xdAC17F958D2ee523a2206206994597C13D831ec7` | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` |
| bnb | `0x55d398326f99059fF775485246999027B3197955` | `0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d` |
| base | — | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| arbitrum | `0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9` | `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` |
| matic | `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` |
| morph | `0xc7D67A9CBB121B3B0b9c053Dd9F469523243379A` | `0xE34C91815d7FC18A9E2148bcD4241D0a5848b693` |
| sol | `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB` | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |

### Token Selection

- **Automatic** (default): Server selects the best pay token from the whitelist (sufficient balance + stable price).
- **Manual**: Pass `--gasless-pay-token <contract>` to specify a particular token.

### Gasless Response Fields

When gasless is available, `data.noGas` contains:

| Field | Description |
|-------|-------------|
| `available` | `true` if gasless is active |
| `payToken` | Contract address of the selected pay token |
| `payTokenSymbol` | Symbol (e.g. "USDC") |
| `payAmount` | Gas fee amount deducted from token balance |
| `payTokenPriceUsd` | Current USD price of pay token |
| `need7702Auth` | EVM only: `true` if first-time 7702 binding needed |
| `acceptableTokens` | Full whitelist of eligible pay tokens |

### Silent Degradation

Gasless silently degrades to standard transfer (no error) when:
- The chain is not in the gasless whitelist
- Transfer amount (USD value) is below the threshold
- No pay token has sufficient balance or queryable price
- `noGas` was not requested

The script detects this (no `noGas` field in response) and warns the user.

### EIP-7702 Override

If the sender address is already bound to a third-party EIP-7702 contract, gasless will fail by default. Pass `--override-7702` to allow overwriting the existing binding. The response `noGas.warn` will contain a warning message to display to the user.

## Signing Modes

The `source.type` field determines which signing logic to use:

| source.type | Signing Method | Applicable Chains |
|-------------|---------------|-------------------|
| `evm_legacy` | Build and sign Legacy (type 0) raw tx | bnb |
| `evm_1559` | Build and sign EIP-1559 (type 2) raw tx | eth, base, arbitrum, matic, morph |
| `evm_7702` | Sign `msgToSign[].hash` via `unsafe_sign_hash`, return `JSON.stringify(msgs)` | EVM gasless |
| `evm_morph_altfee` | Morph type-0x7f custom serialization (requires viem + Morph serializer) | morph AltFee |
| `sol_raw` | Full Ed25519 sign of Solana transaction | sol (standard) |
| `sol_partial` | Partial-sign (feePayer already signed slot 0, user signs slot 1) | sol gasless |

### EVM 7702 Signing Detail

The `source.evm7702.msgToSign` array contains 1-2 items:

1. **`msgType=auth`** (first-time only): Authorization to bind 7702 contract. Sign `hash` with ECDSA secp256k1 (`unsafe_sign_hash`).
2. **`msgType=call`**: Transfer execution call. Sign `hash` with eth_sign (`unsafe_sign_hash`).

Fill each item's `sig` field, then `JSON.stringify(msgToSign)` is submitted as the `sig` parameter.

Both auth + call signing and the transfer itself are bundled into **one on-chain transaction** (EIP-7702 Type-4 tx) by the server.

### Solana Partial Signing

For gasless Solana transfers:
1. Server constructs the transaction with a feePayer (gas account) and pre-signs slot 0
2. `source.sol.rawTx` contains the base58 partial-signed transaction
3. Client adds user signature to slot 1 (Ed25519 partial-sign)
4. The fully-signed transaction is submitted

**blockhash expiry**: Solana `recentBlockhash` expires after ~60 seconds (~150 slots). Sign and submit promptly.

## Morph AltFee

When `chain=morph` and the response contains both `source` (evm_1559) and `altFeeSource` (evm_morph_altfee), two gas payment options exist:

| Option | Source Field | Gas Payment |
|--------|-------------|-------------|
| Standard | `source` (evm_1559) | ETH |
| AltFee | `altFeeSource` (evm_morph_altfee) | USDT/USDC/BGB |

**AltFee token contracts (Morph mainnet, chainId=2818):**

| feeTokenID | Symbol | Contract |
|-----------|--------|----------|
| 1 | USDT | `0xc7D67A9CBB121B3B0b9c053Dd9F469523243379A` |
| 2 | USDC | `0xE34C91815d7FC18A9E2148bcD4241D0a5848b693` |
| 3 | BGB | `0x55d1F1879969bDbb9960d269974564C58dbc3238` |

The response `altFee.feeTokenID` indicates which token was selected by the server. The `altFee` object also includes `feeTokenContract`, `feeTokenSymbol`, `feeTokenDecimal`, and `feeTokenPrice`.

**Signing (type-0x7f):** Uses viem + Morph custom serializer (`serializeAltFeeTransaction`, `ALT_FEE_TX_TYPE = "0x7f"`). RLP structure: `[chainId, nonce, maxPriorityFeePerGas, maxFeePerGas, gas, to, value, data, accessList(empty), feeTokenID, feeLimit, yParity, r, s]`. Sign hash: `keccak256(0x7f || rlp(unsigned_fields))`.

`transfer_make_sign_send.py` signs the standard `source` (evm_1559). For AltFee signing, use external tooling (viem + Morph custom serializer).

## Chain-Specific Notes

### EVM (eth/bnb/base/arbitrum/matic/morph)
- **Native token transfer**: `contract=""`, `source.evm.to` = receiver, `source.evm.data="0x"`
- **Token transfer**: `contract` = ERC-20 address, `source.evm.to` = contract, `data` = `transfer(address,uint256)` calldata
- **EIP-1559** (eth/base/arbitrum/matic/morph): `fee.eip1559` is non-null
- **L2 chains** (base/arbitrum/morph): `fee.l1FeeMax` is non-empty (L1 calldata fee)
- **Gasless**: Only for token transfers (`contract` must be non-empty; native token gasless is not supported)

### Solana (sol)
- **Native SOL transfer**: `contract=""`
- **SPL Token transfer**: `contract` = SPL Token Mint address
- **Fee units**: `fee.stdPriPrice` (lamports/CU), `fee.stdPriLimit` (compute unit limit)
- **blockhash expiry**: ~60 seconds. Use `transfer_make_sign_send.py` to avoid expiry.

### Memo Field
The `--memo` parameter is passed through to `ms_chain` for on-chain inclusion. Chain support varies — not all chains support memo. Pass `""` or omit for no memo.

## Order Status

| Status | Description | txid |
|--------|-------------|------|
| `PENDING` | Order created, not yet broadcast | — |
| `PROCESSING` | Transaction broadcast, awaiting chain confirmation | present |
| `SUCCESS` | Transaction confirmed on-chain | present |
| `FAILED` | Transaction failed (broadcast failure, chain revert, etc.) | may be present |

- Status comes from real-time chain query, not database cache
- Gasless orders may have `txid` in format `getgas_task_xxx` (gas-account task ID, not final chain hash)
- When `orderStatus=FAILED`, the `failReason` field contains the failure description
- `gasAccountData` in the make-transfer-order response is for server internal use; clients should ignore it
- Poll `get-transfer-order` until terminal status (SUCCESS/FAILED)

## Error Codes

| Code | Description | Action |
|------|-------------|--------|
| 0 | Success | — |
| 30101 | Missing or invalid parameters | Check request params; `msg` contains the missing field |
| 30102 | Unsupported chain | Verify chain code |
| 30103 | Insufficient balance | Top up or enable gasless |
| 30104 | estimateRevert (predicted failure) | Do not proceed; investigate root cause |
| 30105 | orderId not found | Check orderId or re-create order |
| 30106 | Order already submitted | Do not resubmit; orderId is single-use |
| 30107 | Invalid gasless signature (7702 auth failed) | Check signing logic for auth message |
| 30108 | Third-party 7702 binding exists, override7702=false | Prompt user, re-request with `--override-7702` |
| 30201 | ms_chain service error | Retry; `msg` has details |
| 30202 | gas-account service unavailable | Fall back to standard transfer |
| 30500 | Internal error | Contact backend; `msg` has details |

## Timing Constraints

- **EVM orderId**: No hard expiry, but nonce may be consumed. Recommend submit within **10 minutes**.
- **Solana blockhash**: Expires in ~**60 seconds**. Must sign and submit promptly (use `transfer_make_sign_send.py`).
- **orderId is single-use**: Once submitted successfully, the same orderId cannot be resubmitted.
