# 🧠 SolScout AI — Multi-Agent Debate Trading on Solana

> **Solana Agent Economy Hackathon: Agent Talent Show**  
> Built with [Bitget Wallet Skill](https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill) + LLM

## What is SolScout AI?

SolScout AI is an **autonomous memecoin trading agent** that uses a **Multi-Agent Debate System** — instead of one bot making all decisions, a council of specialized AI agents debate each trade before executing.

### 🎯 The Problem
Most trading bots use simple if/else logic: "price up → buy, price down → sell." This leads to:
- FOMO buying at tops
- Getting rugged by unsafe tokens  
- No consideration of multiple market perspectives

### 💡 The Solution: AI Debate Council
SolScout deploys **4 specialized agents + 1 judge**:

| Agent | Role | Analyzes |
|---|---|---|
| 📊 **Analyst** | Technical Analysis | Price action, volume, momentum, RSI |
| 📢 **Sentiment** | Social Intelligence | Narrative strength, community, hype quality |
| 🛡️ **Guard** | Security & Safety | Rug detection, dev history, honeypot, tax |
| 🐋 **Whale** | Smart Money | Holder distribution, buy/sell pressure |
| ⚖️ **Judge** | Final Decision | Synthesizes all votes with contrarian thinking |

**Key rule:** If Guard says STRONG_SELL with >60% confidence → **automatic VETO** regardless of other agents.

## Features

- 🔍 **Token Discovery** — Scans Solana rankings + launchpad (pump.fun, trends.fun, raydium)
- 🛡️ **Security Screening** — Contract audit, dev rug history, honeypot detection
- 🧠 **Multi-Agent Debate** — 4 agents analyze independently, judge synthesizes
- ⚡ **Smart Cache LLM Optimization** — Persistent token-memory state prevents re-analyzing static trending tokens (99% reduction in redundant API credit burn).
- 💹 **Autonomous Trading** — Full swap via Bitget Wallet Skill (gasless)
- 📢 **Social Narration** — Auto-generates engaging X threads about debates
- 📊 **Portfolio Management** — TP/SL tracking, position sizing
- 🌐 **Real-Time Dashboard** — Live web UI with debate visualization, trade history, activity log

## Quick Start

```bash
# 1. Clone
git clone https://github.com/ionodeionode/solscout-ai.git
cd solscout-ai

# 2. Install
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with your LLM API key

# 4. Run
python main.py scan              # Discover trending tokens
python main.py debate <address>  # Run debate on a token
python main.py demo              # Full demo (no real trading)
python main.py run               # Autonomous trading loop
python main.py dashboard         # Web dashboard + trading loop
```

## Commands

| Command | Description |
|---|---|
| `python main.py scan` | Scan & display trending tokens from rankings + launchpad |
| `python main.py debate <contract>` | Run full debate council on a specific token |
| `python main.py demo` | End-to-end demo: scan → filter → debate → narrate (no real trades) |
| `python main.py run` | Full autonomous loop with live trading |
| `python main.py dashboard` | Launch real-time web dashboard on `http://localhost:8888` |
| `python main.py dashboard --port 9000` | Launch dashboard on custom port |

## Architecture

```
                    ┌──────────────────┐
                    │   Token Scanner  │
                    │  Rankings + LP   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Security Filter │
                    │  Audit + DevHist │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │    Multi-Agent Debate Council │
              │                              │
              │  📊 Analyst    📢 Sentiment  │
              │  🛡️ Guard      🐋 Whale      │
              │         ⚖️ Judge             │
              └──────────────┬──────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                   │
 ┌────────▼─────────┐ ┌─────▼──────┐  ┌────────▼─────────┐
 │  Trading Engine  │ │  Narrator  │  │  Web Dashboard   │
 │  BWS Swap Flow   │ │  X Threads │  │  Real-Time UI    │
 └──────────────────┘ └────────────┘  └──────────────────┘
```

## Project Structure

```
solscout-ai/
├── main.py                    # Entry point (5 commands)
├── config/
│   └── settings.py            # Config dataclasses + env loading
├── src/
│   ├── agent/
│   │   └── debate.py          # ⭐ Multi-Agent Debate Council
│   ├── data/
│   │   ├── bws_client.py      # Bitget Wallet Skill wrapper
│   │   └── scanner.py         # Token discovery + filtering
│   ├── strategy/
│   │   └── trader.py          # Trading engine (full swap flow)
│   ├── social/
│   │   ├── narrator.py        # X thread generation
│   │   └── twitter.py         # X/Twitter API client
│   └── utils/
│       └── llm.py             # LLM client (OpenAI-compatible)
├── dashboard/
│   ├── index.html             # Real-time web dashboard
│   └── server.py              # FastAPI + background trading loop
├── tests/
│   ├── test_config.py
│   ├── test_debate.py
│   ├── test_scanner.py
│   └── test_trader.py
├── vendor/
│   └── bitget-wallet-skill/   # BWS SDK (cloned from GitHub)
├── .env.example               # Config template
├── .gitignore
├── requirements.txt
└── README.md
```

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12 |
| AI Brain | LLM via OpenAI-compatible API |
| On-chain | Bitget Wallet Skill (Solana) |
| Data | BWS Market API (token info, kline, security, rankings) |
| Social | X/Twitter API v2 (tweepy) |
| Dashboard | FastAPI + Vanilla JS (single-file UI) |

## Trading Strategy

- **Entry:** Debate council consensus BUY + confidence > 60% + security PASS
- **Take Profit 1:** +25% → sell 50% (lock profits)
- **Take Profit 2:** +50% → sell remaining
- **Stop Loss:** -20% → sell all
- **Position Size:** Max 15% portfolio per trade

## Running Tests

```bash
cd solscout-ai
python -m pytest tests/ -v
# or
python -m unittest discover tests -v
```

## Dashboard

The real-time dashboard at `http://localhost:8888` shows:
- **Stats**: PnL, win rate, debates count, rugs avoided
- **Live Activity Log**: Real-time event stream
- **Debate Visualization**: Agent votes with confidence bars
- **Trade History**: All buy/sell actions with PnL
- **Token Scanner**: Latest discovered tokens

## Hackathon Submission

**Solana Agent Economy Hackathon: Agent Talent Show**
- 🏷️ Tracks: Bitget Wallet · Solana
- 🔧 Built with: `bitget-wallet-skill` + LLM
- 🎭 Talent: Multi-Agent Debate narrated live on X

## License

MIT
