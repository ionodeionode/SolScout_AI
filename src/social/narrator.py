"""SolScout AI — Narrator Agent (Social Layer)

Transforms trading debates and results into engaging X/Twitter content.
This is the "Talent Show" component — giving the agent personality.
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.utils.llm import QwenLLM
from src.agent.debate import DebateResult, Signal
from src.strategy.trader import TradeLog

logger = logging.getLogger("solscout.narrator")


NARRATOR_SYSTEM = """You are SolScout AI — a memecoin trading agent on Solana with a witty, data-driven personality.
You narrate your trading decisions like a smart trader who doesn't take themselves too seriously.
Rules:
- Keep tweets under 280 characters
- Use emojis strategically (not excessively)
- Include $TICKER for the token
- Be honest about losses — humor about mistakes, data-flex about wins
- Show the DEBATE process — this is what makes you unique
- Include @BitgetWallet and #AgentTalentShow in the first tweet of threads
"""


class NarratorAgent:
    """Generates social media content from debate results and trades."""

    def __init__(self, llm: QwenLLM):
        self.llm = llm

    def narrate_debate(self, debate: DebateResult, trade: TradeLog | None = None) -> list[str]:
        """Create a tweet thread about a debate and trade decision."""

        vote_summary = "\n".join([
            f"{v.agent_emoji} {v.agent_name}: {v.signal.name} ({v.confidence:.0%}) — {v.reasoning[:60]}"
            for v in debate.votes
        ])

        trade_info = "No trade executed."
        if trade:
            trade_info = f"Traded {trade.sol_amount} SOL for {trade.amount} ${trade.token_symbol}"

        prompt = f"""Write a Twitter THREAD (4-5 tweets, separated by ---) about this trading debate:

TOKEN: ${debate.token.symbol}
Price: ${debate.token.price}
Market Cap: ${debate.token.market_cap:,.0f}

DEBATE VOTES:
{vote_summary}

JUDGE VERDICT: {debate.final_signal.name}
Consensus: {debate.consensus_score:.0%}
Judge reasoning: {debate.judge_reasoning}
Trade: {trade_info}

THREAD FORMAT:
Tweet 1: Hook + decision summary. Tag @BitgetWallet #AgentTalentShow
Tweet 2-3: Key agent insights with emojis (📊🐋🛡️📢)
Tweet 4: The contrarian angle — what almost changed the decision
Tweet 5: Final take — what you learned

Keep each tweet under 280 chars. Make it ENGAGING — humans should want to follow.
Separate tweets with ---"""

        raw = self.llm.chat(prompt, system=NARRATOR_SYSTEM, temperature=0.8)
        tweets = [t.strip() for t in raw.split("---") if t.strip()]
        return tweets[:5]

    def daily_report(self, stats: dict, positions: list, debates_count: int) -> str:
        """Generate daily performance report tweet."""

        prompt = f"""Write ONE tweet (max 280 chars) as SolScout AI's daily report:

📊 Today's Stats:
- Trades: {stats.get('total_trades', 0)}
- Win Rate: {stats.get('win_rate', 0):.0%}
- PnL: {stats.get('total_pnl_sol', 0):+.4f} SOL
- Open Positions: {stats.get('open_positions', 0)}
- Debates: {debates_count}
- Rugs Avoided: (estimate based on Guard vetoes)

Style: Honest. Data-driven. Slight humor.
End with @BitgetWallet #AgentTalentShow"""

        return self.llm.chat(prompt, system=NARRATOR_SYSTEM, temperature=0.7)

    def special_event(self, event_type: str, data: dict) -> str:
        """Generate tweet for special events."""

        events = {
            "rug_avoided": (
                f"🛡️ CLOSE CALL! My Guard Agent just saved me from a potential rug on ${data.get('symbol', '???')}. "
                f"Red flag: {data.get('reason', 'suspicious activity')}. "
                f"AI agents protecting humans, one rug at a time 🤖 @BitgetWallet #AgentTalentShow"
            ),
            "big_win": (
                f"💎 ${data.get('symbol', '???')} just hit +{data.get('pnl', 0):.0f}%! "
                f"My debate council called it: {data.get('signal', 'BUY')} with {data.get('consensus', 0):.0%} consensus. "
                f"@BitgetWallet #AgentTalentShow"
            ),
            "judge_veto": (
                f"⚖️ VETO! All agents said BUY on ${data.get('symbol', '???')}, "
                f"but my Judge said NO — {data.get('reason', 'contrarian instinct')}. "
                f"Let's see who's right... 🧠 @BitgetWallet #AgentTalentShow"
            ),
        }

        return events.get(event_type, f"🤖 SolScout AI is watching the markets... @BitgetWallet #AgentTalentShow")

    def format_thread_for_display(self, tweets: list[str]) -> str:
        """Format a thread for console display."""
        lines = ["╔══════════════════════════════════════╗"]
        lines.append("║     🐦 SolScout AI — X Thread        ║")
        lines.append("╠══════════════════════════════════════╣")
        for i, tweet in enumerate(tweets, 1):
            lines.append(f"║ [{i}/{len(tweets)}]")
            # Word-wrap at ~50 chars
            words = tweet.split()
            line = "║  "
            for word in words:
                if len(line) + len(word) > 55:
                    lines.append(line)
                    line = "║  "
                line += word + " "
            lines.append(line)
            if i < len(tweets):
                lines.append("║  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─")
        lines.append("╚══════════════════════════════════════╝")
        return "\n".join(lines)
