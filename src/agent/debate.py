"""SolScout AI — Multi-Agent Debate Council

The core differentiator: multiple specialized AI agents debate
before making any trading decision. Each agent analyzes from
a different perspective, then a Judge Agent synthesizes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from src.utils.llm import QwenLLM
from src.data.scanner import TokenCandidate

logger = logging.getLogger("solscout.debate")


class Signal(Enum):
    STRONG_BUY = 2
    BUY = 1
    HOLD = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class AgentVote:
    agent_name: str
    agent_emoji: str
    signal: Signal
    confidence: float  # 0.0-1.0
    reasoning: str
    key_data: dict = field(default_factory=dict)


@dataclass
class DebateResult:
    token: TokenCandidate
    votes: list[AgentVote]
    final_signal: Signal
    consensus_score: float  # 0.0-1.0 how much agents agree
    judge_reasoning: str
    recommended_size_pct: float  # Portfolio % to allocate
    should_trade: bool
    timestamp: str = ""

    def summary(self) -> str:
        lines = [f"═══ DEBATE: ${self.token.symbol} ═══"]
        for v in self.votes:
            lines.append(f"{v.agent_emoji} {v.agent_name}: {v.signal.name} ({v.confidence:.0%}) — {v.reasoning[:80]}")
        lines.append(f"⚖️ JUDGE: {self.final_signal.name} | Consensus: {self.consensus_score:.0%}")
        lines.append(f"   {self.judge_reasoning[:120]}")
        lines.append(f"   Trade: {'YES' if self.should_trade else 'NO'} | Size: {self.recommended_size_pct:.1f}%")
        return "\n".join(lines)


SYSTEM_PROMPT = """You are part of SolScout AI's Multi-Agent Debate Council.
You analyze Solana memecoin tokens from your specialized perspective.
Always respond in valid JSON format with these fields:
{
  "signal": "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL",
  "confidence": 0.0-1.0,
  "reasoning": "Your concise analysis (1-3 sentences)",
  "key_data": { "brief supporting data points" }
}
Be CONCISE. Be HONEST. If data is missing, say so and lower your confidence.
"""


class DebateCouncil:
    """Multi-Agent Debate System for trading decisions."""

    def __init__(self, llm: QwenLLM):
        self.llm = llm

    def debate(self, candidate: TokenCandidate) -> DebateResult:
        """Run a full multi-agent debate on a token candidate."""
        logger.info(f"Starting debate for ${candidate.symbol} ({candidate.contract[:12]}...)")

        # Phase 1: Each agent votes independently
        votes = [
            self._analyst_vote(candidate),
            self._sentiment_vote(candidate),
            self._guard_vote(candidate),
            self._whale_vote(candidate),
        ]

        # Phase 2: Judge synthesizes
        result = self._judge_deliberate(candidate, votes)
        logger.info(f"Debate result: {result.final_signal.name} (trade={result.should_trade})")
        return result

    # ── Analyst Agent ────────────────────────────────────────────

    def _analyst_vote(self, c: TokenCandidate) -> AgentVote:
        """📊 Technical Analysis Agent — price action, volume, momentum."""

        # Prepare kline summary
        kline_summary = "No kline data available."
        if c.kline_data and len(c.kline_data) > 0:
            recent = c.kline_data[-10:] if len(c.kline_data) >= 10 else c.kline_data
            kline_summary = json.dumps(recent[:5], indent=0)  # Send a sample

        # Price changes from market data
        price_changes = {}
        if c.market_data:
            for key in ["price_change_5m", "price_change_1h", "price_change_4h", "price_change_24h"]:
                if key in c.market_data:
                    price_changes[key] = c.market_data[key]

        prompt = f"""Analyze this Solana memecoin as a Technical Analyst:

TOKEN: ${c.symbol} ({c.name})
Price: ${c.price}
Market Cap: ${c.market_cap:,.0f}
24h Volume: ${c.volume_24h:,.0f}
Liquidity: ${c.liquidity:,.0f}
Price Changes: {json.dumps(price_changes)}
Recent K-line (15min): {kline_summary}
Tx Stats: {json.dumps(c.tx_stats) if c.tx_stats else 'N/A'}

Analyze: price momentum, volume trend, buy/sell ratio, overbought/oversold.
Give your trading signal."""

        return self._get_vote("Analyst", "📊", prompt)

    # ── Sentiment Agent ──────────────────────────────────────────

    def _sentiment_vote(self, c: TokenCandidate) -> AgentVote:
        """📢 Sentiment Agent — social signals, narrative, hype level."""

        prompt = f"""Analyze this Solana memecoin from a SOCIAL SENTIMENT perspective:

TOKEN: ${c.symbol} ({c.name})
Price: ${c.price}
Market Cap: ${c.market_cap:,.0f}
Holders: {c.holders}
Has Twitter: {bool(c.socials.get('twitter'))}
Has Website: {bool(c.socials.get('website'))}
Platform: {c.platform}
Narratives: {c.market_data.get('narratives', 'N/A') if c.market_data else 'N/A'}
Narrative Tags: {c.market_data.get('narrative_tags', []) if c.market_data else 'N/A'}

Consider:
1. Does the token name/narrative tap into current trends?
2. Social presence quality (having twitter/website = more legit)
3. Holder count vs market cap ratio (healthy distribution?)
4. Platform reputation (pump.fun vs trends.fun vs raydium)
5. Is this likely organic growth or manufactured?

Give your signal."""

        return self._get_vote("Sentiment", "📢", prompt)

    # ── Guard Agent ──────────────────────────────────────────────

    def _guard_vote(self, c: TokenCandidate) -> AgentVote:
        """🛡️ Guard Agent — security, rug detection, red flags."""

        # Dev history
        dev_summary = "No dev data."
        if c.dev_info:
            tokens = c.dev_info.get("tokens", [])
            total = len(tokens)
            rugged = sum(1 for t in tokens if isinstance(t, dict) and t.get("rug_status") == 1)
            dev_summary = f"Dev launched {total} tokens, {rugged} rugged ({rugged/max(total,1)*100:.0f}%)"

        prompt = f"""You are a SECURITY GUARD agent. Your job is to PROTECT against losses.
Be SKEPTICAL. It's better to miss a good trade than to get rugged.

TOKEN: ${c.symbol} ({c.name})
Security Audit: {json.dumps(c.security) if c.security else 'No audit data'}
Dev History: {dev_summary}
Liquidity: ${c.liquidity:,.0f}
Holders: {c.holders}
Top 10 Holders: {c.market_data.get('top10_holder_percent', 'N/A') if c.market_data else 'N/A'}
Insider Holders: {c.market_data.get('insider_holder_percent', 'N/A') if c.market_data else 'N/A'}
Sniper Holders: {c.market_data.get('sniper_holder_percent', 'N/A') if c.market_data else 'N/A'}
Dev Holdings: {c.market_data.get('dev_holder_percent', 'N/A') if c.market_data else 'N/A'}
Lock LP: {c.market_data.get('lock_lp_percent', 'N/A') if c.market_data else 'N/A'}

RED FLAGS to check:
1. High tax (buy/sell tax > 5%)
2. Dev rugged before
3. Top 10 holders > 40%
4. Snipers > 20%
5. Low liquidity
6. Honeypot indicators

If ANY serious red flag: STRONG_SELL signal regardless of other factors.
Give your signal."""

        return self._get_vote("Guard", "🛡️", prompt)

    # ── Whale Agent ──────────────────────────────────────────────

    def _whale_vote(self, c: TokenCandidate) -> AgentVote:
        """🐋 Whale Agent — smart money movements, holder distribution."""

        prompt = f"""You are a WHALE TRACKER agent. Analyze smart money movements:

TOKEN: ${c.symbol} ({c.name})
Market Cap: ${c.market_cap:,.0f}
Holders: {c.holders}
Liquidity: ${c.liquidity:,.0f}
Top 10 Holders: {c.market_data.get('top10_holder_percent', 'N/A') if c.market_data else 'N/A'}
Dev Holdings: {c.market_data.get('dev_holder_percent', 'N/A') if c.market_data else 'N/A'}
Tx Stats (buy/sell): {json.dumps(c.tx_stats) if c.tx_stats else 'N/A'}

Analyze:
1. Is buying pressure > selling pressure? (from tx stats)
2. Is holder distribution healthy? (not too concentrated)
3. Mcap-to-liquidity ratio (healthy = 5:1 to 20:1)
4. Are large holders likely accumulating or distributing?

Give your signal."""

        return self._get_vote("Whale", "🐋", prompt)

    # ── Judge Agent ──────────────────────────────────────────────

    def _judge_deliberate(self, candidate: TokenCandidate, votes: list[AgentVote]) -> DebateResult:
        """⚖️ Judge Agent — adversarial synthesis of all votes."""

        debate_log = "\n".join([
            f"[{v.agent_emoji} {v.agent_name}] Signal: {v.signal.name} "
            f"(Confidence: {v.confidence:.0%})\n"
            f"  Reasoning: {v.reasoning}"
            for v in votes
        ])

        prompt = f"""You are the JUDGE in SolScout AI's trading debate council.

TOKEN: ${candidate.symbol} — Price: ${candidate.price} — MCap: ${candidate.market_cap:,.0f}

AGENT VOTES:
{debate_log}

YOUR RULES:
1. Find CONTRADICTIONS between agents — resolve them
2. Weight votes by confidence AND evidence quality
3. VETO RULE: If Guard says STRONG_SELL with confidence > 60%, 
   the answer is NO TRADE regardless of others
4. Apply CONTRARIAN thinking: if everyone says BUY, 
   check if it might be late-stage FOMO
5. Calculate consensus score (0-1): how much agents agree

Respond in JSON:
{{
  "final_signal": "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL",
  "consensus_score": 0.0-1.0,
  "reasoning": "Your synthesis (2-4 sentences)",
  "should_trade": true | false,
  "recommended_size_pct": 0.0-5.0,
  "contrarian_note": "What could go wrong?"
}}"""

        result = self.llm.chat_json(prompt, system=SYSTEM_PROMPT)

        # Parse judge response
        if result.get("parse_error"):
            logger.warning("Judge response parse failed, defaulting to HOLD")
            return DebateResult(
                token=candidate, votes=votes,
                final_signal=Signal.HOLD, consensus_score=0.0,
                judge_reasoning="Parse error — defaulting to safe HOLD",
                recommended_size_pct=0.0, should_trade=False,
                timestamp=datetime.utcnow().isoformat(),
            )

        signal_str = result.get("final_signal", "HOLD")
        try:
            final_signal = Signal[signal_str]
        except KeyError:
            final_signal = Signal.HOLD

        should_trade = result.get("should_trade", False)
        size_pct = float(result.get("recommended_size_pct", 0))
        consensus = float(result.get("consensus_score", 0))
        reasoning = result.get("reasoning", "No reasoning provided")
        contrarian = result.get("contrarian_note", "")

        full_reasoning = f"{reasoning}"
        if contrarian:
            full_reasoning += f" ⚠️ Contrarian: {contrarian}"

        return DebateResult(
            token=candidate,
            votes=votes,
            final_signal=final_signal,
            consensus_score=consensus,
            judge_reasoning=full_reasoning,
            recommended_size_pct=size_pct,
            should_trade=should_trade,
            timestamp=datetime.utcnow().isoformat(),
        )

    # ── Helpers ───────────────────────────────────────────────────

    def _get_vote(self, agent_name: str, emoji: str, prompt: str) -> AgentVote:
        """Send prompt to LLM and parse the vote."""
        try:
            result = self.llm.chat_json(prompt, system=SYSTEM_PROMPT, temperature=0.4)

            if result.get("parse_error"):
                return AgentVote(
                    agent_name=agent_name, agent_emoji=emoji,
                    signal=Signal.HOLD, confidence=0.3,
                    reasoning="Failed to parse LLM response",
                )

            signal_str = result.get("signal", "HOLD")
            try:
                signal = Signal[signal_str]
            except KeyError:
                signal = Signal.HOLD

            return AgentVote(
                agent_name=agent_name,
                agent_emoji=emoji,
                signal=signal,
                confidence=float(result.get("confidence", 0.5)),
                reasoning=result.get("reasoning", "No reasoning"),
                key_data=result.get("key_data", {}),
            )
        except Exception as e:
            logger.error(f"{agent_name} vote failed: {e}")
            return AgentVote(
                agent_name=agent_name, agent_emoji=emoji,
                signal=Signal.HOLD, confidence=0.1,
                reasoning=f"Agent error: {e}",
            )
