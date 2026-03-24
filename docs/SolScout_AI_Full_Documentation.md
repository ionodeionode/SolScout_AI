# SolScout AI — Complete Project Documentation
## Multi-Agent Debate Trading on Solana
### Solana Agent Economy Hackathon: Agent Talent Show

---

## 1. Project Overview

SolScout AI is an autonomous memecoin trading agent on Solana that uses a Multi-Agent Debate System. Instead of one bot making all decisions, a council of 4 specialized AI agents debate each trade before executing. The system is built with Bitget Wallet Skill (BWS) for on-chain operations and an LLM (Large Language Model) for intelligence.

### Problem Statement
Most trading bots use simple if/else logic: "price up → buy, price down → sell." This leads to:
- FOMO buying at tops
- Getting rugged by unsafe tokens
- No consideration of multiple market perspectives
- Single point of failure in decision making

### Solution: AI Debate Council
SolScout deploys 4 specialized agents + 1 judge that debate every trade:
- **Analyst Agent** (📊): Technical analysis — price action, volume, momentum, RSI
- **Sentiment Agent** (📢): Social intelligence — narrative strength, community, hype quality
- **Guard Agent** (🛡️): Security & safety — rug detection, dev history, honeypot, tax
- **Whale Agent** (🐋): Smart money — holder distribution, buy/sell pressure
- **Judge** (⚖️): Final decision — synthesizes all votes with contrarian thinking

**Critical Rule**: If Guard says STRONG_SELL with >60% confidence → automatic VETO regardless of other agents. This prioritizes capital preservation over profit.

---

## 2. System Architecture

### Data Flow
```
Token Scanner (Rankings + Launchpad)
    ↓
Security Filter (Audit + Dev History)
    ↓
Multi-Agent Debate Council
(Analyst → Sentiment → Guard → Whale → Judge)
    ↓
├── Trading Engine (BWS Swap)
├── Narrator (X/Twitter Threads)
└── Web Dashboard (Real-Time UI)
```

### Technology Stack
- **Language**: Python 3.12
- **AI Brain**: LLM via OpenAI-compatible API (currently configured with Clawo/GPT-5.4)
- **On-chain**: Bitget Wallet Skill (Solana) — gasless swaps, market data, security audits
- **Data Sources**: BWS Market API (token info, kline, security, rankings, dev analysis)
- **Social Layer**: X/Twitter API v2 (tweepy) — auto-generated debate threads
- **Dashboard**: FastAPI (backend) + Vanilla JS single-page app (frontend)
- **Testing**: unittest with mocking (32 unit tests)

---

## 3. Project Structure

```
solscout-ai/
├── main.py                    # Entry point with 5 CLI commands
├── config/
│   ├── __init__.py
│   └── settings.py            # Configuration dataclasses + env loading
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   └── debate.py          # ⭐ Multi-Agent Debate Council (core innovation)
│   ├── data/
│   │   ├── __init__.py
│   │   ├── bws_client.py      # Bitget Wallet Skill Python wrapper
│   │   └── scanner.py         # Token discovery + security filtering
│   ├── strategy/
│   │   ├── __init__.py
│   │   └── trader.py          # Trading engine with full swap flow
│   ├── social/
│   │   ├── __init__.py
│   │   ├── narrator.py        # X thread generation via LLM
│   │   └── twitter.py         # X/Twitter API client
│   └── utils/
│       ├── __init__.py
│       └── llm.py             # LLM client (OpenAI-compatible)
├── dashboard/
│   ├── __init__.py
│   ├── index.html             # Real-time web dashboard (premium UI)
│   └── server.py              # FastAPI server + background trading loop
├── tests/
│   ├── __init__.py
│   ├── test_config.py         # 5 tests for configuration
│   ├── test_debate.py         # 7 tests for debate council
│   ├── test_scanner.py        # 8 tests for token scanner
│   └── test_trader.py         # 6 tests for trading engine
├── vendor/
│   └── bitget-wallet-skill/   # BWS SDK (cloned from GitHub)
├── .env                       # Environment configuration
├── .env.example               # Config template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 4. Module Details

### 4.1 Configuration (config/settings.py)

Uses Python dataclasses for type-safe configuration:

- **LLMConfig**: API key, base URL, model name, temperature, max tokens
- **WalletConfig**: Solana private key, wallet address, RPC URL
- **TradingConfig**: Position sizing (max 15%), stop loss (20%), take profit levels (25%/50%), min trade size (0.1 SOL), slippage (15%)
- **TwitterConfig**: API keys for X/Twitter posting with `is_configured` property
- **AppConfig**: Master config combining all sub-configs, loaded from environment via `from_env()` classmethod

Environment variables loaded via python-dotenv from .env file.

### 4.2 LLM Client (src/utils/llm.py)

OpenAI-compatible client that works with any provider:
- `chat()`: Standard text completion
- `chat_json()`: Structured JSON output with automatic parsing and error handling
- Handles parse errors gracefully by returning `{"raw": response, "parse_error": True}`
- Currently configured to use Clawo API (clawo/gpt-5.4 model)

### 4.3 BWS Client (src/data/bws_client.py)

Python wrapper around the Bitget Wallet Skill Node.js SDK:
- **Market Data**: `rankings()`, `market_info()`, `kline()`, `tx_info()`
- **Security**: `security_audit()`, `dev_analysis()`
- **Trading**: `get_quote()`, `confirm_trade()`, `make_order()`, `sign_transaction()`, `send_transaction()`
- **Wallet**: `get_balance()`, `get_holding()`
- **Launchpad**: `launchpad_list()` — pump.fun, trends.fun, raydium integration

All methods call the BWS SDK via subprocess and parse JSON responses.

### 4.4 Token Scanner (src/data/scanner.py)

Discovers and filters tokens from multiple sources:

**Discovery Sources**:
1. `scan_trending()` — Fetches from BWS rankings (topGainers, top1h, top24h, hotPicks)
2. `scan_launchpad()` — Fetches from pump.fun, trends.fun, raydium launched tokens

**Security Filtering** (`quick_filter()`):
- Minimum liquidity check (default: $5,000)
- Minimum holders check (default: 50)
- High-risk flag detection from security audit
- Sell tax threshold (>10% = reject)
- Dev rug history analysis (>50% rugged tokens = reject)
- Deduplication by contract address

**Data Model** — `TokenCandidate` dataclass:
- chain, contract, symbol, name, price, market_cap, liquidity, holders
- socials, security info, kline data, transaction data, dev info
- `has_socials` property for social presence check

### 4.5 Debate Council (src/agent/debate.py) — ⭐ Core Innovation

The Multi-Agent Debate System is the core differentiator:

**Signal Enum**: STRONG_BUY(2), BUY(1), HOLD(0), SELL(-1), STRONG_SELL(-2)

**Agent Voting Process**:
1. Each agent receives a tailored prompt with token data specific to their expertise
2. Agent returns structured JSON: `{signal, confidence, reasoning, key_data}`
3. Invalid responses default to HOLD with low confidence

**Agents**:
- **Analyst**: Analyzes price action, candlestick patterns, volume trends, momentum indicators
- **Sentiment**: Evaluates social media presence, community size, narrative quality, hype sustainability
- **Guard**: Checks contract security, dev track record, honeypot risks, tax mechanisms, mint/freeze authority
- **Whale**: Examines holder distribution, top wallet concentration, buy/sell ratio across timeframes

**Judge Deliberation**:
- Receives all 4 votes with reasoning
- Must synthesize a final decision considering consensus AND contrarian viewpoints
- Returns: `{final_signal, consensus_score, reasoning, should_trade, recommended_size_pct, contrarian_note}`

**Guard Veto Rule**:
If Guard votes STRONG_SELL with confidence > 60%, the Judge's decision is overridden:
- Final signal forced to STRONG_SELL
- `should_trade` set to False
- Reasoning updated with veto explanation

**Output**: `DebateResult` dataclass containing all votes, final signal, consensus score, judge reasoning, and trade recommendation.

### 4.6 Trading Engine (src/strategy/trader.py)

Manages the full trading lifecycle:

**Position Sizing** (`calculate_position_size()`):

The agent automatically checks your SOL balance and calculates the optimal trade size:

```
Trade Size = SOL_Balance × (max_position_pct / 100) × signal_multiplier
```

| Signal | Multiplier | Example (1 SOL balance, 15% max) |
|--------|------------|----------------------------------|
| STRONG_BUY | × 100% | 1 × 15% × 1.0 = **0.15 SOL** (~$22) |
| BUY | × 70% | 1 × 15% × 0.7 = **0.105 SOL** (~$16) |
| HOLD | × 0% | **No trade** |
| SELL | × 0% | **No trade** |

**Fee-Aware Minimum**: Trades below `MIN_TRADE_SOL` (default: 0.1 SOL) are automatically skipped to prevent micro trades where fees eat all profit.

> **Why 0.1 SOL minimum?** On Solana DEX, a typical swap costs ~0.001 SOL in fees + slippage. For a 0.01 SOL trade, that's 10% lost to fees before any price movement. With 0.1 SOL minimum, fees are only ~1%.

**Swap Execution Flow** (5-step BWS process):
1. `get_quote()` — Get swap quote for token pair
2. `confirm_trade()` — Confirm the trade parameters
3. `make_order()` — Create the order
4. `sign_transaction()` — Sign with wallet private key
5. `send_transaction()` — Submit to Solana network

**Portfolio Management (Auto TP/SL)**:
- Tracks all open positions with entry price, amount, timestamps
- **Take Profit 1 (TP1)**: +25% → sell 50% of position (lock profits)
- **Take Profit 2 (TP2)**: +50% → sell remaining position (maximize gains)
- **Stop Loss (SL)**: -20% → sell entire position (protect capital)
- `check_positions()` — Periodic check for TP/SL triggers

**Example Trade Lifecycle** (wallet balance: 1 SOL):
```
1. Council votes STRONG_BUY on $MEME → Trade size: 0.15 SOL
2. Swap: 0.15 SOL → 150,000 $MEME via Jupiter
3. Price rises +25% → TP1: sell 75,000 $MEME → receive 0.09375 SOL
4. Price rises +50% → TP2: sell 75,000 $MEME → receive 0.1125 SOL
5. Total received: 0.20625 SOL from 0.15 SOL spent = +37.5% profit
```

**Dry Run Mode**: When no wallet is configured, simulates trades with logging.

### 4.7 Narrator (src/social/narrator.py)

Generates engaging X/Twitter content from debate results:

- Takes a `DebateResult` and generates a 4-5 tweet thread
- Uses LLM to create human-like, witty crypto commentary
- Includes: headline, individual agent analysis, contrarian take, final lesson
- Hashtags: #AgentTalentShow @BitgetWallet
- Respects 280-character tweet limit with smart truncation

### 4.8 Twitter Client (src/social/twitter.py)

Handles X/Twitter API integration:
- `post_tweet()` — Single tweet posting
- `post_thread()` — Chain of reply tweets
- `post_debate_result()` — Specialized method for debate narration
- **Console fallback**: If Twitter not configured, logs to console instead
- Uses tweepy for OAuth1.0a authentication

### 4.9 Main Entry Point (main.py)

CLI interface with 5 commands:

1. **`python main.py scan`** — Discover and display trending tokens from rankings + launchpad
2. **`python main.py debate <contract>`** — Run full debate council on a specific token by contract address
3. **`python main.py demo`** — End-to-end demo: scan → filter → debate → narrate (no real trades)
4. **`python main.py run`** — Full autonomous trading loop with live trading
5. **`python main.py dashboard`** — Launch real-time web dashboard on http://localhost:8888

### 4.10 Dashboard Server (dashboard/server.py)

FastAPI application with:

**API Endpoints**:
- `GET /` — Serves the HTML dashboard
- `GET /api/state` — Full application state (status, stats, debates, trades, tokens)
- `GET /api/debates` — Recent debate results
- `GET /api/trades` — Trade history
- `GET /api/wallet/{address}` — 🆕 Public wallet tracker (SOL balance, token holdings, recent TXs)
- `POST /api/scan` — Trigger manual scan

**Background Trading Loop** (`run_trading_loop()`):
- Runs in a daemon thread
- Cycle: scan → filter → enrich → debate each candidate → trade if approved → narrate → manage positions → sleep
- Updates shared state dict for dashboard polling
- Tracks: cycle count, tokens scanned, rugs avoided, total debates, trade stats

### 4.11 Dashboard UI (dashboard/index.html)

Premium single-page web application with **two tabs**:

**Visual Features**:
- Dark theme with animated gradient orbs background
- Grid overlay pattern
- Glassmorphism header with frosted blur
- JetBrains Mono monospace font for data
- Inter font for UI text
- Gradient accent colors (green, cyan, purple, yellow, red)
- Smooth micro-animations on hover and load

**Tab 1: 🤖 Agent Live** — Real-time trading agent monitor:
1. **Stats Grid** — 6 cards: Total PnL, Win Rate, Debates, Tokens Scanned, Rugs Avoided, Open Positions
2. **Live Activity Log** — Real-time event stream with color-coded types (SCAN, DEBATE, TRADE, GUARD)
3. **Recent Debates** — Detailed debate cards with agent vote bars, signal badges, judge reasoning
4. **Trade History** — All buy/sell/TP/SL actions with PnL percentage
5. **Scanned Tokens Grid** — Token cards with symbol, MCap, and liquidity

**Tab 2: 🔍 Wallet Tracker** — Public on-chain wallet lookup:
- Enter any Solana wallet address (no private key needed)
- Displays: SOL balance, token holdings (with amounts), last 10 transactions
- Data fetched directly from Solana mainnet-beta RPC
- Useful for users to monitor their agent's wallet activity

**Real-time Updates**: Polls `/api/state` every 5 seconds, detects state changes and populates activity log.

---

## 5. Trading Strategy

### Entry Conditions
- Debate council consensus: BUY or STRONG_BUY
- Overall confidence > 60%
- Security screening: PASS (no Guard veto)
- Trade size ≥ MIN_TRADE_SOL (0.1 SOL)
- Minimum liquidity and holder requirements met

### Position Management

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_POSITION_PCT` | **15%** | Max % of SOL balance per trade |
| `TAKE_PROFIT_1` | **25%** | TP1: sell 50% at +25% gain |
| `TAKE_PROFIT_2` | **50%** | TP2: sell remaining at +50% gain |
| `STOP_LOSS` | **20%** | SL: exit entire position at -20% |
| `MIN_TRADE_SOL` | **0.1** | Min trade size in SOL (fee protection) |
| `SLIPPAGE_PCT` | **15%** | Slippage tolerance for memecoin swaps |
| `MIN_LIQUIDITY_USD` | **$5,000** | Min liquidity pool to consider a token |
| `MIN_HOLDERS` | **50** | Min unique holders |
| `SCAN_INTERVAL_SECONDS` | **120** | Seconds between scan cycles |

### Recommended Wallet Sizes

| SOL Balance | Max Trade Size | Suitable? |
|-------------|---------------|----------|
| 0.5 SOL | 0.075 SOL (~$11) | ⚠️ Marginal (close to min) |
| 1 SOL | 0.15 SOL (~$22) | ✅ Minimum recommended |
| 5 SOL | 0.75 SOL (~$112) | ✅ Good |
| 10 SOL | 1.5 SOL (~$225) | ✅ Optimal |

> **Note**: SOL prices estimated at ~$150. Actual USD values will vary.

### Fee Analysis

| Trade Size | Swap Fee (~0.3%) | Network Fee | Slippage (~2%) | Total Fee % |
|------------|-----------------|-------------|----------------|-------------|
| 0.01 SOL | 0.00003 | 0.0005 | 0.0002 | **~7%** ❌ |
| 0.05 SOL | 0.00015 | 0.0005 | 0.001 | **~3.3%** ⚠️ |
| 0.1 SOL | 0.0003 | 0.0005 | 0.002 | **~2.8%** ✅ |
| 0.5 SOL | 0.0015 | 0.0005 | 0.01 | **~2.4%** ✅ |
| 1.0 SOL | 0.003 | 0.0005 | 0.02 | **~2.4%** ✅ |

> Trades below 0.1 SOL are automatically skipped by the `MIN_TRADE_SOL` setting.

### Risk Controls
- Guard Agent veto power (absolute override)
- Dev rug history check (>50% rugged = reject)
- Honeypot/tax detection
- Fee-aware minimum trade size
- Maximum position size cap
- Dry run mode for testing

---

## 6. Demo Results (Live Test on March 25, 2026)

### Scan Results
- **Sources**: topGainers (48 tokens), Hotpicks (15), Launchpad (5) → 8 unique candidates
- **Security Filter**: 4 passed, 1 rejected ($TOGETHER — dev rugged 24/30 previous tokens)

### Debate Results

**$dapang** — Final: SELL (82% consensus, No Trade)
- 📊 Analyst: SELL 82% — "Post-spike fatigue, momentum soggy"
- 📢 Sentiment: SELL 84% — "No Twitter, no website, anonymous team"
- 🛡️ Guard: HOLD 62% — "No hard red flags but not strong"
- 🐋 Whale: SELL 79% — "Selling pressure dominating across all windows"
- ⚖️ Judge: "Price action weak after failed rebound, sell flow dominates"

**$词元** — Final: STRONG_SELL (39% consensus, No Trade)
- Guard triggered STRONG_SELL (96% confidence) → **GUARD VETO activated**
- Other agents were HOLD but Guard overrode due to high-risk signals

**$TESSA** — Final: HOLD (74% consensus, No Trade)
- 📊 Analyst: HOLD 59% — Neutral outlook
- 📢 Sentiment: SELL 83% — Weak social presence
- 🛡️ Guard: HOLD 58% — No major risks
- 🐋 Whale: HOLD 42% — Indecisive whale activity
- ⚖️ Judge: "3 of 4 agents HOLD, lone SELL driven by weak social proof rather than hard on-chain danger"

### Narration Output (Auto-generated X Thread)
5-tweet thread for $dapang debate:
1. Headline with verdict and key metrics
2. Analyst deep dive on price action
3. Whale + Sentiment + Guard summary
4. Contrarian case analysis
5. Final lesson ("no trade is a trade")

---

## 7. Key Design Decisions

### Why Multi-Agent Debate?
Single-model trading bots have blind spots. By forcing multiple specialized perspectives to "argue," we:
1. Reduce single-point-of-failure decisions
2. Surface risks that one perspective might miss
3. Generate richer reasoning for narration
4. Create more entertaining social content

### Why Guard Veto?
In defi/memecoin trading, a single catastrophic loss (rug pull) can wipe out many small wins. The Guard's absolute veto power ensures capital preservation takes priority over potential profit. This is the most important safety mechanism.

### Why Narration?
The social layer serves dual purposes:
1. **Transparency**: Users can follow the agent's reasoning in real-time on X
2. **Entertainment**: The debate format creates engaging content naturally
3. **Accountability**: Public decisions create a verifiable track record

### Why BWS (Bitget Wallet Skill)?
- Provides gasless swaps on Solana
- Built-in security auditing (contract analysis, rug detection)
- Developer analysis (track record of token deployers)
- Comprehensive market data API (rankings, klines, tx info)
- Launchpad integration (pump.fun, trends.fun, raydium)

---

## 8. Configuration

### Environment Variables (.env)

```env
# LLM Configuration
QWEN_API_KEY=your_api_key_here
QWEN_BASE_URL=https://api.clawo.xyz/v1
QWEN_MODEL=clawo/gpt-5.4

# Solana Wallet (for live trading)
SOLANA_PRIVATE_KEY=your_private_key
SOLANA_WALLET_ADDRESS=your_wallet_address

# Trading Parameters
# ──────────────────────────────────────────
# MAX_POSITION_PCT: Max % of SOL balance per trade
#   With 1 SOL → max trade = 0.15 SOL (~$22)
#   With 10 SOL → max trade = 1.5 SOL (~$225)
MAX_POSITION_PCT=15

# Take Profit: Auto-sell when price increases
TAKE_PROFIT_1=25         # +25% → sell 50% of position
TAKE_PROFIT_2=50         # +50% → sell remaining 50%

# Stop Loss: Auto-exit when price drops
STOP_LOSS=20             # -20% → sell 100% immediately

# Min trade size in SOL (prevents fee-eaten micro trades)
MIN_TRADE_SOL=0.1

# Slippage tolerance for memecoin swaps
SLIPPAGE_PCT=15

# Token discovery filters
MIN_LIQUIDITY_USD=5000   # Min liquidity pool ($)
MIN_HOLDERS=50           # Min unique holders
SCAN_INTERVAL_SECONDS=120

# X/Twitter (optional — for auto-narration)
X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_SECRET=
```

### Dependencies (requirements.txt)
- requests>=2.31.0
- openai>=1.12.0
- httpx>=0.27.0
- aiohttp>=3.9.0
- python-dotenv>=1.0.0
- pydantic>=2.5.0
- tweepy>=4.14.0
- fastapi>=0.109.0
- uvicorn>=0.27.0

---

## 9. Testing

32 unit tests across 4 test files, all passing:

### test_config.py (5 tests)
- Default values for all config classes
- Environment variable loading
- `is_configured` property for TwitterConfig
- AppConfig.from_env() integration

### test_debate.py (7 tests)
- Signal enum values
- DebateResult summary generation
- Vote parsing success/failure
- Invalid signal handling
- Judge deliberation (buy scenario, parse error fallback)
- Full debate flow with mocked LLM

### test_scanner.py (8 tests)
- Quick filter pass/fail cases
- Low liquidity rejection
- High risk token rejection
- High sell tax rejection
- Dev rug history detection
- Token deduplication
- Trending scan with mocked API
- Enrichment field updates

### test_trader.py (6 tests)
- Position sizing for BUY/STRONG_BUY/HOLD signals
- Position size cap enforcement
- Zero balance handling
- Initial stats verification
- Empty position check

Run tests: `python -m unittest discover tests -v`

---

## 10. Deployment Options

### Local Development
```bash
python main.py demo      # Test without trading
python main.py dashboard # Full dashboard + loop
```

### Production (24/7)
- **Railway**: Deploy with Procfile (`web: python main.py dashboard`)
- **Render**: Docker-based deployment
- **VPS**: Run with systemd service or tmux/screen

### Going Live Checklist
1. ✅ Code complete and tested
2. ⬜ Create Solana wallet and fund with SOL
3. ⬜ Add private key to .env
4. ⬜ (Optional) Configure X/Twitter API keys
5. ⬜ Deploy to cloud service
6. ⬜ Monitor dashboard for first live trades

---

## 11. Hackathon Submission Details

- **Hackathon**: Solana Agent Economy Hackathon
- **Track**: Agent Talent Show
- **Required Integration**: Bitget Wallet Skill ✅
- **Blockchain**: Solana ✅
- **Innovation**: Multi-Agent Debate architecture for trading decisions
- **Social Layer**: Auto-narrated X threads from debate results
- **Safety**: Guard Agent veto system for capital preservation
- **Dashboard**: Real-time premium web UI for monitoring

---

## 12. Future Improvements

1. **More agents**: Add a Technical Indicators agent (RSI, MACD, Bollinger Bands)
2. **Memory**: Persistent storage for position history and agent learning
3. **Backtesting**: Historical data replay to validate debate effectiveness
4. **Multi-chain**: Extend to Ethereum, Base, BSC via BWS
5. **Webhook alerts**: Telegram/Discord notifications for trades
6. **Agent personality tuning**: Adjust agent risk tolerance dynamically
7. **Portfolio rebalancing**: Auto-adjust positions based on market conditions
