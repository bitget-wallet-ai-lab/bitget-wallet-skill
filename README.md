# Bitget Wallet Skill

## Overview

An AI Agent skill that wraps the [Bitget Wallet API](https://web3.bitget.com/en/docs), enabling natural-language-driven on-chain data queries and swap operations.

### Design Principles

| Principle | Description |
|-----------|-------------|
| **Domain Knowledge + Tools** | Not just API wrappers — includes trading workflows, signing guides, security models, and known pitfalls so agents make informed decisions |
| **Zero External Dependencies** | All code is self-contained. Solana signing is pure Python (Ed25519 + base58 built-in). EVM signing uses `eth_account` (standard). Only `requests` for API calls. No pip install needed for Solana |
| **API Infrastructure, Not Reimplementation** | Capabilities come from Bitget Wallet's production API. The skill provides the knowledge and tooling layer, not a parallel implementation |
| **Human-in-the-Loop by Default** | Swap operations generate transaction data but never sign autonomously. User confirmation required for all fund-moving actions |

### Core Capabilities

| Capability | Description | Example |
|------------|-------------|---------|
| **Token Info** | Price, market cap, holders, social links | "What's the price of SOL?" |
| **Batch Price Query** | Multi-token price lookup in one call | Portfolio valuation |
| **K-line Data** | 1m/5m/1h/4h/1d candlestick data | Trend analysis, charting |
| **Transaction Stats** | 5m/1h/4h/24h buy/sell volume & trader count | Activity detection, whale monitoring |
| **Rankings** | Top gainers / top losers | Market scanning, alpha discovery |
| **Liquidity Pools** | LP pool information | Slippage estimation, depth analysis |
| **Security Audit** | Contract safety checks (honeypot, permissions, blacklist) | Pre-trade risk control |
| **Batch Tx Info** | Batch transaction statistics for multiple tokens | "Compare volume for SOL and ETH" |
| **Historical Coins** | Discover new tokens by timestamp | "What tokens launched today?" |
| **Swap Send** | Broadcast signed transactions with MEV protection | "Broadcast my signed swap" |
| **Swap Quote** | Best-route quote for cross-chain/same-chain swaps | "How much USDC for 1 SOL?" |
| **Swap Calldata** | Generate unsigned transaction data | Execute trades via wallet signing |
| **Order Quote** | Cross-chain + gasless aware price quote | "Quote 10 USDC Base to BNB USDT" |
| **Order Create** | Create order with unsigned tx/signature data | One-step cross-chain swap |
| **Order Submit** | Submit signed transactions for an order | Gasless or normal execution |
| **Order Status** | Track order lifecycle (init→processing→success) | "Check my swap status" |
| **x402 Payment** | Pay for x402-enabled APIs with USDC on Base | "Access this paid API endpoint" |

> ⚠️ **Swap amounts are human-readable** — pass `0.1` for 0.1 USDT, NOT `100000000000000000`. The `toAmount` in responses is also human-readable. This differs from most on-chain APIs.

### ✨ Order Mode — Gasless & Cross-Chain Swaps

Order Mode is the key upgrade in v2026.3.5. It enables two capabilities no other AI agent swap skill offers:

**⛽ Gasless Transactions (EIP-7702)**
- Swap tokens with **zero native token balance** — no ETH, no BNB, no MATIC needed
- Gas cost is deducted from the input token automatically
- Agent only signs; a backend relayer pays gas and broadcasts the transaction
- Supported on all EVM chains (Ethereum, Base, BNB Chain, Arbitrum, Polygon, Morph)

**🌉 One-Step Cross-Chain Swaps**
- Swap tokens across different chains in a **single order** — no manual bridging
- Example: USDC on Base → USDT on BNB Chain, one API call, one signature
- Combined with gasless: cross-chain swap with zero gas on the source chain

**How it works:**
```
1. order-quote   → Get price + check gasless support
2. order-create  → Create order, receive unsigned data
3. Sign          → Agent signs with wallet key (EIP-712 for gasless, raw tx for normal)
4. order-submit  → Submit signed data
5. order-status  → Track until success
```

**Example — Gasless cross-chain swap:**
```bash
# Quote: Base USDC → BNB USDT
python3 scripts/bitget_api.py order-quote \
  --from-chain base --from-contract 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --to-chain bnb --to-contract 0x55d398326f99059fF775485246999027B3197955 \
  --amount 10 --from-address 0xYourAddress --to-address 0xYourAddress

# Create order with gasless
python3 scripts/bitget_api.py order-create \
  --from-chain base --from-contract 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --to-chain bnb --to-contract 0x55d398326f99059fF775485246999027B3197955 \
  --amount 10 --from-address 0xYourAddress --to-address 0xYourAddress \
  --market bkbridgev3.liqbridge --slippage 1 --feature no_gas
```

### 💳 x402 Payments — Pay-Per-Request API Access

x402 is an open standard for HTTP-native payments. When an agent encounters a paid API (HTTP 402), it signs a USDC authorization and retries — no accounts, no API keys needed.

**How it works:**
```
1. Agent requests a resource → gets HTTP 402 + payment requirements
2. Agent signs EIP-3009 TransferWithAuthorization (gasless, off-chain)
3. Agent retries with PAYMENT-SIGNATURE header
4. Service's facilitator settles on-chain → agent gets the resource
```

**Key features:**
- **Truly gasless** — agent pays only USDC, facilitator sponsors gas
- **No accounts needed** — wallet address is your identity
- **Works with any x402 service** — Pinata IPFS, DiamondClaws DeFi data, and [100+ more](https://www.x402.org/ecosystem)

```bash
# Example: pay $0.001 for Pinata IPFS upload
python3 scripts/x402_pay.py pay \
  --url "https://402.pinata.cloud/v1/pin/private?fileSize=100" \
  --private-key <key> --method POST --data '{"fileSize": 100}' --auto
```

See [`docs/x402-payments.md`](docs/x402-payments.md) for domain knowledge, signing details, and testing guide.

### Supported Chains

Ethereum · Solana · BNB Chain · Base · Arbitrum · Tron · TON · Sui · Optimism and more.

---

## Architecture

```
Natural Language Input
    ↓
AI Agent (OpenClaw / Dify / Custom)
    ↓
bitget_api.py (Python 3.11+)
    ↓  ← Built-in demo keys or env var override
HMAC-SHA256 Signing
    ↓
Bitget Wallet API (bopenapi.bgwapi.io)
    ↓
Structured JSON → Agent interprets → Natural language response
```

**Security by Design:**
- Built-in demo credentials are public read-only API keys (safe to share)
- For production use, override with your own keys via `BGW_API_KEY` / `BGW_API_SECRET` env vars
- Swap calldata generates transaction data; signing requires explicit wallet key access
- **Wallet key management:** mnemonic stored in secure storage, private keys derived on-the-fly and discarded after each signing operation (never persisted)

---

## Agent Use Cases

### 1. Personal Research Assistant
> "Check if this Solana meme coin is safe, and give me a price quote."

- Token info + security audit + price in a single query
- For: individual traders, researchers
- Platforms: Telegram Bot, Discord Bot, OpenClaw

### 2. Portfolio Management Agent
> "What's my total portfolio value right now?"

- Batch query across chains and tokens, calculate net value
- Scheduled snapshots + K-line data for historical tracking
- For: DeFi users, fund managers
- Platforms: OpenClaw cron + Telegram alerts

### 3. Market Monitoring / Alert Agent
> Automatically scan top gainers, detect anomalies, push alerts

- Rankings + transaction volume + security audit combined
- Discover trending tokens → auto-run security audit → filter honeypots → notify user
- For: on-chain alpha hunters
- Platforms: Cron jobs, Dify workflows

### 4. Semi-Automated Trading Agent
> "Buy this token with 1 SOL"

- Swap quote → show route and slippage → user confirms → generate calldata → wallet signs
- **Human-in-the-loop** — the agent cannot sign independently
- For: active traders wanting an AI assistant
- Platforms: OpenClaw + Bitget Wallet App / hardware wallet

### 5. Arbitrage Bot Data Layer
> Monitor DEX price discrepancies, discover cross-chain arbitrage opportunities

- Multi-chain swap-quote comparison, calculate spreads
- Combine with CEX data for DEX-CEX spread monitoring
- For: quant teams
- Platforms: Custom Python scripts, OpenClaw sub-agents

### 6. Community Service Bot
> Someone asks "How much is XX coin?" in a group chat — bot auto-replies

- Lightweight queries, fast response
- Security audit feature doubles as anti-scam protection
- For: Telegram/Discord communities
- Platforms: Telegram Bot + OpenClaw skill

### 7. Dify / LangChain Tool Node
> Integrate as a Tool in Dify workflows or LangChain agents

- `bitget_api.py` can serve directly as a Dify Code node or external API Tool
- Can also be wrapped as an MCP Server for any MCP-compatible agent framework
- For: enterprise agent platform integration

---

## Quick Start

### Prerequisites

1. Python 3.11+
2. `requests` library (`pip install requests`)
3. For EVM signing: `eth-account` (`pip install eth-account`)
4. Public demo API credentials are built in. To use your own keys, set `BGW_API_KEY` and `BGW_API_SECRET` env vars.

> Solana signing requires **no additional packages** — pure Python Ed25519 and base58 are built into `order_sign.py`.

> **Note:** The built-in demo keys are for testing purposes and may change over time. If they stop working, please update the skill (`git pull`) to get the latest keys.

### Examples

```bash
# Get SOL price
python3 scripts/bitget_api.py token-price --chain sol --contract ""

# Security audit for a token
python3 scripts/bitget_api.py security --chain sol --contract <contract_address>

# Swap quote (1 SOL → USDC)
python3 scripts/bitget_api.py swap-quote \
  --from-chain sol --from-contract "" \
  --to-contract EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v \
  --amount 1
```

---

## Supported Chains (Order Mode)

| Chain | Same-chain | Cross-chain | Gasless |
|-------|-----------|-------------|---------|
| Ethereum | ✅ | ✅ | ✅ |
| BNB Chain | ✅ | ✅ | ✅ |
| Base | ✅ | ✅ | ✅ |
| Arbitrum | ✅ | ✅ | ✅ |
| Polygon | ✅ | ✅ | ✅ |
| Morph | ✅ | ✅ | ✅ |
| Solana | ✅ | ⚠️ Pending | ❌ Not supported |

> Calldata mode (non-order) supports additional chains: Tron, TON, Sui, Optimism, and more.

## Future Directions

| Direction | Description |
|-----------|-------------|
| **Solana Gasless** | Pending backend support — client signing is ready, awaiting relayer implementation |
| **On-chain Event Subscription** | WebSocket listeners for large transactions, new pool creation |
| **Historical Data Cache** | Store K-line + price data in local SQLite to reduce API calls |
| **Multi-wallet Management** | Support multi-address balance queries and batch quotes |
| **Risk Rule Engine** | Security audit results + custom rules (blacklist, min liquidity thresholds) |

---

## Compatible Platforms

### ✅ Tested & Verified

| Platform | Status | Notes |
|----------|--------|-------|
| [OpenClaw](https://openclaw.ai) | ✅ Passed | Native skill support |
| [Manus](https://manus.im) | ✅ Passed | Auto-installed and executed |
| [Bolt.new](https://bolt.new) | ✅ Passed | Auto-cloned repo, ran all commands |
| [Devin](https://devin.ai) | ✅ Passed | Read SKILL.md, installed deps, returned correct data |
| [Replit Agent](https://replit.com) | ✅ Passed | Full project setup with web frontend |

### 🔧 Should Work (file system + Python + network access)

| Platform | Type | How to Use |
|----------|------|------------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | CLI Agent | Clone repo, add SKILL.md to project context |
| [Codex CLI](https://github.com/openai/codex) | CLI Agent | Clone repo, reference in AGENTS.md |
| [Cursor](https://cursor.com) | IDE Agent | Clone into project, or use [MCP version](https://github.com/bitget-wallet-ai-lab/bitget-wallet-mcp) |
| [Windsurf](https://codeium.com/windsurf) | IDE Agent | Clone into project, or use [MCP version](https://github.com/bitget-wallet-ai-lab/bitget-wallet-mcp) |
| [Cline](https://github.com/cline/cline) | VS Code Agent | Clone into project workspace |
| [Aider](https://aider.chat) | CLI Agent | Add scripts to project |
| [OpenHands](https://github.com/All-Hands-AI/OpenHands) | Coding Agent | Docker sandbox with full file system |
| [SWE-agent](https://github.com/princeton-nlp/SWE-agent) | Coding Agent | Shell access in sandbox |
| [Dify](https://dify.ai) | Workflow Platform | Use as Code node or external API Tool |
| [Coze](https://www.coze.com) | Agent Platform | Import as plugin or API Tool |
| [LangChain](https://langchain.com) / [CrewAI](https://crewai.com) | Frameworks | Wrap `bitget_api.py` as a Tool |

### 💡 Compatibility Rule

Any AI agent that can **read files + run Python + access the internet** should work with this skill.

---

## Related Projects

- [bitget-wallet-mcp](https://github.com/bitget-wallet-ai-lab/bitget-wallet-mcp) — MCP Server for Claude Desktop / Cursor / Windsurf
- [bitget-wallet-cli](https://github.com/bitget-wallet-ai-lab/bitget-wallet-cli) — CLI tool for terminal users

---

## Security Notes

- Built-in demo API keys are public and read-only; for production, use env vars (`BGW_API_KEY` / `BGW_API_SECRET`)
- Swap functions generate quotes and transaction data — signing requires explicit wallet access
- Wallet mnemonic is the only persistent secret; private keys are derived per-operation and discarded
- Large operations require explicit user confirmation (human-in-the-loop)
- Always run a security audit (`security` command) before interacting with any token

## Security

- **Zero external dependencies for Solana** — pure Python Ed25519 (RFC 8032) and base58 built into `order_sign.py`. EVM uses `eth_account`. No obscure packages, no supply-chain risk.
- Only communicates with `https://bopenapi.bgwapi.io` (BGW API) and x402 resource servers — no other external endpoints
- No `eval()` / `exec()` or dynamic code execution
- No file system access outside the skill directory
- Built-in API keys are public demo credentials (safe to commit)
- No data collection, telemetry, or analytics
- No access to sensitive files (SSH keys, credentials, wallet files, etc.)
- We recommend auditing the source yourself before installation

## License

MIT
