# x402 Payments Domain Knowledge

## What is x402?

x402 is an open standard for internet-native payments, built on HTTP 402 ("Payment Required"). It enables AI agents to pay for API access, data, and services using crypto — no accounts, no API keys, no subscriptions.

**Why agents need this:** As AI agents call external APIs (market data, compute, storage, premium content), x402 lets them pay per-request with stablecoins instead of managing API keys and subscriptions.

## Protocol Flow

```
1. Agent → GET /premium-data → Resource Server
2. Resource Server → 402 Payment Required + PaymentRequirements (in headers)
3. Agent reads requirements (amount, token, network, payTo, scheme)
4. Agent signs payment authorization (EIP-3009 or Permit2 or Solana partial-sign)
5. Agent → GET /premium-data + PAYMENT-SIGNATURE header → Resource Server
6. Resource Server → Facilitator /verify → Facilitator /settle → blockchain
7. Resource Server → 200 OK + data + PAYMENT-RESPONSE header → Agent
```

**Key insight:** The agent signs but never broadcasts. The Facilitator pays gas and submits on-chain. Agent is truly gasless.

## Payment Schemes

### `exact` on EVM

Two methods, prioritized in order:

| Method | Token Support | Prerequisite | Gasless? |
|--------|--------------|-------------|----------|
| **EIP-3009** | USDC (native `transferWithAuthorization`) | None | ✅ Truly gasless |
| **Permit2** | Any ERC-20 | One-time `approve(Permit2)` | ✅ After approval |

#### EIP-3009 (Preferred for USDC)

Agent signs a `transferWithAuthorization` message (EIP-712 typed data):

```
Domain: token contract (e.g., USDC on Base)
Types: { TransferWithAuthorization(from, to, value, validAfter, validBefore, nonce) }
```

**Signing payload fields:**
- `from`: Agent wallet address
- `to`: Resource server's `payTo` address
- `value`: Payment amount (in token smallest unit, e.g., 10000 = $0.01 USDC)
- `validAfter`: Current timestamp
- `validBefore`: Current timestamp + `maxTimeoutSeconds`
- `nonce`: Random 32-byte hex (unique per authorization)

**Security properties:**
- Facilitator CANNOT modify amount or destination — signature binds both
- Signature is single-use (nonce prevents replay)
- Time-bounded (validBefore prevents stale authorization)

#### Permit2 (Universal Fallback)

For tokens without EIP-3009. Uses Uniswap's canonical Permit2 contract + x402ExactPermit2Proxy.

**One-time setup:** Agent must `approve(Permit2_contract, max_uint256)` — costs gas once.

**Signing payload fields:**
- `permitted.token`: Token address
- `permitted.amount`: Payment amount
- `spender`: x402ExactPermit2Proxy address (NOT the facilitator)
- `nonce`: Random 32-byte hex
- `deadline`: Expiry timestamp
- `witness.to`: payTo address (enforced on-chain by proxy)

### `exact` on Solana

Solana uses a different model — partially-signed transactions:

1. Agent builds a `VersionedTransaction` containing SPL `TransferChecked` instruction
2. `feePayer` = Facilitator's pubkey (from PaymentRequirements.extra.feePayer)
3. Agent signs as the token authority (partial sign — feePayer slot left empty)
4. Serialize → base64 → send in PAYMENT-SIGNATURE header
5. Facilitator validates, adds feePayer signature, submits to Solana

**Transaction structure (3-5 instructions):**
```
1. ComputeBudget: SetComputeUnitLimit
2. ComputeBudget: SetComputeUnitPrice
3. SPL Token: TransferChecked (amount, from ATA, to ATA, mint)
4. (Optional) Lighthouse instruction (Phantom wallet protection)
5. (Optional) Lighthouse instruction (Solflare wallet protection)
```

## Integration for BGW Agents

### As a Client (Paying for Services)

When the agent encounters a 402 response:

1. **Parse** `PAYMENT-REQUIRED` header (base64-decoded JSON)
2. **Check** if we support the `scheme` + `network` combination
3. **Check** wallet balance covers the `amount`
4. **Sign** the payment authorization using the appropriate method
5. **Retry** the request with `PAYMENT-SIGNATURE` header

**Supported networks:**
- `eip155:8453` (Base) — primary, USDC via EIP-3009
- `eip155:1` (Ethereum) — USDC via EIP-3009
- `eip155:137` (Polygon) — USDC via EIP-3009
- `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp` (Solana mainnet)

### As a Server (Charging for Services)

BGW skill endpoints could be wrapped with x402 middleware to charge for:
- Swap execution
- Market data queries
- Security audits
- Cross-chain routing

### Budget & Safety

**Agent spending controls:**
- Per-request maximum (e.g., $0.10 per API call)
- Per-session budget (e.g., $5.00 total per session)
- Per-day budget (e.g., $50.00 daily cap)
- Require user confirmation above threshold

**Risk model (from conversation analysis):**
- EIP-3009 signing does NOT lock funds — signature is just an authorization
- Multiple signatures can be outstanding simultaneously
- If wallet balance drops before settlement, later settlements fail (revert)
- This is credit risk, not theft risk — facilitator bears the loss, not the agent

## Key Contracts & Addresses

### USDC (EIP-3009 compatible)
| Chain | USDC Address | EIP-3009 Support |
|-------|-------------|-----------------|
| Base | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | ✅ |
| Ethereum | `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48` | ✅ |
| Polygon | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` | ✅ |
| Arbitrum | `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` | ✅ |

### Permit2 (Canonical)
- Address: See [Uniswap Permit2 deployments](https://docs.uniswap.org/contracts/v4/deployments)
- Same address across all supported EVM chains (CREATE2)

### Facilitator
- Coinbase public facilitator: `https://x402.org/facilitator`

## EIP-3009 Signing Reference

```python
from eth_account import Account
from eth_account.messages import encode_typed_data
import os, time

def sign_x402_eip3009(private_key, token_address, chain_id, to, value, max_timeout=60):
    """Sign a transferWithAuthorization for x402 payment."""
    now = int(time.time())
    nonce = "0x" + os.urandom(32).hex()

    domain = {
        "name": "USD Coin",        # Check token contract for actual name
        "version": "2",             # Check token contract for actual version
        "chainId": chain_id,
        "verifyingContract": token_address,
    }

    types = {
        "TransferWithAuthorization": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
        ]
    }

    message = {
        "from": Account.from_key(private_key).address,
        "to": to,
        "value": value,
        "validAfter": now,
        "validBefore": now + max_timeout,
        "nonce": nonce,
    }

    signable = encode_typed_data(domain, types, message)
    signed = Account.sign_message(signable, private_key)
    return {
        "signature": signed.signature.hex(),
        "authorization": {
            "from": message["from"],
            "to": to,
            "value": str(value),
            "validAfter": str(now),
            "validBefore": str(now + max_timeout),
            "nonce": nonce,
        }
    }
```

## Solana Partial-Sign Reference

```python
import base58, base64
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.system_program import transfer, TransferParams
from solders.message import MessageV0
from spl.token.instructions import transfer_checked, TransferCheckedParams

def sign_x402_solana(private_key_hex, serialized_tx_b64):
    """Partially sign a Solana x402 payment transaction."""
    kp = Keypair.from_seed(bytes.fromhex(private_key_hex))
    tx_bytes = base64.b64decode(serialized_tx_b64)
    vtx = VersionedTransaction.from_bytes(tx_bytes)

    # Find our signer index
    our_index = -1
    for i, key in enumerate(vtx.message.account_keys):
        if key == kp.pubkey():
            our_index = i
            break

    if our_index == -1:
        raise ValueError(f"Wallet {kp.pubkey()} not found in transaction signers")

    # Extract message bytes and sign
    original_bytes = bytes(vtx)
    sig_count = len(vtx.signatures)
    sig_array_start = 1  # shortvec for count=2 is 1 byte
    if sig_count >= 128:
        sig_array_start = 2
    msg_bytes = original_bytes[sig_array_start + sig_count * 64:]
    sig = kp.sign_message(msg_bytes)

    # Splice signature into correct slot
    new_tx = bytearray(original_bytes)
    offset = sig_array_start + our_index * 64
    new_tx[offset:offset + 64] = bytes(sig)

    return base64.b64encode(bytes(new_tx)).decode()
```

## Common Pitfalls

1. **Amount units vary by token.** USDC has 6 decimals: `10000` = $0.01, `1000000` = $1.00. Always check `decimals`.
2. **EIP-3009 domain name/version must match token contract.** USDC uses `name="USD Coin", version="2"`. Wrong values = invalid signature.
3. **Nonce must be unique per authorization.** Use `os.urandom(32)` — collision = rejected payment.
4. **validBefore must not exceed maxTimeoutSeconds.** Facilitator rejects expired authorizations.
5. **Solana feePayer is NOT the agent.** The facilitator pays gas. Agent only signs as token authority.
6. **Multiple outstanding signatures = credit risk.** Signing doesn't lock funds. If balance drops below cumulative signed amount, later settlements revert.
7. **Permit2 requires one-time approval.** First payment on a new token costs gas for the approve tx.
8. **x402 is USDC-first.** EIP-3009 is the preferred path. USDT does NOT support EIP-3009 on most chains.
