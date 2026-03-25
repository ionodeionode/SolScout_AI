# SolScout Platform Context

## Core Application Structure
- **Execution Script**: `main.py`
  - Command: `python main.py run` initiates the autonomous trading sequence based on the `SCAN_INTERVAL_SECONDS` environment variable.
  - Command: `python main.py dashboard` spins up a port `8888` FastAPI server for visual telemetry.
- **Config**: `.env` specifies variables like `MAX_OPEN_POSITIONS`, which limits API credit bleeding and caps active market risk.
- **Data Layers**:
  - `data/positions.json`: A static snapshot tracking ongoing positions (the dictionary key is the token's contract address). Holds values like `entry_price` and `amount`.
  - `data/state.json`: Appends concluded trades into a `trades` array. This array often needs cleanup if the blockchain returns a transaction validation error that went unhandled by `trader.py`.
 
## The Trading Heuristic (LLM Intelligence Engine)
The Bot processes tokens sequentially:
1. Bitget Wallet Skill fetches Launchpad/Trending tokens (`src/data/scanner.py`). Repeated scans use `seen_tokens` cache filtering.
2. The `src/agent/debate.py` instantiates 4 distinct agents.
3. If Guard rejects (>60% Confidence `STRONG_SELL`), the trade is vetoed instantly. Else, the Judge processes all sub-votes and returns a final position action.
4. `src/strategy/trader.py` checks target conditions ($25\%/\$50\%$ PnL Take Profit vs $20\%$ Stop Loss) to conclude ongoing positions algorithmically.
