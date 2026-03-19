# First-Time Setup

## Wallet Setup

When a user first requests a swap or signing operation, check if a wallet is already configured. If not:

### Path 1: Create a new wallet

1. **Generate a BIP-39 mnemonic** (24 words / 256 bits). Use any available BIP-39 library.
2. **Store in secure storage** immediately. Never output mnemonic to chat/logs.
3. **Inform user** where the mnemonic is stored. They should back it up through secure means — not through conversation.
4. **Derive and show addresses** for EVM, Solana, Tron so user can verify and fund.

### Path 2: Query only (no wallet)

If user only wants price/token info/security checks — skip wallet setup. Signing unavailable.

### Derivation paths

| Chain | Path | Curve |
|-------|------|-------|
| EVM (ETH/BNB/Base/...) | `m/44'/60'/0'/0/0` | secp256k1 |
| Solana | `m/44'/501'/0'/0'` | Ed25519 (SLIP-0010) |
| Tron | `m/44'/195'/0'/0/0` | secp256k1 |

### Key management rules

- **Only mnemonic is persisted.** Private keys are derived on-the-fly, used, then discarded.
- **Mnemonic never sent to chat** — retrieved programmatically for derivation only.
- **Secure storage must:** (1) encrypt at rest, (2) require auth to read, (3) not expose in logs/history.
- **Private keys must never be transmitted externally** — not through APIs, chat, HTTP, webhooks, file uploads, clipboard. Keys exist only in local memory during signing. No exceptions.

### Signing pipeline

```
Secure storage (mnemonic) → derive private key (in memory) → write to temp file (mktemp) → sign → file auto-deleted → discard key variable
```

---

## First-Time Swap Configuration

On first swap, guide user through one-time preferences:

1. **Transaction deadline** — how long tx remains valid on-chain:
   - Conservative: `120s` (better sandwich attack protection)
   - Standard: `300s` (balanced, default)
   - Relaxed: `600s` (slow signing workflows)
   - _Shorter deadline = better price protection, but tx may fail if signing is slow._

2. **Automatic security check** — audit unfamiliar tokens before swaps:
   - Always check (recommended, default)
   - Ask each time
   - Skip (not recommended)

3. **Save preferences** in agent memory/config. User can update anytime.

If user declines: use defaults `deadline=300`, `security=always`.
