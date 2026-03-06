# Wallet & Signing Domain Knowledge

## Key Hierarchy (BIP-39 / BIP-44)

```
Mnemonic (12/24 words)
  └→ Seed (512 bits via PBKDF2)
      └→ Master Key
          └→ Derivation Path (BIP-44)
              ├→ m/44'/60'/0'/0/0   → EVM private key → ETH/BNB/Base/Arbitrum/Polygon address
              ├→ m/44'/60'/0'/0/1   → EVM account #2
              ├→ m/44'/501'/0'/0'   → Solana private key (Ed25519)
              └→ m/44'/195'/0'/0/0  → Tron private key
```

**Critical facts:**
- **One mnemonic → all chains.** The same 12/24 words derive keys for every supported chain.
- **EVM chains share one key.** ETH, BNB, Base, Arbitrum, Polygon, Optimism all use the same private key and address at `m/44'/60'/0'/0/0`.
- **Solana uses a different key.** Ed25519 (not secp256k1). Different address, different signing algorithm.
- **Private key ≠ mnemonic.** A private key is one specific key derived from the mnemonic. Losing the mnemonic means losing access to all derived keys.

## Key Management for Agents

**Principle: mnemonic is the only persistent secret. Private keys are ephemeral.**

```
Storage:     Mnemonic in secure storage (encrypted vault, keychain, etc.)
Derivation:  On-the-fly, per signing operation
Lifecycle:   Derive → sign → discard. Keys never persist beyond a single operation.
```

**Why store a mnemonic, not individual keys:**
- One mnemonic → all chains (EVM, Solana, future chains)
- No key inventory to manage — derive what you need, when you need it
- Adding new chains requires zero storage changes
- Reduced attack surface — fewer persistent secrets

**Secure storage requirements:**
The mnemonic must be stored in a mechanism that:
1. Encrypts at rest
2. Requires authentication to read
3. Does not expose secrets in logs, shell history, or environment dumps

Examples: password managers (1Password, Bitwarden), OS keychains, encrypted vaults, hardware security modules.

**Signing pipeline:**
```
Secure storage → mnemonic → derive private key (in memory) → order_sign.py → signed tx → discard key
```

**Key derivation (conceptual):**
```python
# 1. Retrieve mnemonic from secure storage
mnemonic = retrieve_from_secure_storage("Agent Wallet", "mnemonic")

# 2. Derive key for the target chain
if chain == "evm":
    # m/44'/60'/0'/0/0, secp256k1
    from eth_account import Account
    Account.enable_unaudited_hdwallet_features()
    key = Account.from_mnemonic(mnemonic).key.hex()
elif chain == "sol":
    # m/44'/501'/0'/0', Ed25519 via SLIP-0010
    key = derive_solana_key(mnemonic)  # HMAC-SHA512 chain derivation

del mnemonic  # discard mnemonic immediately after derivation

# 3. Sign transaction
signed = sign_order(order_json, key)
del key  # discard key immediately after signing
```

**⚠️ Never:**
- Store derived private keys persistently
- Print mnemonic or keys to chat channels (except during initial wallet setup)
- Pass secrets via command-line arguments visible in `ps` output (prefer stdin/env vars for production)

## Signature Types (EVM)

| Type | Use Case | How to Sign |
|------|----------|-------------|
| **Raw Transaction** (type 0/2) | Normal transfers, swaps | `Account.sign_transaction(tx_dict)` → full signed tx hex |
| **EIP-191** (personal_sign) | Message signing, off-chain auth | `Account.sign_message(encode_defunct(msg))` |
| **EIP-712** (typed data) | Structured data (permits, orders) | `Account.sign_message(encode_typed_data(...))` or `unsafe_sign_hash(hash)` |
| **EIP-7702** (delegation auth) | Delegate EOA to smart contract | `unsafe_sign_hash(keccak(0x05 \|\| rlp([chainId, addr, nonce])))` |

**When to use which:**
- API returns `txs` with `kind: "transaction"` → Raw Transaction signing
- API returns `signatures` with `signType: "eip712"` → EIP-712 (use API hash)
- API returns `signatures` with `signType: "eip7702_auth"` → EIP-7702 delegation

**⚠️ `unsafe_sign_hash` vs `sign_message`:**
- `sign_message` adds the EIP-191 prefix (`\x19Ethereum Signed Message:\n32`)
- `unsafe_sign_hash` signs the raw hash directly (no prefix)
- For API-provided hashes, **always use `unsafe_sign_hash`** — the hash is already the final digest
- Using `sign_message` on a pre-computed hash produces a wrong signature

## Multi-Chain Signing

| Chain Family | Curve | Signing Library | Address Format |
|-------------|-------|----------------|----------------|
| EVM (ETH/BNB/Base/...) | secp256k1 | eth-account | 0x... (20 bytes, checksummed) |
| Solana | Ed25519 | solders / solana-py | Base58 (32 bytes) |
| Tron | secp256k1 | Same as EVM, Base58Check address | T... |

**EVM all-chain:** Sign once, broadcast to any EVM chain. The chainId in the tx prevents replay across chains.

## Transaction Anatomy (EVM)

```
Type 0 (Legacy):     {nonce, gasPrice, gasLimit, to, value, data}
Type 2 (EIP-1559):   {nonce, maxFeePerGas, maxPriorityFeePerGas, gasLimit, to, value, data, chainId}
Type 4 (EIP-7702):   {... + authorizationList: [{chainId, address, nonce, y_parity, r, s}]}
```

**Key fields for swap transactions:**
- `to`: Router contract (not the destination token)
- `data`: Encoded swap calldata from API
- `value`: Amount of native token to send (0 for ERC-20 swaps, >0 for native → token)
- `nonce`: Must match account's current nonce (API provides this)
- `gasLimit` / `gasPrice`: API provides estimates

## Solana Transaction Signing

### Transaction Format

Solana transactions are serialized in a binary format, transmitted as **base58** strings:

```
[shortvec: sig_count][sig_0: 64B][sig_1: 64B]...[message_bytes]
```

- **shortvec**: Variable-length encoding of the signature count
- **sig_N**: 64-byte Ed25519 signature slots (filled with zeros when unsigned)
- **message_bytes**: The transaction message to sign
  - For **V0 transactions**: starts with `0x80` version prefix
  - For **Legacy transactions**: no version prefix

### Signer Slots

The first N account keys in the message correspond to required signers (N = `header.num_required_signatures`):

| Mode | sig[0] | sig[1] | Description |
|------|--------|--------|-------------|
| **Gasless (no_gas)** | Relayer (fee payer) | User wallet | Backend fills sig[0] after submission |
| **User gas** | User wallet | — | User is the sole signer and fee payer |

**⚠️ Solana gasless status (2026-03-06):** Backend does NOT currently support Solana gasless. `features: []` returned for all Solana quotes. Forcing `no_gas` creates the order but relayer never signs `sig[0]` → order fails immediately. Use `user_gas` mode only.

### Partial Signing Pattern

For gasless (2-signer) transactions, the user performs a **partial sign**:

1. **Base58 decode** the `serializedTx` from API response
2. **Parse** signature count via shortvec decoding
3. **Extract message bytes** (everything after the signature slots)
4. **Find user's signer index** in `account_keys[:num_required_signatures]`
5. **Ed25519 sign** the message bytes with user's private key
6. **Write** the 64-byte signature into the correct slot
7. **Base58 encode** and return the partially-signed transaction

```python
# Conceptual flow (actual implementation in order_sign.py)
tx_bytes = base58.b58decode(serialized_tx)
sig_count, header_len = decode_shortvec(tx_bytes, 0)
message_bytes = tx_bytes[header_len + (sig_count * 64):]

signature = keypair.sign_message(message_bytes)  # Ed25519
tx_bytes[header_len + (signer_index * 64) : +64] = bytes(signature)

return base58.b58encode(tx_bytes)
```

### Key Format (Solana)

Solana private keys can be in multiple formats:

| Format | Length | Example |
|--------|--------|---------|
| **Base58** (keypair) | ~88 chars | Standard Phantom/CLI export |
| **Hex (64 bytes)** | 128 chars | Full keypair (privkey + pubkey) |
| **Hex (32 bytes)** | 64 chars | Seed only (pubkey derived) |

The `_load_sol_keypair()` function in `order_sign.py` handles all three formats automatically.

### Key Retrieval

All keys are derived on-the-fly from the mnemonic in secure storage. The agent should:

1. Retrieve the mnemonic from its configured secure storage
2. Derive the chain-specific private key using the correct BIP-44 path
3. Pass the key to `order_sign.py` via `--private-key` (EVM) or `--private-key-sol` (Solana)
4. Discard both mnemonic and key from memory after signing

**Secure storage holds only:**
- The BIP-39 mnemonic (the single persistent secret for all chains)

## Order Mode Signing (order_sign.py)

`scripts/order_sign.py` handles signing for the order-create → order-submit flow.

### Usage

```bash
# EVM: pipe or pass JSON
python3 scripts/bitget_api.py order-create ... | python3 scripts/order_sign.py --private-key <hex>
python3 scripts/order_sign.py --order-json '<json>' --private-key <hex>

# Solana: use --private-key-sol
python3 scripts/order_sign.py --order-json '<json>' --private-key-sol <base58|hex>
```

### Auto-Detection

The script auto-detects the chain and signing mode:

| Input | Detection | Handler |
|-------|-----------|---------|
| `data.signatures` present | EVM gasless (EIP-712) | `sign_order_signatures()` |
| `data.txs` + chainId=501 or chainName=sol | Solana | `sign_order_txs_solana()` |
| `data.txs` + other chain | EVM transaction | `sign_order_txs_evm()` |

### Data Shape Flexibility

The Solana signer handles multiple API response shapes:

```json
// Shape 1: kind/data wrapper
{"txs": [{"kind": "transaction", "data": {"serializedTx": "..."}}]}

// Shape 2: nested data
{"txs": [{"chainId": "501", "data": {"serializedTx": "..."}}]}

// Shape 3: flat
{"txs": [{"chainId": "501", "serializedTx": "..."}]}
```

### Dependencies

| Chain | Required Libraries |
|-------|-------------------|
| EVM | `eth-account` (pre-installed) |
| Solana | `solders`, `base58` (pip install) |


