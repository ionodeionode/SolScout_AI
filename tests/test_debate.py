"""Tests for the Debate Council module."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.debate import Signal, AgentVote, DebateResult, DebateCouncil
from src.data.scanner import TokenCandidate


def make_candidate(**kwargs):
    defaults = dict(
        chain="sol", contract="ABC123", symbol="TEST", name="TestToken",
        price=0.001, market_cap=100_000, liquidity=10_000, holders=200,
    )
    defaults.update(kwargs)
    return TokenCandidate(**defaults)


class TestSignal(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Signal.STRONG_BUY.value, 2)
        self.assertEqual(Signal.HOLD.value, 0)
        self.assertEqual(Signal.STRONG_SELL.value, -2)


class TestDebateResult(unittest.TestCase):
    def test_summary(self):
        token = make_candidate()
        votes = [
            AgentVote("Analyst", "📊", Signal.BUY, 0.8, "Looks bullish"),
            AgentVote("Guard", "🛡️", Signal.HOLD, 0.6, "No red flags but cautious"),
        ]
        result = DebateResult(
            token=token, votes=votes,
            final_signal=Signal.BUY, consensus_score=0.7,
            judge_reasoning="Balanced outlook, proceed", recommended_size_pct=3.0,
            should_trade=True,
        )
        summary = result.summary()
        self.assertIn("TEST", summary)
        self.assertIn("BUY", summary)
        self.assertIn("Analyst", summary)
        self.assertIn("Guard", summary)
        self.assertIn("YES", summary)


class TestDebateCouncil(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.council = DebateCouncil(self.mock_llm)

    def test_get_vote_success(self):
        self.mock_llm.chat_json.return_value = {
            "signal": "BUY", "confidence": 0.75,
            "reasoning": "Good momentum", "key_data": {"rsi": 55},
        }
        vote = self.council._get_vote("Analyst", "📊", "Analyze this token")
        self.assertEqual(vote.signal, Signal.BUY)
        self.assertAlmostEqual(vote.confidence, 0.75)
        self.assertIn("momentum", vote.reasoning)

    def test_get_vote_parse_error(self):
        self.mock_llm.chat_json.return_value = {"raw": "garbled", "parse_error": True}
        vote = self.council._get_vote("Analyst", "📊", "Analyze this token")
        self.assertEqual(vote.signal, Signal.HOLD)
        self.assertAlmostEqual(vote.confidence, 0.3)

    def test_get_vote_invalid_signal(self):
        self.mock_llm.chat_json.return_value = {
            "signal": "MOON", "confidence": 0.9,
            "reasoning": "Invalid signal string",
        }
        vote = self.council._get_vote("Analyst", "📊", "Analyze this token")
        self.assertEqual(vote.signal, Signal.HOLD)

    def test_judge_deliberate_buy(self):
        self.mock_llm.chat_json.return_value = {
            "final_signal": "BUY", "consensus_score": 0.8,
            "reasoning": "Strong consensus",
            "should_trade": True, "recommended_size_pct": 3.0,
            "contrarian_note": "Could be late entry",
        }
        candidate = make_candidate()
        votes = [
            AgentVote("Analyst", "📊", Signal.BUY, 0.8, "Bullish"),
            AgentVote("Guard", "🛡️", Signal.HOLD, 0.6, "OK"),
        ]
        result = self.council._judge_deliberate(candidate, votes)
        self.assertEqual(result.final_signal, Signal.BUY)
        self.assertTrue(result.should_trade)
        self.assertAlmostEqual(result.recommended_size_pct, 3.0)

    def test_judge_deliberate_parse_error(self):
        self.mock_llm.chat_json.return_value = {"raw": "broken", "parse_error": True}
        candidate = make_candidate()
        votes = [AgentVote("Analyst", "📊", Signal.BUY, 0.8, "Bullish")]
        result = self.council._judge_deliberate(candidate, votes)
        self.assertEqual(result.final_signal, Signal.HOLD)
        self.assertFalse(result.should_trade)

    def test_full_debate(self):
        """Test full debate flow with mocked LLM."""
        call_count = [0]
        def mock_chat_json(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 4:  # Agent votes
                return {
                    "signal": "BUY", "confidence": 0.7,
                    "reasoning": f"Agent {call_count[0]} says buy",
                    "key_data": {},
                }
            else:  # Judge
                return {
                    "final_signal": "BUY", "consensus_score": 0.85,
                    "reasoning": "All agents agree",
                    "should_trade": True, "recommended_size_pct": 4.0,
                    "contrarian_note": "",
                }

        self.mock_llm.chat_json.side_effect = mock_chat_json
        candidate = make_candidate()
        result = self.council.debate(candidate)
        self.assertEqual(len(result.votes), 4)
        self.assertEqual(result.final_signal, Signal.BUY)
        self.assertTrue(result.should_trade)


if __name__ == "__main__":
    unittest.main()
