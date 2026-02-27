# Bitget Wallet ToB API Skill

## Overview

An AI Agent skill that wraps the [Bitget Wallet ToB API](https://web3.bitget.com/en/docs), enabling natural-language-driven on-chain data queries and swap operations.

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

> ⚠️ **Swap amounts are human-readable** — pass `0.1` for 0.1 USDT, NOT `100000000000000000`. The `toAmount` in responses is also human-readable. This differs from most on-chain APIs.
| **Swap Quote** | Best-route quote for cross-chain/same-chain swaps | "How much USDC for 1 SOL?" |
| **Swap Calldata** | Generate unsigned transaction data | Execute trades via wallet signing |

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
Bitget Wallet ToB API (bopenapi.bgwapi.io)
    ↓
Structured JSON → Agent interprets → Natural language response
```

**Security by Design:**
- Built-in demo credentials are public read-only API keys (safe to share)
- For production use, override with your own keys via `BGW_API_KEY` / `BGW_API_SECRET` env vars
- Swap calldata only generates transaction data; **actual signing requires wallet confirmation** (prevents unauthorized transactions)

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
3. That's it — public demo API credentials are built in. To use your own keys, set `BGW_API_KEY` and `BGW_API_SECRET` env vars.

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

## Future Directions

| Direction | Description |
|-----------|-------------|
| **MCP Server Wrapper** | Package as a standard MCP Tool for Claude / Dify / any MCP client |
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
- Swap functions only generate quotes and transaction data — **no autonomous signing capability**
- Large operations require explicit user confirmation (human-in-the-loop)
- Always run a security audit (`security` command) before interacting with any token

## Security

- Only communicates with `https://bopenapi.bgwapi.io` — no other external endpoints
- No `eval()` / `exec()` or dynamic code execution
- No file system access outside the skill directory
- Built-in API keys are public demo credentials (safe to commit)
- No data collection, telemetry, or analytics
- No access to sensitive files (SSH keys, credentials, wallet files, etc.)
- Dependencies: `requests` only (stdlib: `hmac`, `hashlib`, `json`, `base64`)
- We recommend auditing the source yourself before installation

## License

MIT
