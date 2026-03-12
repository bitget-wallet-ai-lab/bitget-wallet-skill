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

## Mnemonic file and addresses (no wallet directory)

This skill **does not** use a `wallet/` directory. There is no create-wallet, no multi-wallet, no list/switch.

**Critical rule for agents:** The user provides a **file path** to their BIP-39 mnemonic. Run `python3 scripts/wallet_cli.py --mnemonic-file <path>` to get **only** addresses (evm_address, solana_address, tron_address) and store them in context. **Do not** output or store mnemonic or private keys anywhere in the conversation.

- **Addresses in context:** Store the output of `wallet_cli.py --mnemonic-file <path>` (evm_address, solana_address, tron_address) in conversation context. Use them for `--from-address` / `--to-address` in quote, confirm, balance, and `order_make_sign_send.py`.
- **Before balance or swap:** If the user has not provided a mnemonic file path in the conversation, prompt them first; then run `wallet_cli.py --mnemonic-file <path>` and store addresses in context.

### Security and signing

Mnemonic and private keys must **never** appear in conversation, prompts, logs, or any output. Only the mnemonic **file path** and derived **addresses** may be stored or shown. **`order_make_sign_send.py`** reads the mnemonic file locally, derives keys in memory, signs, and never prints mnemonic or keys. It requires `--mnemonic-file`, `--from-address`, `--to-address` (from context). MakeOrder unsigned data expires in ~60 seconds; run `order_make_sign_send.py` in one go right after user confirms. Key derivation: `derive_wallets_from_mnemonic()` in `wallet_from_mnemonic.py`; used by `wallet_cli.py` (addresses only) and `order_make_sign_send.py` (sign in memory). **⚠️ Never** output mnemonic or private keys in chat or logs.

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
python3 scripts/bitget_agent_api.py make-order ... | python3 scripts/order_sign.py --private-key <hex>
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


