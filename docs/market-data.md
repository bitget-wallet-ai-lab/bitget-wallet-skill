# Market Data Domain Knowledge

## Tool Architecture — Market Side

Market tools handle **"选币"** and **"选地址"** only. No trading/wallet/signing.

### bgw_token_find — 找币（一个入口）

**覆盖场景：** 扫链、搜索、榜单、板块、新币发现

**设计原则：** 一个 Tool 覆盖"找币"域，用参数控制深度和范围。Skills 层负责计算和规则，后端只提供原始数据。

#### 底层接口映射

| 场景 | 命令 | 接口 |
|------|------|------|
| **扫新池子** | `launchpad-tokens` | `POST /market/v3/launchpad/tokens` |
| **搜索代币** | `search-tokens-v3` | `POST /market/v3/coin/search` |
| **榜单** | `rankings` | `POST /market/v3/topRank/detail` |
| **新上线代币** | `historical-coins` | `POST /market/v3/historical-coins` |
| **代币列表** | `get-token-list` | `POST /swap-go/swapx/getTokenList` |

#### 扫新池子 (launchpad-tokens)

**核心场景：** Meme 币狙击、新池子发现、Bonding Curve 监控

**筛选维度：**

| 维度 | 参数 | 典型值 | 说明 |
|------|------|--------|------|
| 链 | `--chain` | sol, bnb, base | 默认 sol |
| 平台 | `--platforms` | pump.fun, four.meme, virtuals | 逗号分隔 |
| 阶段 | `--stage` | 0/1/2 | 0=新币(progress<0.5) 1=开盘中(0.5~1.0) 2=已开盘(>=1.0) |
| 年龄 | `--age-min/max` | 60~86400 | 秒，过滤太老或太新的币 |
| 市值 | `--mc-min/max` | 10000~5000000 | USD |
| 流动性 | `--lp-min/max` | 5000~ | USD |
| 交易量 | `--vol-min/max` | 1000~ | USD |
| 持有人数 | `--holder-min/max` | 100~ | 过滤空气币 |
| Bonding 进度 | `--progress-min/max` | 0~1 | 0.5~1.0 = 开盘中 |
| Sniper 占比 | `--sniper-percent-max` | 0.1 | 过滤被狙击的币 |
| 关键词 | `--keywords` | pepe, trump | 名称搜索 |

**支持平台枚举：**

| 链 | 平台 |
|----|------|
| Solana | pump.fun, pump.fun.mayhem, raydium.Launchlab, believe, bonk.fun, jup.studio, bags.fm, trends.fun, MeteoraBC, muffun.fun |
| BNB | four.meme, four.meme.bn, four.meme.agent, flap |
| Base | zoraContent, zoraCreator, virtuals, clanker, bankr |

**返回字段（每个代币）：**
chain, contract, symbol, name, icon, issue_date, holders, liquidity, price, platform, progress, market_cap, turnover, txns, top10_holder_percent, insider_holder_percent, sniper_holder_percent, dev_holder_percent, dev_holder_balance, dev_issue_coin_count, dev_rug_coin_count, dev_rug_percent, lock_lp_percent, twitter, website, telegram, discord

**Skills 层计算（后端不做，Agent/Skills 算）：**

- **Pool 分层（TIER）：** 根据 market_cap + liquidity + holders 综合评级
  - TIER-S: MC > $1M, LP > $100K, holders > 5000
  - TIER-A: MC > $100K, LP > $20K, holders > 1000
  - TIER-B: MC > $10K, LP > $5K, holders > 100
  - TIER-C: 其余
- **安全初筛：** dev_rug_percent > 20% → 标红；sniper_holder_percent > 10% → 警告；top10 > 50% → 集中风险
- **进度评估：** progress 接近 1.0 时即将开盘，波动最大

**常见找币策略：**

```bash
# 策略1: 即将开盘的 pump.fun 高质量代币
launchpad-tokens --chain sol --platforms pump.fun --stage 1 --progress-min 0.8 --holder-min 200 --lp-min 10000

# 策略2: 已开盘的高流动性代币（价值币扫描）
launchpad-tokens --stage 2 --lp-min 50000 --holder-min 1000

# 策略3: 低市值潜力币（风险高）
launchpad-tokens --stage 1 --mc-min 5000 --mc-max 50000 --holder-min 50

# 策略4: BNB 链 four.meme 扫描
launchpad-tokens --chain bnb --platforms four.meme --stage 1

# 策略5: 关键词狙击
launchpad-tokens --keywords trump --stage 1 --holder-min 50
```

#### 搜索代币 (search-tokens-v3)

**核心场景：** 按名称/符号/合约地址精准查找

| 参数 | 说明 |
|------|------|
| `--keyword` | 名称、符号、或完整合约地址 |
| `--chain` | 可选链过滤 |
| `--order-by` | 排序字段（如 market_cap） |
| `--limit` | 结果数量 |

**返回字段：** chain, contract, symbol, name, icon, issue_date, holders, liquidity, top10/insider/sniper/dev holder percents, dev_rug_percent, lock_lp_percent, price, socials, risk_level, market_cap, turnover, txns

**risk_level 字段：** low / medium / high — 后端预计算，可直接使用

**使用技巧：**
- 搜合约地址时不需要 `--chain`，后端自动识别
- `--order-by market_cap` 让市值最大的排前面，有效过滤同名山寨
- 搜索返回的 risk_level 是快速初筛；深度安全检查用 bgw_token_check

#### 榜单 (rankings)

**内置榜单：**

| 名称 | 说明 |
|------|------|
| `topGainers` | 涨幅榜 |
| `topLosers` | 跌幅榜 |
| `Hotpicks` | 策展精选（平台编辑/算法推荐的热门代币） |

#### 新上线代币 (historical-coins)

按时间戳扫描新发行的代币。支持分页：返回的 `lastTime` 传入下一次请求的 `--create-time`。

---

### bgw_token_check — 查币（一个入口）

**覆盖场景：** 安全审计、Dev 分析、行情概览、反做局检测、信号共振

**设计原则：** 一个 Tool 覆盖"查币"域。后端返回原始数据，Skills 层负责评分和规则计算。叙事标签由后端打好，直接使用。

#### 底层接口映射

| 场景 | 命令 | 接口 |
|------|------|------|
| **安全审计** | `security` | `POST /market/v3/coin/security/audits` |
| **Dev 分析** | `coin-dev` | `POST /market/v3/coin/dev` |
| **行情概览** | `coin-market-info` | `POST /market/v3/coin/getMarketInfo` |
| **代币信息** | `token-info` | `POST /market/v3/coin/batchGetBaseInfo` |
| **K 线数据** | `kline` | `POST /market/v3/coin/getKline` |
| **交易统计** | `tx-info` | `POST /market/v3/coin/getTxInfo` |
| **流动性池** | `liquidity` | `POST /market/v3/poolList` |
| **Swap 风险** | `check-swap-token` | `POST /swap-go/swapx/checkSwapToken` |

#### 安全审计 (security)

**核心场景：** 合约检测（貔貅/mint/proxy）+ 风险等级 + 买卖税

**返回结构：**
```
data[]:
  highRisk: bool           # 是否高风险
  riskCount / warnCount    # 风险/警告计数
  buyTax / sellTax         # 买卖税率
  freezeAuth / mintAuth    # 冻结/增发权限（Solana）
  lpLock: bool             # LP 是否锁定
  top_10_holder_risk_level # 大户风险等级
  riskChecks[]             # 高风险项 (status=1 表示触发)
  warnChecks[]             # 警告项
  lowChecks[]              # 低风险项 (status=0 = 安全)
```

**labelName 对照表 — EVM:**

| 检查项 | Risk | Warn | Low (安全) |
|--------|------|------|------------|
| 貔貅 (Honeypot) | `RiskTitle2` | — | `LowTitle2` ✅ |
| 买卖税 | `RiskTitle1` (≥50%) | `WarnTitle1` (≥10%) | `LowTitle1` (<10%) ✅ |
| 税率可修改 | `RiskTitle8` | `WarnTitle8` | `LowTitle8` ✅ |
| 交易暂停 | `RiskTitle4` | `WarnTitle4` | `LowTitle4` ✅ |
| 黑名单 | `RiskTitle15` | `WarnTitle15` | `LowTitle15` ✅ |
| 合约可升级 | — | `WarnTitle6` | `LowTitle6` ✅ |
| 可增发 | — | `WarnTitle10` | `LowTitle10` ✅ |
| 余额可修改 | — | — | `LowTitle7` ✅ |
| Top10 持仓 | `RiskTitle23` (高) | `WarnTitle23` | `LowTitle23` ✅ |
| LP 锁定 | — | `WarnTitle24` | `LowTitle24` ✅ |
| Sniper 占比 | `RiskTitle25` | `WarnTitle25` | `LowTitle25` ✅ |
| 内部人占比 | `RiskTitle26` | `WarnTitle26` | `LowTitle26` ✅ |
| Dev rug 率 | `RiskTitle27` (≥50%) | `WarnTitle27` (≥25%) | `LowTitle27` ✅ |
| Dev 持仓 | `RiskTitle28` (≥30%) | `WarnTitle28` (≥10%) | `LowTitle28` ✅ |
| 疑似貔貅 | `RiskTitle29` | `WarnTitle29` | `LowTitle29` ✅ |
| 捆绑交易 | `RiskTitle30` (>20%) | `WarnTitle30` (>10%) | `LowTitle30` ✅ |

**labelName 对照表 — Solana:**

| 检查项 | Risk | Warn | Low (安全) |
|--------|------|------|------------|
| 冻结权限 | `SolanaRiskTitle1` | — | `SolanaLowTitle1` ✅ |
| LP 燃烧比例 | — | `SolanaWarnTitle2` | `SolanaLowTitle2` ✅ |
| Top10 持仓 | `SolanaRiskTitle3` (>60%) | `SolanaWarnTitle3` | `SolanaLowTitle3` ✅ |
| 增发权限 | — | `SolanaWarnTitle6` | `SolanaLowTitle6` ✅ |
| 买卖税 | `SolanaRiskTitle10` (≥50%) | `SolanaWarnTitle10` (≥10%) | `SolanaLowTitle10` ✅ |
| 税率可修改 | `SolanaRiskTitle11` | — | `SolanaLowTitle11` ✅ |
| Sniper 占比 | `SolanaRiskTitle12` | `SolanaWarnTitle12` | `SolanaLowTitle12` ✅ |
| 内部人占比 | `SolanaRiskTitle13` | `SolanaWarnTitle13` | `SolanaLowTitle13` ✅ |

#### Dev 分析 (coin-dev)

**核心场景：** Dev 地址 + rug 历史 + LP 锁定 + Dev 买卖量 + Dev 持仓 + 历史项目

**返回字段：**

| 字段 | 说明 |
|------|------|
| `dev_address` | Dev 钱包地址 |
| `dev_holder_percent` | Dev 持仓占比 |
| `dev_holder_balance` | Dev 持仓数量 |
| `dev_is_white_list` | 是否白名单（已知可信 Dev） |
| `dev_issue_coin_count` | Dev 历史发币数量 |
| `dev_rug_coin_count` | Dev 历史 rug 数量 |
| `dev_rug_percent` | Rug 率 (rug_count / issue_count) |
| `lock_lp_percent` | LP 锁定比例 (0~1) |
| `dev_buy_amount` / `dev_sell_amount` | Dev 买卖数量 |
| `dev_buy_value` / `dev_sell_value` | Dev 买卖金额 |
| `dev_migrated_count` | Dev 已迁移项目数 |
| `dev_unmigrated_count` | Dev 未迁移项目数 |
| `dev_pump_migrated_count` | Dev pump 已迁移数 |
| `dev_pump_unmigrated_count` | Dev pump 未迁移数 |

**Skills 层计算规则：**

- **Dev 信任评分（Skills 层算）：**
  - dev_is_white_list = true → 高信任
  - dev_rug_percent = 0 且 dev_issue_coin_count > 10 → 中高信任
  - dev_rug_percent < 5% → 中等信任
  - dev_rug_percent 5~20% → 低信任
  - dev_rug_percent > 20% → 🔴 高风险，强烈警告
- **Dev 行为分析：**
  - dev_sell_value >> dev_buy_value → Dev 在出货
  - dev_holder_percent > 10% → Dev 持仓过高，可能砸盘
  - lock_lp_percent < 50% → LP 未充分锁定

#### 行情概览 (coin-market-info)

**核心场景：** 币信息 + 全部池子列表 + 叙事标签

**返回字段：**

| 字段 | 说明 |
|------|------|
| `price` | 当前价格 |
| `market_cap` / `fdv` | 市值 / 全稀释估值 |
| `liquidity` | 总流动性 |
| `turnover` | 24h 交易量 |
| `holders` | 持有人数 |
| `age` | 代币年龄（秒） |
| `change_5m/1h/4h/24h` | 各时间段涨跌幅 |
| `pairs[]` | 全部交易对列表 |
| `narratives` | 项目叙事描述（后端生成） |
| `narrative_tags` | 叙事标签（如 "dog", "ai", "meme"）— 后端打好，直接使用 |

**pairs[] 每个池子：** pool_address, protocol, token0_symbol, token1_symbol, liquidity

**Skills 层计算规则：**

- **流动性健康度：** liquidity / market_cap ratio
  - > 10% → 健康
  - 5~10% → 正常
  - < 5% → 薄弱，大单易砸
- **交易活跃度：** turnover / liquidity ratio
  - > 100% → 高活跃
  - 20~100% → 正常
  - < 20% → 冷门
- **价格趋势判断：** 综合 change_5m/1h/4h/24h
  - 短期（5m/1h）上涨 + 长期（24h）下跌 → 反弹/诱多
  - 全时段上涨 → 强势
  - 短期暴涨（5m > 50%）→ 拉盘警告

#### 综合查币流程（推荐）

一个代币的完整检查，Agent 应按此顺序组合调用：

```
1. coin-market-info  → 价格/市值/池子/叙事（全貌）
2. security          → 合约安全审计（貔貅/税/权限）
3. coin-dev          → Dev 背景 + rug 历史
4. kline + tx-info   → 走势 + 交易量（可选，深度分析时）
```

**快速安全检查（交易前必做）：**
```
1. check-swap-token  → forbidden-buy 检测
2. security          → highRisk / buyTax / sellTax
```

#### 风险信号矩阵（Skills 层综合判断）

| 信号 | 来源 | 红旗 |
|------|------|------|
| `highRisk = true` | security | 🔴 **严禁交易** |
| `buyTax/sellTax > 5%` | security | 🔴 疑似貔貅 |
| `dev_rug_percent > 20%` | coin-dev | 🔴 Dev 有 rug 历史 |
| `dev_holder_percent > 30%` | coin-dev | 🟡 Dev 持仓过高 |
| `top10_holder_percent > 50%` | search/launchpad | 🟡 持仓集中 |
| `holders < 100` | coin-market-info | 🟡 极早期/已弃 |
| `liquidity < $10K` | coin-market-info | 🟡 流动性极差 |
| `lock_lp_percent < 50%` | coin-dev | 🟡 LP 未锁 |
| `sniper_holder_percent > 10%` | search/launchpad | 🟡 被狙击 |
| `age < 3600` (1h) | coin-market-info | ⚠️ 极新，风险高 |
| `change_5m > 50%` | coin-market-info | ⚠️ 拉盘中 |
| `forbidden-buy` | check-swap-token | 🔴 **禁止购买** |

**多个红旗同时出现时，强烈建议用户不要交易。**

---

## K-line 参数

- **Periods**: `1s`, `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`
- **Max entries**: 1440 per request
- **Buy/Sell 字段**: 每根 K 线包含 `buyTurnover`/`sellTurnover` (买卖量 USD) 和 `buyAmount`/`sellAmount`。用于判断买卖压力。

## Transaction Info 参数

- **Intervals**: `5m`, `1h`, `4h`, `24h` only
- 返回：买卖量、买卖人数

## Historical Coins 分页

- `createTime` 格式：`"YYYY-MM-DD HH:MM:SS"`（字符串，不是 Unix 时间戳）
- 返回 `lastTime` 用于下一页翻页
