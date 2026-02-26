# Platform Compatibility Guide

This document covers which AI agent platforms support the Bitget Wallet Skill, how to install it on each, and the results of our verification testing.

## Compatibility Rule

Any AI agent that can **read files + execute Python + access the internet** can use this skill. The skill is self-contained — no external API keys or credentials are needed for testing.

---

## ✅ Tested & Verified Platforms

### OpenClaw

**Status:** ✅ Passed — Native support

**What is it:** An open-source AI agent runtime that connects to Telegram, Discord, Slack, and more.

**Installation:**
```bash
cd ~/.openclaw/workspace
git submodule add https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill.git skills/bitget-wallet
```

**How it works:** OpenClaw automatically detects `SKILL.md` in the `skills/` directory. The agent reads the skill instructions and calls the Python script directly when a user asks about crypto prices, token security, or swap quotes.

**Test result:** The agent correctly queried SOL/ETH prices and ran USDC security audits with accurate, real-time data.

---

### Manus

**Status:** ✅ Passed

**What is it:** A general-purpose AI agent by Meta with full computer access (browser, terminal, file system). Runs tasks in a sandboxed Ubuntu environment.

**Account setup:**
1. Go to [manus.im](https://manus.im)
2. Sign up with Google (free plan: 1,300 credits)

**Installation:** Simply provide the GitHub URL in your prompt:

> "Here's a skill for querying on-chain crypto data: https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill — Install it and use it to get the current price of SOL, ETH, and run a security audit on USDC on Solana."

**How it works:** Manus automatically (6 steps):
1. Read the skill-creator guide and visited the GitHub repository
2. Reviewed `SKILL.md` to understand API details and script instructions
3. Cloned the repo to `/home/ubuntu/skills/bitget-wallet-skill/`
4. Installed `requests` dependency
5. Ran `python3 scripts/bitget_api.py token-price --chain sol --contract ""`
6. Ran price query for ETH and security audit for USDC, then presented all results

**Test result:**
- SOL: $89.12 ✅
- ETH: $2,065.74 ✅
- USDC Audit: High Risk: No, 0 risks, 0 warnings, Buy/Sell Tax: 0%, Freeze/Mint Authority: No ✅
- Verdict: "USDC on Solana passes the security audit with zero risk and zero warning flags."

**Notes:** Manus completed all 6 steps autonomously and presented results in well-formatted tables. The skill was installed at `/home/ubuntu/skills/bitget-wallet-skill/` and is ready for future use. Free plan credits were sufficient.

---

### Bolt.new

**Status:** ✅ Passed

**What is it:** A web-based AI agent that builds full-stack applications from natural language prompts. Powered by Claude Sonnet.

**Account setup:**
1. Go to [bolt.new](https://bolt.new)
2. Sign up with Google (free tier: 300K daily tokens)

**Installation:** Provide the GitHub URL directly in the chat prompt:

> "Here's a skill for querying on-chain crypto data: https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill — Install it and use it to get the current price of SOL, ETH, and run a security audit on USDC on Solana."

**How it works:** Bolt automatically:
1. Fetched the repository and read `SKILL.md` and `README.md`
2. Understood the API structure and available commands
3. Installed the `requests` dependency
4. Ran `python3 scripts/bitget_api.py token-price --chain sol --contract ""`
5. Presented results in a formatted web UI

**Test result:**
- SOL: $85.25 ✅
- ETH: $1,993.73 ✅
- USDC Audit: PASSED — 0 risks, 0 warnings, Freeze/Mint Authority disabled ✅

**Notes:** Bolt also built a web frontend to display the results, which goes beyond the basic skill usage. Free tier was sufficient for the full test.

---

### Devin

**Status:** ✅ Passed

**What is it:** An AI software engineer by Cognition that can clone repos, write code, run commands, and create pull requests.

**Account setup:**
1. Go to [app.devin.ai/signup](https://app.devin.ai/signup)
2. Sign up with Google (free trial: 5.0 ACUs)

**Installation:** Enter the task in Devin's chat:

> "Clone https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill and use it to: 1) Get current price of SOL 2) Get current price of ETH 3) Run security audit on USDC on Solana (contract: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v). Show all results."

**How it works:** Devin automatically:
1. Read `SKILL.md` (lines 1–77) and `README.md` (lines 1–154)
2. Cloned the bitget-wallet-skill repository
3. Ran `pip install requests`
4. Executed three commands sequentially:
   - `python3 scripts/bitget_api.py token-price --chain sol --contract ""`
   - `python3 scripts/bitget_api.py token-price --chain eth --contract ""`
   - `python3 scripts/bitget_api.py security --chain sol --contract EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
5. Parsed JSON output and presented structured results

**Test result:**
- SOL: $85.98 ✅
- ETH: $2,009.69 ✅
- USDC Audit: High Risk: No, 0 risks, 0 warnings, Buy/Sell Tax: 0% ✅
- Verdict: "USDC on Solana passes the security audit cleanly — no risks or warnings detected."

**Notes:** Devin's approach was methodical — it read the documentation first, then executed commands step by step. The free trial was sufficient for the full test.

---

### Replit Agent

**Status:** ✅ Passed

**What is it:** An AI agent built into Replit that can create full applications from natural language descriptions.

**Account setup:**
1. Go to [replit.com](https://replit.com)
2. Sign up with Google (free Starter plan)

**Installation:** Enter the prompt on the Replit home page:

> "Here's a skill for querying on-chain crypto data: https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill — Install it and use it to get the price of SOL, ETH, and run a security audit on USDC on Solana."

**How it works:** Replit Agent automatically:
1. Created a new project called "Crypto Data Query"
2. Cloned the skill repository
3. Set up Python environment and installed dependencies
4. Ran all three query commands
5. Built a complete web application to display the results

**Test result:**
- SOL: $85.30 ✅
- ETH: $1,990.14 ✅
- USDC Audit: Security Status: EXCELLENT (No Risks Found), Freeze/Mint Authority: Disabled ✓ ✅
- "The USDC token on Solana appears to be legitimate and secure with no concerning security issues."

**Notes:** Replit went further than expected — it not only ran the skill but built a full web app around it with a polished UI. Used about 33% of the free Starter plan's agent credits for the entire test.

---

## 🔧 Compatible Platforms (Not Yet Tested)

These platforms have the required capabilities (file system access, Python execution, network access) and should work with this skill.

### CLI Agents

| Platform | How to Use |
|----------|------------|
| **Claude Code** | Clone repo into your project. The agent can read `SKILL.md` and execute scripts directly. |
| **Codex CLI (OpenAI)** | Clone repo, reference the skill in `AGENTS.md`. Codex will discover and use the scripts. |
| **Aider** | Add the scripts directory to your project. Aider can execute Python commands. |

### IDE Agents

| Platform | How to Use |
|----------|------------|
| **Cursor** | Clone into project directory, or use the [MCP version](https://github.com/bitget-wallet-ai-lab/bitget-wallet-mcp) for native tool integration. |
| **Windsurf** | Same as Cursor — clone or use MCP version. |
| **Cline (VS Code)** | Clone into workspace. Cline can read files and run terminal commands. |
| **Continue (VS Code / JetBrains)** | Clone into project, or configure MCP server. |

### Coding Agents

| Platform | How to Use |
|----------|------------|
| **OpenHands** | The Docker sandbox provides a full Linux environment. Clone and run directly. |
| **SWE-agent** | Has shell access — clone the repo and execute scripts. |

### Workflow / Low-Code Platforms

| Platform | How to Use |
|----------|------------|
| **Dify** | Import `bitget_api.py` as a Code node, or wrap as an external API Tool. |
| **Coze (扣子)** | Create a plugin with the API endpoints, or use the script as a Code block. |
| **n8n** | Use the AI Agent node with a code execution step. |
| **Langflow / Flowise** | Wrap as a custom tool in the visual workflow builder. |

### Frameworks

| Framework | How to Use |
|-----------|------------|
| **LangChain / LangGraph** | Import `bitget_api.py` functions as a `Tool`. |
| **CrewAI** | Wrap as a custom `Tool` class for your crew agents. |
| **AutoGen (Microsoft)** | Register as a function call tool. |
| **Semantic Kernel** | Import as a native function plugin. |

---

## 🔗 Alternative Integrations

For platforms that don't support direct file execution, use these alternatives:

| Need | Solution |
|------|----------|
| MCP-compatible agents (Claude Desktop, Cursor, Windsurf) | Use [bitget-wallet-mcp](https://github.com/bitget-wallet-ai-lab/bitget-wallet-mcp) |
| Terminal / CLI usage | Use [bitget-wallet-cli](https://github.com/bitget-wallet-ai-lab/bitget-wallet-cli) |
| REST API integration | Deploy the MCP server with SSE transport |

---

## Testing Methodology

All verified platforms were tested with the same prompt to ensure consistency:

> "Here's a skill for querying on-chain crypto data: https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill
>
> Please install this skill and use it to:
> 1. Get the current price of SOL
> 2. Get the current price of ETH
> 3. Run a security audit on USDC on Solana (contract: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v)
>
> Show me all the results."

**Evaluation criteria:**
- ✅ Agent independently reads documentation and understands the skill
- ✅ Agent installs dependencies without manual guidance
- ✅ Agent executes correct commands with proper arguments
- ✅ Returned data is accurate and matches real-time market data
- ✅ Security audit results are consistent across platforms
