# Wallet & Signing Domain Knowledge

### Key Hierarchy (BIP-39 / BIP-44)

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

### Key Management for Agents

**Principle: minimal privilege, no persistence.**

```
Storage:     1Password only (never local files, env vars, or code)
Injection:   Fetch → use → destroy in same script execution
Scope:       Single private key, not full mnemonic
Derivation:  Done once during setup, only the derived key is stored
```

**Why agents hold a private key, not a mnemonic:**
- Mnemonic = master access to all chains and accounts
- Private key = access to one account on EVM chains (or one Solana account)
- If compromised, blast radius is limited to one key's assets
- Agent only needs to sign transactions, not derive new accounts

**Key retrieval pattern (Python):**
```python
# Fetch from 1Password, use, discard
import subprocess
key = subprocess.run(
    ["python3.13", "scripts/op_sdk.py", "get", "Agent Wallet", "--field", "evm_key", "--reveal"],
    capture_output=True, text=True
).stdout.strip()
# ... use key for signing ...
del key  # explicit cleanup
```

### Signature Types (EVM)

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

### Multi-Chain Signing

| Chain Family | Curve | Signing Library | Address Format |
|-------------|-------|----------------|----------------|
| EVM (ETH/BNB/Base/...) | secp256k1 | eth-account | 0x... (20 bytes, checksummed) |
| Solana | Ed25519 | solders / solana-py | Base58 (32 bytes) |
| Tron | secp256k1 | Same as EVM, Base58Check address | T... |

**EVM all-chain:** Sign once, broadcast to any EVM chain. The chainId in the tx prevents replay across chains.

### Transaction Anatomy (EVM)

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


