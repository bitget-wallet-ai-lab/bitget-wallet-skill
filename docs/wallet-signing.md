# Wallet & Signing

## Key Hierarchy

```
Mnemonic (24 words) → Seed → Master Key → Derivation Path:
  m/44'/60'/0'/0/0   → EVM (ETH/BNB/Base/Arbitrum/Polygon) — secp256k1
  m/44'/501'/0'/0'   → Solana — Ed25519 (SLIP-0010)
  m/44'/195'/0'/0/0  → Tron — secp256k1
```

- One mnemonic → all chains. EVM chains share one key/address.
- Only mnemonic is persisted. Private keys are derived on-the-fly, used, discarded.

## Signing Pipeline

```
Secure storage (mnemonic) → derive key → write to temp file (mktemp, chmod 600) → order_sign.py reads & deletes file → signed tx → discard key
```

**Never** pass keys as CLI arguments (visible in `ps`/history). Use `--private-key-file`.

## EVM Signature Types

| Type | When | How |
|------|------|-----|
| Raw Transaction | Normal swaps (`txs[].kind: "transaction"`) | `Account.sign_transaction(tx_dict)` |
| EIP-712 | Gasless/permits (`signType: "eip712"`) | `unsafe_sign_hash(api_hash)` — **not** `sign_message` |
| EIP-7702 | Delegation auth | `unsafe_sign_hash(keccak(0x05 \|\| rlp(...)))` |

⚠️ For API-provided hashes, **always use `unsafe_sign_hash`** (no EIP-191 prefix).

## Solana Signing

Binary format: `[shortvec: sig_count][sig_slots: 64B each][message_bytes]`

| Mode | sig[0] | sig[1] |
|------|--------|--------|
| User gas | User wallet | — |
| Gasless | Relayer (fee payer) | User wallet (partial-sign) |

Gasless: supported for ≥~$5. Cross-chain (Sol↔EVM): ≥$10.

Key formats handled automatically: Base58 keypair, hex 64-byte, hex 32-byte seed.

## order_sign.py Auto-Detection

| Input | Mode |
|-------|------|
| `data.signatures` present | EVM gasless (EIP-712) |
| `data.txs` + chainId=501/chain=sol | Solana |
| `data.txs` + EVM + `msgs[].signType: "eth_sign"` | EVM gasPayMaster |
| `data.txs` + EVM otherwise | EVM raw transaction |

## Usage

```bash
# EVM
echo '<makeOrder_json>' | python3 scripts/order_sign.py --private-key-file /tmp/.pk_evm
# Solana
python3 scripts/order_sign.py --order-json '<json>' --private-key-file-sol /tmp/.pk_sol
# Tron
python3 scripts/order_sign.py --order-json '<json>' --private-key-file-tron /tmp/.pk_tron
```

Dependencies: `eth-account` (EVM), pure Python Ed25519 + base58 (Solana, built-in).
