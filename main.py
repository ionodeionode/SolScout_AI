"""
SolScout AI — Autonomous Memecoin Intelligence Agent
=====================================================

Multi-Agent Debate Trading System on Solana.
Built with Bitget Wallet Skill + Qwen LLM.

Usage:
    python main.py scan          # Scan & display trending tokens
    python main.py debate <addr> # Run debate on specific token
    python main.py run           # Full autonomous loop
    python main.py demo          # Demo mode (no real trading)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from config.settings import AppConfig
from src.utils.llm import QwenLLM
from src.data.bws_client import BitgetWalletSkill
from src.data.scanner import TokenScanner
from src.agent.debate import DebateCouncil
from src.strategy.trader import TradingEngine
from src.social.narrator import NarratorAgent

# ── Logging ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("solscout")


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ███████╗ ██████╗ ██╗     ███████╗ ██████╗ ██████╗ ██╗   ██╗████████╗ ║
║   ██╔════╝██╔═══██╗██║     ██╔════╝██╔════╝██╔═══██╗██║   ██║╚══██╔══╝ ║
║   ███████╗██║   ██║██║     ███████╗██║     ██║   ██║██║   ██║   ██║    ║
║   ╚════██║██║   ██║██║     ╚════██║██║     ██║   ██║██║   ██║   ██║    ║
║   ███████║╚██████╔╝███████╗███████║╚██████╗╚██████╔╝╚██████╔╝   ██║    ║
║   ╚══════╝ ╚═════╝ ╚══════╝╚══════╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝    ║
║                                                              ║
║   🧠 Multi-Agent Debate Trading on Solana                    ║
║   🔧 Powered by Bitget Wallet Skill + Qwen                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


def build_components(config: AppConfig):
    """Initialize all components."""
    skill = BitgetWalletSkill()
    llm = QwenLLM(config.llm)
    scanner = TokenScanner(skill, config.trading.min_liquidity_usd, config.trading.min_holders)
    council = DebateCouncil(llm)
    trader = TradingEngine(skill, config.wallet, config.trading)
    narrator = NarratorAgent(llm)
    return skill, llm, scanner, council, trader, narrator


# ── Commands ──────────────────────────────────────────────────────

def cmd_scan(config: AppConfig):
    """Scan and display trending tokens."""
    skill, llm, scanner, council, trader, narrator = build_components(config)

    print("\n🔍 Scanning trending tokens on Solana...\n")

    # Scan rankings
    candidates = scanner.scan_trending(limit=10)
    print(f"📊 Found {len(candidates)} tokens from rankings\n")

    # Scan launchpad
    lp_candidates = scanner.scan_launchpad(limit=10)
    print(f"🚀 Found {len(lp_candidates)} tokens from launchpad\n")

    all_candidates = candidates + lp_candidates

    print(f"{'Symbol':<12} {'Price':>12} {'MCap':>14} {'Liquidity':>12} {'Holders':>8} {'Platform':<15}")
    print("─" * 80)

    for c in all_candidates:
        print(
            f"${c.symbol:<11} "
            f"${c.price:>11.8f} "
            f"${c.market_cap:>13,.0f} "
            f"${c.liquidity:>11,.0f} "
            f"{c.holders:>7} "
            f"{c.platform:<15}"
        )

    print(f"\nTotal: {len(all_candidates)} tokens found")


def cmd_debate(config: AppConfig, contract: str):
    """Run a debate on a specific token."""
    skill, llm, scanner, council, trader, narrator = build_components(config)

    print(f"\n🧠 Running debate for token: {contract[:20]}...\n")

    # Create candidate from contract
    from src.data.scanner import TokenCandidate
    candidate = TokenCandidate(chain="sol", contract=contract, symbol="???", name="")

    # Enrich with data
    print("📡 Fetching token data...")
    candidate = scanner.enrich_candidate(candidate)

    # Try to get symbol from market data
    if candidate.market_data:
        candidate.symbol = candidate.market_data.get("symbol", candidate.symbol)
        candidate.name = candidate.market_data.get("name", candidate.name)

    print(f"   Token: ${candidate.symbol} ({candidate.name})")
    print(f"   Price: ${candidate.price}")
    print(f"   MCap: ${candidate.market_cap:,.0f}")
    print(f"   Liquidity: ${candidate.liquidity:,.0f}")
    print(f"   Holders: {candidate.holders}")

    # Quick filter
    passed, reason = scanner.quick_filter(candidate)
    print(f"\n🛡️ Quick filter: {'✅ PASS' if passed else '❌ FAIL — ' + reason}")

    if not passed:
        print("Token failed safety filter. Skipping debate.")
        return

    # Run debate
    print("\n⚖️ Starting Multi-Agent Debate...\n")
    result = council.debate(candidate)

    # Display result
    print(result.summary())

    # Generate narration
    print("\n📝 Generating narrative thread...\n")
    tweets = narrator.narrate_debate(result)
    print(narrator.format_thread_for_display(tweets))


def cmd_demo(config: AppConfig):
    """Demo mode: scan → filter → debate → narrate (no real trading)."""
    skill, llm, scanner, council, trader, narrator = build_components(config)

    print("\n🎭 DEMO MODE — Scan → Debate → Narrate (no real trades)\n")

    # Step 1: Scan
    print("═══ Step 1: Scanning ═══")
    candidates = scanner.scan_trending(limit=5)
    lp = scanner.scan_launchpad(limit=5)
    all_candidates = (candidates + lp)[:8]
    print(f"Found {len(all_candidates)} candidates\n")

    if not all_candidates:
        print("No tokens found. Try again later.")
        return

    # Step 2: Enrich & Filter
    print("═══ Step 2: Enrich & Filter ═══")
    debate_targets = []
    for c in all_candidates[:5]:  # Limit to 5 to save API calls
        print(f"  Checking ${c.symbol}...", end=" ")
        c = scanner.enrich_candidate(c)
        passed, reason = scanner.quick_filter(c)
        if passed:
            print("✅ SAFE")
            debate_targets.append(c)
        else:
            print(f"❌ {reason}")

    if not debate_targets:
        print("\nNo tokens passed safety filter.")
        return

    # Step 3: Debate top candidate
    print(f"\n═══ Step 3: Debate (${debate_targets[0].symbol}) ═══")
    result = council.debate(debate_targets[0])
    print(result.summary())

    # Step 4: Narrate
    print(f"\n═══ Step 4: Narrate ═══")
    tweets = narrator.narrate_debate(result)
    print(narrator.format_thread_for_display(tweets))

    # Step 5: Stats
    print(f"\n═══ Summary ═══")
    print(f"Tokens scanned: {len(all_candidates)}")
    print(f"Passed filter: {len(debate_targets)}")
    print(f"Debate signal: {result.final_signal.name}")
    print(f"Should trade: {'YES' if result.should_trade else 'NO'}")
    print(f"Recommended size: {result.recommended_size_pct}% of portfolio")


def cmd_run(config: AppConfig):
    """Full autonomous loop: scan → debate → trade → narrate → repeat."""
    skill, llm, scanner, council, trader, narrator = build_components(config)

    if not config.wallet.private_key:
        print("⚠️  No SOLANA_PRIVATE_KEY configured. Running in DRY RUN mode.")
        dry_run = True
    else:
        dry_run = False
        balance = trader.get_sol_balance()
        print(f"💰 Wallet balance: {balance} SOL")

    print(f"\n🤖 Starting autonomous loop (interval: {config.trading.scan_interval_seconds}s)\n")
    print("Press Ctrl+C to stop.\n")

    cycle = 0
    total_debates = 0

    try:
        while True:
            cycle += 1
            print(f"\n{'═' * 60}")
            print(f"  Cycle #{cycle} — {time.strftime('%H:%M:%S')}")
            print(f"{'═' * 60}")

            # 1. 🚨 Monitor existing positions first! (PRIORITY)
            if not dry_run:
                print("🕵️  Checking current positions for TP/SL signals...")
                actions = trader.check_positions()
                for action in actions:
                    print(f"  📋 {action.action}: ${action.token_symbol} PnL={action.pnl_pct:+.1f}%")

            # 2. Check if we reached Max Open Positions limit
            open_count = sum(1 for p in trader.positions.values() if p.status != "closed")
            if open_count >= config.trading.max_open_positions:
                print(f"⚠️  Max open positions reached ({open_count}/{config.trading.max_open_positions}).")
                print("⏭️  Skipping new scans to prioritize monitoring.")
            else:
                # 3. Scan & filter
                candidates = scanner.scan_trending(limit=10)
                lp = scanner.scan_launchpad(limit=10)
                all_candidates = scanner._deduplicate(candidates + lp)
                print(f"📡 Found {len(all_candidates)} tokens")

                safe_tokens = []
                for c in all_candidates[:8]:
                    c = scanner.enrich_candidate(c)
                    passed, reason = scanner.quick_filter(c)
                    if passed:
                        safe_tokens.append(c)

                print(f"🛡️ {len(safe_tokens)} passed safety filter")

                # 4. Debate top candidates
                for token in safe_tokens[:3]:
                    result = council.debate(token)
                    total_debates += 1
                    print(f"\n{result.summary()}")

                    # 5. Trade if signal is positive
                    if result.should_trade and not dry_run:
                        trade = trader.execute_buy(result)
                        if trade:
                            tweets = narrator.narrate_debate(result, trade)
                            print(narrator.format_thread_for_display(tweets))

                    elif result.should_trade and dry_run:
                        print(f"  [DRY RUN] Would buy ${result.token.symbol} with {result.recommended_size_pct}% portfolio")
                        tweets = narrator.narrate_debate(result)
                        print(narrator.format_thread_for_display(tweets))

            # 6. Stats
            stats = trader.get_stats()
            print(f"\n📊 Stats: {stats['total_trades']} trades | "
                  f"Win rate: {stats['win_rate']:.0%} | "
                  f"PnL: {stats['total_pnl_sol']:+.4f} SOL | "
                  f"Debates: {total_debates}")

            # Wait for next cycle
            print(f"\n⏳ Next scan in {config.trading.scan_interval_seconds}s...")
            time.sleep(config.trading.scan_interval_seconds)

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping SolScout AI...")
        stats = trader.get_stats()
        print(f"\n📊 Final Stats: {json.dumps(stats, indent=2)}")


# ── Dashboard Command ─────────────────────────────────────────────

def cmd_dashboard(config: AppConfig, port: int = 8888):
    """Launch the real-time web dashboard with trading loop."""
    print(f"\n🌐 Starting SolScout AI Dashboard on http://localhost:{port}\n")
    from dashboard.server import start_server
    start_server(port=port)


# ── Main ──────────────────────────────────────────────────────────

def main():
    print_banner()
    config = AppConfig.from_env()

    parser = argparse.ArgumentParser(description="SolScout AI — Multi-Agent Debate Trading")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan", help="Scan trending tokens")
    debate_p = sub.add_parser("debate", help="Debate a specific token")
    debate_p.add_argument("contract", help="Token contract address")
    sub.add_parser("demo", help="Demo mode (scan→debate→narrate, no trading)")
    sub.add_parser("run", help="Full autonomous trading loop")
    dash_p = sub.add_parser("dashboard", help="Launch real-time web dashboard")
    dash_p.add_argument("--port", type=int, default=8888, help="Dashboard port")

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(config)
    elif args.command == "debate":
        cmd_debate(config, args.contract)
    elif args.command == "demo":
        cmd_demo(config)
    elif args.command == "run":
        cmd_run(config)
    elif args.command == "dashboard":
        cmd_dashboard(config, port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
