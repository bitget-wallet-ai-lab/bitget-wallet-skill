# Social Login Wallet Reference

All operations use `social-wallet.py core <operation> '<params_json>'`.

`<params_json>` is a JSON object. The `chain` field is always required. For custom EVM chains (`evm_custom#`), `chainId` is also required (e.g. `"chainId": 56` for BNB, `"chainId": 8453` for Base). Native chains like `eth` default to their standard chainId.

## profile — Get Wallet Identity

Retrieve the `walletId` for the current Social Login Wallet. This ID must be passed as `--wallet-id` to all `bitget-wallet-agent-api.py` calls when using a Social Login Wallet.

**Endpoint:** `POST /social-wallet/agent/profile`

**Usage:**
```bash
python3 scripts/social-wallet.py profile
```

**Request:** Encrypted empty `{}` payload (same auth flow as other endpoints — AES-GCM encryption + HMAC-SHA384 signature). No business parameters needed.

**Response:**
```json
{
  "walletId": "58680ea41d9e987cddc641ff8b058c55"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `walletId` | string | Unique wallet identifier. Pass to `--wallet-id` in all `bitget-wallet-agent-api.py` calls. |

**When to call:**
- Once per session, before any API calls that need wallet identity.
- The `walletId` does not expire within a session, but changes if the user re-binds with a different appid/appsecret.

**Flow:**
1. Call `social-wallet.py profile` → get `walletId`
2. Pass `--wallet-id <walletId>` to all subsequent `bitget-wallet-agent-api.py` commands (balance, quote, confirm, make-order, send, etc.)
3. Without `--wallet-id`, the API defaults to `toc_agent` token (for mnemonic/private-key wallets)

## User Confirmation Rule

**Every signing operation (`sign_transaction`, `sign_message`) requires explicit user confirmation before execution.** The agent must:

1. Show the user what will be signed: chain, recipient address, amount, token, calldata summary
2. Wait for the user to explicitly confirm ("confirm", "yes", "execute")
3. Only then call the signing script

Read-only operations (`get_address`, `get_public_key`, `validate_address`, `batchGetAddressAndPubkey`) do not require confirmation.

## Fund Limit & Wallet Isolation

**Social Login Wallets are for small, routine on-chain operations — NOT primary asset storage.**

- **Before the first transaction**, remind the user to confirm how much they are comfortable keeping in this wallet. Suggested range: small test amounts or daily-use funds only.
- **Keep isolated from main wallet.** The Social Login Wallet should not hold the user's primary assets. If the user attempts a high-value transaction (e.g. > $100 or a significant portion of their holdings), warn them and suggest using their main wallet (mnemonic/hardware) instead.
- **Never bulk-transfer assets** from a main wallet into a Social Login Wallet. The Social Login Wallet's security model (TEE-hosted keys, API-based signing) is different from self-custody — users should understand the tradeoff.
- **Periodically remind users** to move excess funds back to their main wallet if the Social Login Wallet balance grows beyond their intended limit.

## Integration with Swap Flow

**⚠️ `order_make_sign_send.py` is NOT compatible with Social Login Wallets.** That script requires a local private key file, but Social Login Wallets sign via TEE API — no local private key exists. For Social Login Wallet swaps, you **must** use the 3-step manual flow:

1. **makeOrder** → `bitget-wallet-agent-api.py make-order ...`
2. **Sign** → `social-wallet.py core sign_message/sign_transaction` (per tx, based on mode detection)
3. **Send** → `bitget-wallet-agent-api.py send --json-file ...`

All three steps must complete within ~60 seconds (makeOrder data expiry).

### gasPayMaster / gasless

When using the Social Login Wallet for gasless swaps (no_gas mode), the makeOrder response returns `txFunction: "swap_instant_gas_paymaster"` with `deriveTransaction.msgs[]`. Each msg has `signType: "eth_sign"` and a `hash` to sign.

**Signing flow — detect mode first:**

For each tx in makeOrder response, check which signing mode to use:

```python
derive = tx.get("deriveTransaction", {})
msgs = derive.get("msgs", [])

if msgs and any(m.get("signType") == "eth_sign" for m in msgs):
    # gasPayMaster mode — sign msg hashes
    ...
else:
    # regular tx mode — sign_transaction
    ...
```

**⚠️ CRITICAL: Always check `deriveTransaction.msgs` first.** Even for cross-chain swaps, the tx may have `txFunction: "swap_instant_gas_paymaster"` with msgs. Do NOT fall through to regular tx signing based on the absence of top-level msgs — check `deriveTransaction.msgs`.

### Mode 1: gasPayMaster (msgs with eth_sign)

Used for gasless same-chain and cross-chain swaps. The tx contains `deriveTransaction.msgs[]` with `signType: "eth_sign"`.

1. For each msg in `deriveTransaction.msgs[]`:
   - Call `social-wallet.py core sign_message '{"chain":"evm_custom#bnb","message":"EthSign:<hash>"}'`
   - The `EthSign:` prefix tells the social wallet to sign the raw hash (no EIP-191 prefix), equivalent to `unsafe_sign_hash`
2. Put the signature in the msg's **`sig`** field (**not** `signature` — backend rejects `signature`)
3. Set `tx.sig = json.dumps(msgs)` (JSON string of the msgs array with `sig` fields)

```python
for m in msgs:
    sign_params = {"chain": "evm_custom#bnb", "message": f"EthSign:{m['hash']}"}
    result = social_wallet_sign_message(sign_params)
    m["sig"] = result["result"]  # NOT "signature"!

tx["sig"] = json.dumps(msgs)
```

### Mode 2: Regular transaction signing

Used for user_gas mode (non-gasless). The tx has no msgs, just standard tx fields.

1. Build sign_transaction params from `deriveTransaction` (to, value, data, nonce, gasLimit, gasPrice, chainId)
2. Call `social-wallet.py core sign_transaction '<params>'`
3. Set `tx.sig = result["result"]` (the signed RLP tx hex)

```python
sign_params = {
    "chain": f"evm_custom#bnb",
    "chainId": derive.get("chainId", 56),
    "to": derive["to"],
    "value": derive.get("value", 0),
    "data": derive.get("data", "0x"),
    "nonce": derive["nonce"],
    "gasLimit": str(derive["gasLimit"]),
    "gasPrice": str(derive.get("gasPrice", "0.000000001")),
}
result = social_wallet_sign_transaction(sign_params)
tx["sig"] = result["result"]
```

### Mode 3: Tron transaction signing

Tron txs have a `transaction` object with `raw_data_hex`, `raw_data`, `txID`. Social wallet returns a raw signature hex (65 bytes / 130 chars). Must be wrapped in the format expected by send API.

1. Get `transaction` from `deriveTransaction.transaction` or `tx.transaction`
2. Call `social-wallet.py core sign_transaction '{"chain":"tron","transaction":{...}}'`
3. Wrap the returned sig hex: `{"signature": [sig_hex], "txID": txID, "raw_data": raw_data}`
4. Set `tx.sig = json.dumps(wrapped)`

```python
transaction = derive.get("transaction") or tx.get("transaction")
sign_params = {"chain": "tron", "transaction": transaction}
result = social_wallet_sign_transaction(sign_params)
sig_hex = result["result"]  # raw 65-byte hex

# Wrap in expected format
sig_obj = {
    "signature": [sig_hex],
    "txID": transaction["txID"],
    "raw_data": transaction["raw_data"],
}
tx["sig"] = json.dumps(sig_obj)
```

### Common mistakes

| Mistake | Error | Fix |
|---------|-------|-----|
| Using `"signature"` instead of `"sig"` in msgs | error_code 40009 | Use `m["sig"]` |
| Using sign_transaction for gasPayMaster tx | Signature verification failed | Check `deriveTransaction.msgs` first, use sign_message with EthSign |
| Missing `EthSign:` prefix for raw hash | Wrong signature (personal_sign adds prefix) | Always use `EthSign:{hash}` |
| Tron: passing raw sig hex as tx.sig | On-chain tx failed | Wrap in `{"signature":[hex],"txID":...,"raw_data":...}` |
| Using wrong market/protocol in confirm | error_code 30000 | Use exact values from quote response |

---

## Supported Chains

| Chain | `chain` value | Type |
|-------|--------------|------|
| Bitcoin | `btc` | Native |
| Ethereum | `eth` | Native |
| BNB Smart Chain | `evm_custom#bnb` | EVM |
| Base | `evm_custom#base` | EVM |
| Polygon | `matic` | EVM |
| Arbitrum | `evm_custom#arb` | EVM |
| Optimism | `evm_custom#op` | EVM |
| Klaytn | `evm_custom#klay` | EVM |
| Morph | `evm_custom#morph` | EVM |
| Solana | `sol` | Native |
| TRON | `tron` | Native |

For custom EVM chains, use `evm_custom#<name>` and provide `chainId`.

---

## Operations

### sign_transaction

Sign a raw transaction. Params vary by chain.

#### ETH / EVM

```bash
# Legacy transaction
python social-wallet.py core sign_transaction '{
  "chain": "eth",
  "to": "0xBfEfaAd8F4F77E3781caAfA88dBCc62A4F836148",
  "value": 0.1,
  "nonce": 0,
  "gasLimit": 21000,
  "gasPrice": 0.0000001,
  "data": "0x"
}'

# EIP-1559 token transfer
python social-wallet.py core sign_transaction '{
  "chain": "eth",
  "coin": "USDT",
  "contract": "0xdac17f958d2ee523a2206206994597c13d831ec7",
  "from": "0x4dEC25BDb5BBd6F9943Df53b8FE04793365f25e5",
  "to": "0xdac17f958d2ee523a2206206994597c13d831ec7",
  "value": 0,
  "data": "0xa9059cbb000000000000000000000000...",
  "nonce": 3,
  "gasLimit": "76822",
  "gasPrice": "0.000000000385",
  "chainId": 1,
  "maxPriorityFeePerGas": 10000000.0,
  "maxFeePerGas": 421871350.0
}'

# Custom EVM chain (Morph)
python social-wallet.py core sign_transaction '{
  "chain": "evm_custom#morph",
  "chainId": 2818,
  "coin": "BGB",
  "contract": "0x389c08bc23a7317000a1fd76c7c5b0cb0b4640b5",
  "from": "0x61324f49e824C80771bca96aF396c971B8ab4aF9",
  "to": "0x389c08bc23a7317000a1fd76c7c5b0cb0b4640b5",
  "value": 0,
  "data": "0xa9059cbb...",
  "nonce": 0,
  "gasLimit": "115470",
  "gasPrice": "0.000000000001"
}'
```

**ETH/EVM fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| chain | string | Yes | `eth`, `matic`, `evm_custom#bnb`, etc. |
| to | string | Yes | Recipient / contract address |
| value | number | Yes | Amount in native token units |
| nonce | int | Yes | Transaction nonce |
| gasLimit | string/int | Yes | Gas limit |
| gasPrice | string/float | Yes | Gas price in ETH units |
| data | string | No | Calldata hex (default `"0x"`) |
| chainId | int | No | Required for custom EVM chains |
| coin | string | No | Token symbol (e.g. `"USDT"`) |
| contract | string | No | Token contract address |
| from | string | No | Sender address |
| maxPriorityFeePerGas | float | No | EIP-1559 priority fee (Wei) |
| maxFeePerGas | float | No | EIP-1559 max fee (Wei) |
| type | int | No | 0=Legacy, 2=EIP-1559, 4=EIP-7702 |
| eip7702CallStruct | object | No | EIP-7702 auth + calls |
| typeInt | int | No | Klaytn tx type (e.g. 9) |

#### BTC

```bash
# Standard UTXO transaction (Taproot)
python social-wallet.py core sign_transaction '{
  "chain": "btc",
  "path": "m/86'\''0'\''0'\''0/0",
  "from": "bc1psv5h0ja94klp7yak2p73v8r3rdxckckdkvp4ezl9ufev67lt2xpqv5naue",
  "to": "bc1pker8csvuu7w9qqd2mv7yr8u0wad8qr9dz86j5m8q7tdf3eed7euqvgjsn2",
  "value": 0.00004,
  "fee": "0.00001",
  "utxos": [
    {
      "address": "bc1psv5h0ja94klp7yak2p73v8r3rdxckckdkvp4ezl9ufev67lt2xpqv5naue",
      "txid": "fb5cc16402b72a4bd50fb67034b6b5d51a39cd3ac6e375e07244f32d39ae5870",
      "vout": 0,
      "scriptPubKey": "5120832977cba5adbe1f13b6507d161c711b4d8b62cdb3035c8be5e272cd7beb5182",
      "amount": 0.00005,
      "satoshis": 5000
    }
  ]
}'

# PSBT signing (Unisat compatible)
python social-wallet.py core sign_transaction '{
  "chain": "btc",
  "path": "m/86'\''0'\''0'\''0/0",
  "from": "bc1p...",
  "psbtHex": "70736274ff0100e7...",
  "__internalFunc": "__signPsbt_unisat",
  "options": {
    "autoFinalized": false,
    "signInputs": {"bc1p...": [0]}
  }
}'
```

**BTC fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| chain | string | Yes | `btc` |
| path | string | Yes | HD path: `m/86'/0'/0'/0/0` (Taproot), `m/84'/0'/0'/0/0` (SegWit), `m/44'/0'/0'/0/0` (Legacy) |
| from | string | Yes | Sender address |
| to | string | Yes | Recipient address |
| value | float | Yes | Amount in BTC |
| fee | string | Yes | Fee in BTC |
| utxos | array | Yes | UTXO list (each: address, txid, vout, scriptPubKey, amount, satoshis) |
| feeRate | int | No | Fee rate (satoshis/byte) |
| psbtHex | string | No | PSBT hex (for PSBT signing) |
| __internalFunc | string | No | `"__signPsbt_unisat"` for PSBT |
| options | object | No | PSBT sign options |

**BTC address types:**

| Type | path | Address prefix |
|------|------|---------------|
| Taproot | `m/86'/0'/0'/0/0` | `bc1p` |
| Native SegWit | `m/84'/0'/0'/0/0` | `bc1q` |
| Nested SegWit | `m/49'/0'/0'/0/0` | `3` |
| Legacy | `m/44'/0'/0'/0/0` | `1` |

#### SOL

```bash
# Native SOL transfer
python social-wallet.py core sign_transaction '{
  "chain": "sol",
  "to": "3zG7MWVbMn3sgpUc2o9NXUwSN9PYxQkhbpTayUaCbfWM",
  "value": "0.01",
  "fee": "0.000005",
  "recentBlockhash": "3a499brRdxYmm3FKc7yGbpfuxvbWFBV8pk7cZf5Hc6vS"
}'

# SPL token transfer (USDT)
python social-wallet.py core sign_transaction '{
  "chain": "sol",
  "contract": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
  "to": "H97DeDaSfMURDdmr7RnUFkgThY4FgS7DwDC77kR33zPG",
  "value": "0.1",
  "recentBlockhash": "6HwRhEAqhi368PUBfUiFVoVN4Vv6jZ7CjwnqByr4GWdi",
  "fromSource": "26gLeaNyhnqiD92Ei2nEnQjRhZDjcQZ18NvtQ6vSPkYz",
  "decimal": 6
}'

# Pre-built transaction (signData hex)
python social-wallet.py core sign_transaction '{
  "chain": "sol",
  "signData": {"hex": "020006106e655af38ff7324bbf1d4e16b06084763269b9..."}
}'

# Versioned transaction (signData serializedTransaction)
python social-wallet.py core sign_transaction '{
  "chain": "sol",
  "signData": {"serializedTransaction": "N5v1TwETGrQbCDYRtEXvbiFFUgCLdtLHxKsQuhvLVfTf...", "version": "0"}
}'
```

**SOL fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| chain | string | Yes | `sol` |
| to | string | Conditional | Recipient address (native/token transfer) |
| value | string | Conditional | Amount as string |
| recentBlockhash | string | Conditional | Recent block hash |
| contract | string | No | SPL token mint address |
| fromSource | string | No | Source token account |
| toSource | string | No | Destination token account |
| decimal | int | No | Token decimals |
| memo | string | No | Memo |
| fee | string | No | Fee |
| signData | object | No | Pre-built tx: `{hex}`, `{serializedTransaction, version}`, or `{sol_wc}` |

#### TRON

Three ways to pass params (priority order): `transaction` > `data` > top-level fields.

```bash
# Via transaction object (recommended)
python social-wallet.py core sign_transaction '{
  "chain": "tron",
  "transaction": {
    "visible": false,
    "txID": "abc123...",
    "raw_data": {"contract": [...], "ref_block_bytes": "1234", "ref_block_hash": "abcd1234", "expiration": 1234567890000, "timestamp": 1234567890000},
    "raw_data_hex": "0a02..."
  }
}'

# Multi-sig
python social-wallet.py core sign_transaction '{
  "chain": "tron",
  "transaction": {"visible": false, "txID": "abc123...", "raw_data_hex": "0a02...", "permissionId": 2}
}'
```


### sign_message

Sign a message. Supported on all chains.

```bash
# ETH — personal_sign (default)
python social-wallet.py core sign_message '{"chain": "eth", "message": "hello world!"}'

# ETH — EIP-712 TypedData
python social-wallet.py core sign_message '{
  "chain": "evm_custom#bnb",
  "message": {"__type": "typedData", "data": [{"type": "string", "name": "Message", "value": "Hi!"}]}
}'

# ETH — ethSign (raw hash)
python social-wallet.py core sign_message '{"chain": "eth", "message": "EthSign:0x879a053d4800c6354e76c7985a865d2922c82fb5b3f4577b2fe08b998954f2e0"}'

# BTC
python social-wallet.py core sign_message '{"chain": "btc", "message": "Hello Bitcoin"}'

# BTC — BIP322-Simple (Taproot)
python social-wallet.py core sign_message '{"chain": "btc", "message": "{\"message\":\"1\",\"__type\":\"bip322-simple\",\"address\":\"bc1p...\"}"}'

# SOL
python social-wallet.py core sign_message '{"chain": "sol", "message": "The quick brown fox"}'

```

**ETH/EVM message formats:**

| Format | message value | Description |
|--------|--------------|-------------|
| personal_sign | Plain text or `"Personal:..."` | Default, adds `\x19Ethereum Signed Message` prefix |
| ethSign | `"EthSign:0x..."` or `{"__type":"ethSign","data":"0x..."}` | Signs raw hash |
| typedData | `{"__type":"typedData","data":[...]}` | EIP-712 structured signing |

---

### get_address

Get the wallet address for a chain.

```bash
python social-wallet.py core get_address '{"chain": "eth"}'
python social-wallet.py core get_address '{"chain": "sol"}'
python social-wallet.py core get_address '{"chain": "btc", "ext": {"type": "taproot", "path": "m/86'\''0'\''0'\''0/0"}}'
```

---

### validate_address

Check if an address is valid.

```bash
python social-wallet.py core validate_address '{"chain": "eth", "address": "0xc82D88971c1cC94c1e0821aDD449a4655C98E2BA"}'
python social-wallet.py core validate_address '{"chain": "btc", "address": "bc1p..."}'
```

---

### get_public_key

Get the public key.

```bash
python social-wallet.py core get_public_key '{"chain": "eth", "format": "hex"}'
python social-wallet.py core get_public_key '{"chain": "sol", "format": "base58"}'
```

Formats: `hex`, `enc` (Base64 compressed), `base58`.

---

### convert_address

Convert address to multiple formats.

```bash
python social-wallet.py core convert_address '{"chain": "eth", "tag": ["evm", "source"]}'
python social-wallet.py core convert_address '{"chain": "btc"}'
```

---

### get_address_type (BTC only)

```bash
python social-wallet.py core get_address_type '{"chain": "btc", "address": "bc1p..."}'
```

---

### verify_message (SOL / TRON)

```bash
python social-wallet.py core verify_message '{"chain": "sol", "message": "hello", "signature": "...", "address": "..."}'
```

---

### decrypt_message (ETH / SOL / TRON)

```bash
python social-wallet.py core decrypt_message '{"chain": "eth", "message": "{\"version\":\"x25519-xsalsa20-poly1305\",\"nonce\":\"...\",\"ciphertext\":\"...\",\"ephemPublicKey\":\"...\"}"}'
```

---

## Operation Support Matrix

| Operation | BTC | ETH | EVM | SOL | TRON |
|-----------|:---:|:---:|:---:|:---:|:----:|
| sign_transaction | Y | Y | Y | Y | Y |
| sign_message | Y | Y | Y | Y | Y |
| get_address | Y | Y | Y | Y | Y |
| get_public_key | Y | Y | Y | Y | Y |
| validate_address | Y | Y | Y | Y | Y |
| validate_mnemonic | Y | Y | Y | Y | - | Y |
| convert_address | Y | Y | Y | Y | - | Y |
| verify_message | - | - | - | Y | Y |
| decrypt_message | - | Y | - | Y | Y |
| get_address_type | Y | - | - | - | - |
| bit_sign_message | Y | Y | Y | - | - |
| sign_hd_transaction | Y | - | - | Y | - | - | Y |
| sign_hd_message | Y | - | - | Y | - | - | Y |
