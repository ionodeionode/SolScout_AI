---
name: solscout-ai
description: >
  Monitor, manage, and troubleshoot the SolScout AI autonomous Solana memecoin trading bot.
  Use when user asks about: SolScout bot status, PnL report, active positions, trade history,
  win rate, rugs avoided, bot errors, restart bot, clean stuck state, dashboard, debate results,
  or anything related to the SolScout multi-agent trading system on Solana.
---

# SolScout AI Manager

## Project Structure
- Entry: `main.py` — commands: `scan`, `debate <address>`, `demo`, `run`, `dashboard`
- Data: `data/positions.json` (active trades), `data/state.json` (history + UI state)
- Config: `.env` (LLM API key, SOLANA_PRIVATE_KEY, MAX_OPEN_POSITIONS)
- Dashboard: http://localhost:8888

## PnL Report
Read `data/positions.json` → list holdings with entry_price, current_price, pnl_pct.
Read `data/state.json` → summarize TP/SL in last 24h.
Output as Markdown table. If positions.json empty → "0 Active Positions" (never hallucinate).

## Troubleshooting
- **JSON decode error** on positions.json → hung process or malformed file
- **DRY RUN mode** → SOLANA_PRIVATE_KEY not set in .env
- **Bot stops buying** → MAX_OPEN_POSITIONS reached, check count in positions.json
- **Stuck token** → run `python clean_state.py` or remove block from state.json manually
- **After any fix** → must restart: `python main.py run` or `systemctl restart solscout`

## Trading Logic
- Entry: consensus BUY + confidence > 60% + security PASS
- TP1: +25% → sell 50%
- TP2: +50% → sell 100%
- SL: -20% → sell 100%
- Guard VETO: if STRONG_SELL > 60% confidence → auto reject regardless of other agents

## Tone
Crypto-native, enthusiastic. Celebrate "Rugs Avoided" and "Take Profits" actively.
