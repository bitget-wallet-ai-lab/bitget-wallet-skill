# Bitget Wallet Skill

## Overview

An AI Agent skill that wraps the [Bitget Wallet API](https://web3.bitget.com/en/docs), enabling natural-language-driven on-chain data queries and swap operations.

### Design Principles

| Principle | Description |
|-----------|-------------|
| **Domain Knowledge + Tools** | Not just API wrappers — includes swap flow (see `docs/swap.md`), signing guides, security models, and known pitfalls so agents make informed decisions |
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
| **Rankings** | Top gainers / top losers / Hotpicks (curated trending) | Market scanning, alpha discovery |
| **Liquidity Pools** | LP pool information | Slippage estimation, depth analysis |
| **Security Audit** | Contract safety checks (honeypot, permissions, blacklist) | Pre-trade risk control |
| **Batch Tx Info** | Batch transaction statistics for multiple tokens | "Compare volume for SOL and ETH" |
| **Historical Coins** | Discover new tokens by timestamp | "What tokens launched today?" |
| **Swap Send** | Broadcast signed transactions with MEV protection | "Broadcast my signed swap" |
| **Swap Quote** | Multi-market quotes for same-chain/cross-chain swaps | "How much USDC for 1 SOL?" |
| **Swap Confirm** | Final quote from selected market with orderId | Lock in price and route |
| **Swap MakeOrder** | Generate unsigned transaction data for signing | Execute trades via wallet signing |
| **Swap Send** | Submit signed transactions | Broadcast with MEV protection |
| **Order Details** | Track order lifecycle (processing→success/failed) | "Check my swap status" |
| **x402 Payment** | Pay for x402-enabled APIs with USDC on Base | "Access this paid API endpoint" |

> ⚠️ **Swap amounts are human-readable** — pass `0.1` for 0.1 USDT, NOT `100000000000000000`. The `toAmount` in responses is also human-readable. This differs from most on-chain APIs.

### ✨ Order Mode — Gasless & Cross-Chain Swaps

The swap flow enables two capabilities no other AI agent swap skill offers:

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
1. quote          → Get multi-market quotes
2. confirm        → Final quote from chosen market, get orderId
3. makeOrder      → Create unsigned transaction data
4. Sign           → Agent signs with wallet key
5. send           → Submit signed data
6. getOrderDetails → Track until success
```

**Example — Same-chain swap:**
```bash
# Quote: BNB USDT → USDC
python3 scripts/bitget_agent_api.py quote \
  --from-chain bnb --from-contract 0x55d398326f99059fF775485246999027B3197955 \
  --from-symbol USDT --from-amount 5 \
  --to-chain bnb --to-contract 0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d \
  --to-symbol USDC \
  --from-address 0xYourAddress --to-address 0xYourAddress

# Confirm with chosen market
python3 scripts/bitget_agent_api.py confirm \
  --from-chain bnb --from-contract 0x55d398326f99059fF775485246999027B3197955 \
  --from-symbol USDT --from-amount 5 \
  --to-chain bnb --to-contract 0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d \
  --to-symbol USDC \
  --from-address 0xYourAddress --to-address 0xYourAddress \
  --market bgwevmaggregator --protocol bgwevmaggregator_v000 \
  --slippage 0.01 --feature user_gas
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
bitget_agent_api.py (Python 3.9+)
    ↓  ← Token auth (no API key needed)
Bitget Agent API (copenapi.bgwapi.io)
    ↓
Structured JSON → Agent interprets → Natural language response
```

**Security by Design:**
- No API key or HMAC signing needed — uses token-based authentication
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

- `bitget_agent_api.py` can serve directly as a Dify Code node or external API Tool
- Can also be wrapped as an MCP Server for any MCP-compatible agent framework
- For: enterprise agent platform integration

---

## Quick Start

### Prerequisites

1. Python 3.9+
2. `requests` library (`pip install requests`)
3. For EVM signing: `eth-account` (`pip install eth-account`)

> No API key needed — the Agent API uses token-based authentication with built-in headers.

> Solana signing requires **no additional packages** — pure Python Ed25519 and base58 are built into `order_sign.py`.

### Examples

```bash
# Get SOL price
python3 scripts/bitget_agent_api.py token-price --chain sol --contract ""

# Security audit for a token
python3 scripts/bitget_agent_api.py security --chain sol --contract <contract_address>

# Swap quote (5 USDT → USDC on BNB Chain)
python3 scripts/bitget_agent_api.py quote \
  --from-chain bnb --from-contract 0x55d398326f99059fF775485246999027B3197955 \
  --from-symbol USDT --from-amount 5 \
  --to-chain bnb --to-contract 0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d \
  --to-symbol USDC \
  --from-address 0xYourAddress --to-address 0xYourAddress
```

---

## Supported Chains (Swap)

| Chain | Same-chain | Cross-chain | Gasless |
|-------|-----------|-------------|---------|
| Ethereum | ✅ | ✅ | ✅ |
| BNB Chain | ✅ | ✅ | ✅ |
| Base | ✅ | ✅ | ✅ |
| Arbitrum | ✅ | ✅ | ✅ |
| Polygon | ✅ | ✅ | ✅ |
| Morph | ✅ | ✅ | ✅ |
| Solana | ✅ | ⚠️ Pending | ❌ Not supported |

> Market data commands support 32+ chains. See `docs/market-data.md` for the full list.

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
| [LangChain](https://langchain.com) / [CrewAI](https://crewai.com) | Frameworks | Wrap `bitget_agent_api.py` as a Tool |

### 💡 Compatibility Rule

Any AI agent that can **read files + run Python + access the internet** should work with this skill.

---

## Related Projects

- [bitget-wallet-mcp](https://github.com/bitget-wallet-ai-lab/bitget-wallet-mcp) — MCP Server for Claude Desktop / Cursor / Windsurf
- [bitget-wallet-cli](https://github.com/bitget-wallet-ai-lab/bitget-wallet-cli) — CLI tool for terminal users

---

## Security Notes

- No API keys needed — uses token-based authentication (no secrets to manage)
- Swap functions generate quotes and transaction data — signing requires explicit wallet access
- Wallet mnemonic is the only persistent secret; private keys are derived per-operation and discarded
- Large operations require explicit user confirmation (human-in-the-loop)
- Always run a security audit (`security` command) before interacting with any token

## Security

- **Zero external dependencies for Solana** — pure Python Ed25519 (RFC 8032) and base58 built into `order_sign.py`. EVM uses `eth_account`. No obscure packages, no supply-chain risk.
- Only communicates with `https://copenapi.bgwapi.io` (Agent API) and x402 resource servers — no other external endpoints
- No `eval()` / `exec()` or dynamic code execution
- No file system access outside the skill directory
- No data collection, telemetry, or analytics
- No access to sensitive files (SSH keys, credentials, wallet files, etc.)
- We recommend auditing the source yourself before installation

## License

MIT
