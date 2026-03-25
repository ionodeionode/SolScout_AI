"""SolScout AI — Dashboard API Server

FastAPI server providing real-time trading data + serving the dashboard UI.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import AppConfig
from src.utils.llm import QwenLLM
from src.data.bws_client import BitgetWalletSkill
from src.data.scanner import TokenScanner, TokenCandidate
from src.agent.debate import DebateCouncil, DebateResult, Signal
from src.strategy.trader import TradingEngine
from src.social.narrator import NarratorAgent
from src.social.twitter import TwitterClient

logger = logging.getLogger("solscout.dashboard")

# ── State Persistence ─────────────────────────────────────────
STATE_FILE = Path(__file__).parent.parent / "data" / "state.json"

def _load_state() -> dict:
    """Load state from disk, fallback to defaults."""
    default = {
        "debates": [],
        "trades": [],
        "scanned_tokens": [],
        "stats": {
            "total_trades": 0, "open_positions": 0,
            "wins": 0, "losses": 0, "win_rate": 0,
            "total_pnl_sol": 0, "total_debates": 0,
            "rugs_avoided": 0, "tokens_scanned": 0,
        },
        "status": "idle",
        "last_updated": "",
        "cycle_count": 0,
    }
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Merge saved into defaults (keep new keys)
            for k in default:
                if k in saved:
                    default[k] = saved[k]
            logger.info(f"Loaded state: {len(default['trades'])} trades, {default['stats']['total_debates']} debates")
            return default
    except Exception as e:
        logger.warning(f"Failed to load state: {e}")
    return default

def save_state():
    """Save state to disk."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(app_state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save state: {e}")

# ── App State ─────────────────────────────────────────────────
app_state = _load_state()

# Global trader reference (set by trading loop)
trader: TradingEngine | None = None

# ── FastAPI App ───────────────────────────────────────────────
app = FastAPI(title="SolScout AI Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
DASHBOARD_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_path = DASHBOARD_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/state")
async def get_state():
    return JSONResponse(content=app_state)


@app.get("/api/debates")
async def get_debates():
    return JSONResponse(content={"debates": app_state["debates"][-20:]})


@app.get("/api/trades")
async def get_trades():
    return JSONResponse(content={"trades": app_state["trades"][-50:]})


@app.get("/api/stats")
async def get_stats():
    return JSONResponse(content=app_state["stats"])


@app.post("/api/scan")
async def trigger_scan():
    """Manually trigger a scan cycle."""
    app_state["status"] = "scanning"
    # The background loop will pick this up
    return {"status": "scan_triggered"}


# ── Wallet Tracker API ────────────────────────────────────────

SOLANA_RPC = "https://api.mainnet-beta.solana.com"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


async def _fetch_token_metadata(client, mints: list[str]) -> dict:
    """Fetch token name/symbol from Jupiter strict token list."""
    meta = {}
    try:
        resp = await client.get(
            "https://token.jup.ag/strict",
            timeout=10.0,
        )
        if resp.status_code == 200:
            for item in resp.json():
                addr = item.get("address", "")
                if addr in mints:
                    meta[addr] = {
                        "symbol": item.get("symbol", "???"),
                        "name": item.get("name", "Unknown Token"),
                        "logoURI": item.get("logoURI", ""),
                    }
    except Exception as e:
        logger.warning(f"Jupiter metadata fetch failed: {e}")

    # Fallback: try Jupiter all list for mints not found in strict
    missing = [m for m in mints if m not in meta]
    if missing:
        try:
            resp = await client.get(
                "https://token.jup.ag/all",
                timeout=10.0,
            )
            if resp.status_code == 200:
                for item in resp.json():
                    addr = item.get("address", "")
                    if addr in missing:
                        meta[addr] = {
                            "symbol": item.get("symbol", "???"),
                            "name": item.get("name", "Unknown Token"),
                            "logoURI": item.get("logoURI", ""),
                        }
        except Exception as e:
            logger.warning(f"Jupiter all-list fetch failed: {e}")
    return meta


async def _fetch_token_prices(client, mints: list[str]) -> dict:
    """Fetch current USD prices from Jupiter Price API v2."""
    prices = {}
    try:
        ids_param = ",".join(mints[:20])  # Limit to 20
        resp = await client.get(
            f"https://api.jup.ag/price/v2?ids={ids_param}",
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            for mint, info in data.items():
                price = info.get("price")
                if price is not None:
                    prices[mint] = float(price)
    except Exception as e:
        logger.warning(f"Jupiter price fetch failed: {e}")
    return prices


@app.get("/api/wallet/{address}")
async def get_wallet_info(address: str):
    """Query on-chain wallet data: SOL balance + token holdings + metadata."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # 1. Get SOL balance
            sol_resp = await client.post(SOLANA_RPC, json={
                "jsonrpc": "2.0", "id": 1,
                "method": "getBalance",
                "params": [address]
            })
            sol_data = sol_resp.json()
            sol_balance = sol_data.get("result", {}).get("value", 0) / 1e9

            # 2. Get token accounts
            token_resp = await client.post(SOLANA_RPC, json={
                "jsonrpc": "2.0", "id": 2,
                "method": "getTokenAccountsByOwner",
                "params": [
                    address,
                    {"programId": TOKEN_PROGRAM_ID},
                    {"encoding": "jsonParsed"}
                ]
            })
            token_data = token_resp.json()

            raw_tokens = []
            accounts = token_data.get("result", {}).get("value", [])
            for acct in accounts:
                info = acct.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                token_amount = info.get("tokenAmount", {})
                amount = float(token_amount.get("uiAmountString", "0"))
                if amount > 0:
                    raw_tokens.append({
                        "mint": info.get("mint", ""),
                        "amount": amount,
                        "decimals": token_amount.get("decimals", 0),
                    })

            raw_tokens.sort(key=lambda t: t["amount"], reverse=True)
            raw_tokens = raw_tokens[:20]

            # 3. Fetch token metadata + prices in parallel
            mints = [t["mint"] for t in raw_tokens]
            metadata = await _fetch_token_metadata(client, mints)
            prices = await _fetch_token_prices(client, mints)

            # 4. Enrich tokens
            tokens = []
            for t in raw_tokens:
                mint = t["mint"]
                meta = metadata.get(mint, {})
                current_price = prices.get(mint)
                current_value = (current_price * t["amount"]) if current_price else None
                tokens.append({
                    "mint": mint,
                    "symbol": meta.get("symbol", mint[:6] + "..."),
                    "name": meta.get("name", "Unknown Token"),
                    "logoURI": meta.get("logoURI", ""),
                    "amount": t["amount"],
                    "decimals": t["decimals"],
                    "current_price": current_price,
                    "current_value_usd": round(current_value, 4) if current_value else None,
                })

            # 5. Get recent transactions (last 10) — full signatures
            tx_resp = await client.post(SOLANA_RPC, json={
                "jsonrpc": "2.0", "id": 3,
                "method": "getSignaturesForAddress",
                "params": [address, {"limit": 10}]
            })
            tx_data = tx_resp.json()
            recent_txs = []
            for tx in tx_data.get("result", []):
                sig = tx.get("signature", "")
                recent_txs.append({
                    "signature": sig,
                    "signature_short": sig[:16] + "..." if len(sig) > 16 else sig,
                    "slot": tx.get("slot", 0),
                    "time": tx.get("blockTime", 0),
                    "status": "success" if tx.get("err") is None else "failed",
                })

            return JSONResponse(content={
                "address": address,
                "sol_balance": round(sol_balance, 6),
                "token_count": len(tokens),
                "tokens": tokens,
                "recent_transactions": recent_txs,
                "status": "ok"
            })
    except Exception as e:
        logger.error(f"Wallet lookup error: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=400
        )

# ── Test Trade Endpoint (for verifying buy/sell flow) ────────

@app.post("/api/test-buy")
async def test_buy(request: Request):
    """Force a test buy on a specific token — bypasses debate council."""
    try:
        body = await request.json()
        contract = body.get("contract", "")
        sol_amount = float(body.get("sol_amount", 0.1))
        
        if not contract:
            return JSONResponse(
                content={"status": "error", "message": "contract is required"},
                status_code=400
            )
        
        if sol_amount > 0.5:
            return JSONResponse(
                content={"status": "error", "message": "Max test amount is 0.5 SOL"},
                status_code=400
            )

        config = AppConfig.from_env()
        
        if not config.wallet.private_key or config.wallet.private_key == "PASTE_YOUR_NEW_PRIVATE_KEY_HERE":
            return JSONResponse(
                content={"status": "error", "message": "No private key configured — set SOLANA_PRIVATE_KEY in .env"},
                status_code=400
            )
        
        skill = BitgetWalletSkill()
        
        # Get token info
        token_info = skill.token_info("sol", contract)
        token_data = token_info.get("data", {})
        symbol = token_data.get("symbol", "???")
        price = float(token_data.get("price", 0) or 0)
        
        logger.info(f"🧪 TEST BUY: {sol_amount} SOL → ${symbol} ({contract[:16]}...)")
        
        # Step 1: Quote
        quote_result = skill.swap_quote(
            from_address=config.wallet.address,
            from_chain="sol",
            from_symbol="SOL",
            from_contract="",
            from_amount=str(sol_amount),
            to_chain="sol",
            to_symbol=symbol,
            to_contract=contract,
        )
        
        data = quote_result.get("data", {})
        quotes = data.get("quoteResults", [])
        if not quotes:
            return JSONResponse(
                content={"status": "error", "message": f"No quotes for ${symbol}", "raw": str(quote_result)[:500]},
                status_code=400
            )
        
        best = quotes[0]
        market = best.get("market", {})
        market_id = market.get("id", "")
        protocol = market.get("protocol", "")
        out_amount = float(best.get("outAmount", 0))
        slippage = best.get("slippageInfo", {}).get("recommendSlippage", "0.15")
        
        # Step 2: Confirm
        confirm_result = skill.swap_confirm(
            from_chain="sol", from_symbol="SOL",
            from_contract="", from_amount=str(sol_amount),
            from_address=config.wallet.address,
            to_chain="sol", to_symbol=symbol,
            to_contract=contract, to_address=config.wallet.address,
            market=market_id, protocol=protocol, slippage=slippage,
        )
        
        order_id = confirm_result.get("data", {}).get("orderId", "")
        if not order_id:
            return JSONResponse(
                content={"status": "error", "message": "No orderId from confirm", "raw": str(confirm_result)[:500]},
                status_code=400
            )
        
        # Step 3: Make order
        make_result = skill.swap_make_order(
            order_id=order_id,
            from_chain="sol", from_contract="",
            from_symbol="SOL", from_address=config.wallet.address,
            to_chain="sol", to_contract=contract,
            to_symbol=symbol, to_address=config.wallet.address,
            from_amount=str(sol_amount), slippage=slippage,
            market=market_id, protocol=protocol,
        )
        
        txs = make_result.get("data", {}).get("txs", [])
        if not txs:
            return JSONResponse(
                content={"status": "error", "message": "No txs from makeOrder", "raw": str(make_result)[:500]},
                status_code=400
            )
        
        # Step 4: Sign
        from src.strategy.trader import TradingEngine
        trader = TradingEngine(skill, config.wallet, config.trading)
        signed_txs = trader._sign_transactions(txs)
        if not signed_txs:
            return JSONResponse(
                content={"status": "error", "message": "Transaction signing failed"},
                status_code=400
            )
        
        # Step 5: Send
        send_result = skill.swap_send(order_id, signed_txs)
        
        logger.info(f"🧪 TEST BUY RESULT: {json.dumps(send_result)[:300]}")
        
        # Step 6: Register position for tracking (TP/SL monitoring)
        from src.strategy.trader import Position
        position = Position(
            token_contract=contract,
            token_symbol=symbol,
            chain="sol",
            entry_price=price,
            amount=out_amount,
            sol_spent=sol_amount,
            entry_time=datetime.utcnow().isoformat(),
            order_id=order_id,
            debate_signal="TEST",
        )
        trader.positions[contract] = position
        trader.save_positions()
        logger.info(f"📍 Position registered: {symbol} — will track for TP/SL")
        
        # Record in dashboard
        app_state["trades"].insert(0, {
            "symbol": symbol,
            "action": "TEST_BUY",
            "amount": out_amount,
            "price": price,
            "sol_amount": sol_amount,
            "pnl_pct": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "signal": "TEST",
        })
        app_state["stats"]["total_trades"] += 1
        app_state["stats"]["open_positions"] = len(trader.positions)
        save_state()
        
        return JSONResponse(content={
            "status": "ok",
            "message": f"Test buy executed: {sol_amount} SOL → {out_amount} ${symbol}",
            "order_id": order_id,
            "token": symbol,
            "sol_spent": sol_amount,
            "tokens_received": out_amount,
            "send_result": str(send_result)[:500],
        })
        
    except Exception as e:
        logger.error(f"Test buy failed: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500
        )

# ── Background Trading Loop ──────────────────────────────────

def run_trading_loop(config: AppConfig):
    """Background loop: scan → debate → trade → narrate."""
    global trader
    skill = BitgetWalletSkill()
    llm = QwenLLM(config.llm)
    scanner = TokenScanner(skill, config.trading.min_liquidity_usd, config.trading.min_holders)
    council = DebateCouncil(llm)
    trader = TradingEngine(skill, config.wallet, config.trading)
    narrator = NarratorAgent(llm)
    twitter = TwitterClient(config.twitter)

    dry_run = not bool(config.wallet.private_key)
    if dry_run:
        logger.info("⚠️  No wallet configured — DRY RUN mode")

    while True:
        try:
            app_state["cycle_count"] += 1
            app_state["status"] = "scanning"
            app_state["last_updated"] = datetime.utcnow().isoformat()

            # 1. Scan
            candidates = scanner.scan_trending(limit=10)
            lp = scanner.scan_launchpad(limit=10)
            all_candidates = scanner._deduplicate(candidates + lp)
            app_state["tokens_scanned"] = len(all_candidates)

            scanned_list = []
            for c in all_candidates[:10]:
                scanned_list.append({
                    "symbol": c.symbol, "name": c.name,
                    "price": c.price, "market_cap": c.market_cap,
                    "liquidity": c.liquidity, "holders": c.holders,
                    "platform": c.platform, "contract": c.contract,
                })
            app_state["scanned_tokens"] = scanned_list

            # 2. Enrich & Filter
            safe_tokens = []
            for c in all_candidates[:8]:
                c = scanner.enrich_candidate(c)
                passed, reason = scanner.quick_filter(c)
                if passed:
                    safe_tokens.append(c)
                else:
                    app_state["stats"]["rugs_avoided"] += 1

            app_state["stats"]["tokens_scanned"] += len(all_candidates)

            # 3. Debate
            app_state["status"] = "debating"
            for token in safe_tokens[:3]:
                result = council.debate(token)
                app_state["stats"]["total_debates"] += 1

                # Store debate result
                debate_entry = {
                    "token": token.symbol,
                    "contract": token.contract,
                    "price": token.price,
                    "market_cap": token.market_cap,
                    "signal": result.final_signal.name,
                    "consensus": round(result.consensus_score, 2),
                    "should_trade": result.should_trade,
                    "size_pct": result.recommended_size_pct,
                    "judge_reasoning": result.judge_reasoning[:200],
                    "votes": [
                        {
                            "agent": v.agent_name, "emoji": v.agent_emoji,
                            "signal": v.signal.name,
                            "confidence": round(v.confidence, 2),
                            "reasoning": v.reasoning[:100],
                        }
                        for v in result.votes
                    ],
                    "timestamp": datetime.utcnow().isoformat(),
                }
                app_state["debates"].insert(0, debate_entry)
                app_state["debates"] = app_state["debates"][:50]  # Keep last 50

                # 4. Trade
                if result.should_trade:
                    app_state["status"] = "trading"
                    if not dry_run:
                        trade = trader.execute_buy(result)
                        if trade:
                            trade_entry = {
                                "symbol": trade.token_symbol,
                                "action": trade.action,
                                "amount": trade.amount,
                                "price": trade.price,
                                "sol_amount": trade.sol_amount,
                                "pnl_pct": trade.pnl_pct,
                                "timestamp": trade.timestamp,
                                "signal": trade.debate_signal,
                            }
                            app_state["trades"].insert(0, trade_entry)

                            # Post to X
                            tweets = narrator.narrate_debate(result, trade)
                            twitter.post_debate_result(tweets)
                    else:
                        # Dry run — still narrate
                        tweets = narrator.narrate_debate(result)
                        twitter.post_debate_result(tweets)

                        app_state["trades"].insert(0, {
                            "symbol": token.symbol,
                            "action": "DRY_RUN_BUY",
                            "amount": 0, "price": token.price,
                            "sol_amount": 0, "pnl_pct": 0,
                            "timestamp": datetime.utcnow().isoformat(),
                            "signal": result.final_signal.name,
                        })

            # 5. Check positions
            if not dry_run:
                actions = trader.check_positions()
                for action in actions:
                    app_state["trades"].insert(0, {
                        "symbol": action.token_symbol,
                        "action": action.action,
                        "amount": action.amount,
                        "price": action.price,
                        "sol_amount": action.sol_amount,
                        "pnl_pct": action.pnl_pct,
                        "timestamp": action.timestamp,
                    })

            # 6. Update stats
            stats = trader.get_stats()
            app_state["stats"].update(stats)
            app_state["status"] = "idle"
            app_state["last_updated"] = datetime.utcnow().isoformat()

            # 7. Persist state to disk
            save_state()

        except Exception as e:
            logger.error(f"Loop error: {e}")
            app_state["status"] = "error"
            save_state()

        time.sleep(config.trading.scan_interval_seconds)


def start_server(host: str = "0.0.0.0", port: int = 8888):
    """Start dashboard server with background trading loop."""
    import uvicorn

    config = AppConfig.from_env()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  🧠 SolScout AI Dashboard                                ║
║  🌐 http://localhost:{port:<5}                              ║
║  📡 API: /api/state | /api/debates | /api/trades          ║
║  🎮 Controls: /api/scan (POST) — trigger manual scan      ║
║  ⏹️  Press Ctrl+C to stop                                  ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Start trading loop in background thread
    loop_thread = threading.Thread(
        target=run_trading_loop,
        args=(config,),
        daemon=True,
    )
    loop_thread.start()
    logger.info("🤖 Trading loop started in background")

    # Start web server
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    start_server()
