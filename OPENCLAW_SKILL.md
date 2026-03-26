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

## Installation
Two options:

**Option 1 — Auto (recommended, 1 command):**
```bash
curl -sSL https://raw.githubusercontent.com/ionodeionode/SolScout_AI/main/setup_vps.sh | bash
```
Then: edit `~/solscout-ai/.env` → `sudo systemctl start solscout` → dashboard at http://<vps-ip>:8888
*(Note: Auto-setup configures a 07:00 AM daily cronjob to restart the service and clear AI memory caches for fresh re-entry evaluations).*

**Option 2 — Manual:** clone repo → `pip install -r requirements.txt` → clone BWS SDK → copy `.env.example` to `.env` → fill keys → `python main.py demo` to test first.

Required `.env` keys: `QWEN_API_KEY`, `SOLANA_PRIVATE_KEY`, `SOLANA_WALLET_ADDRESS`

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
- **Missing second legs (no re-entry)?** → Wait for the default 7:00 AM Cronjob to flush cache, or manually clear cache via `systemctl restart solscout`.

## Trading Logic
- Entry: consensus BUY + confidence > 60% + security PASS
- TP1: +25% → sell 50%
- TP2: +50% → sell 100%
- SL: -20% → sell 100%
- Guard VETO: if STRONG_SELL > 60% confidence → auto reject regardless of other agents

## Wallet Tracker
When user asks about wallet balance, token holdings, PnL of a specific wallet, or "wallet tracker":
- API: `GET https://solscout-ai.xyz/api/wallet/<SOLANA_ADDRESS>`
- Returns: `sol_balance`, token list with `entry_price`/`current_price`/`pnl_pct`, `recent_transactions`, `sol_price_usd`
- Display as Markdown table: Token | Amount | Current Price | Value (SOL) | Entry | PnL%
- If no address provided → ask user for Solana wallet address

## Tone
Crypto-native, enthusiastic. Celebrate "Rugs Avoided" and "Take Profits" actively.
