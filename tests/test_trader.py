"""Tests for the Trading Engine module."""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import TradingConfig, WalletConfig
from src.strategy.trader import TradingEngine, Position
from src.agent.debate import DebateResult, Signal, AgentVote
from src.data.scanner import TokenCandidate


def make_debate_result(signal=Signal.BUY, should_trade=True, size_pct=3.0):
    token = TokenCandidate(
        chain="sol", contract="test123", symbol="TEST", name="TestToken",
        price=0.001, market_cap=100000, liquidity=10000, holders=200,
    )
    votes = [AgentVote("Analyst", "📊", Signal.BUY, 0.8, "Bullish")]
    return DebateResult(
        token=token, votes=votes,
        final_signal=signal, consensus_score=0.8,
        judge_reasoning="Test", recommended_size_pct=size_pct,
        should_trade=should_trade,
    )


class TestPositionSizing(unittest.TestCase):
    def setUp(self):
        self.mock_skill = MagicMock()
        wallet = WalletConfig(private_key="test", address="addr123")
        trading = TradingConfig(max_position_pct=5.0)
        self.engine = TradingEngine(self.mock_skill, wallet, trading)

    def test_position_size_buy(self):
        self.mock_skill.get_balance.return_value = {
            "data": [{"list": {"": {"balance": "10.0"}}}]
        }
        result = make_debate_result(signal=Signal.BUY, size_pct=3.0)
        size = self.engine.calculate_position_size(result)
        # 10 SOL * 3% * 0.7 (BUY multiplier) = 0.21
        self.assertAlmostEqual(size, 0.21, places=2)

    def test_position_size_strong_buy(self):
        self.mock_skill.get_balance.return_value = {
            "data": [{"list": {"": {"balance": "10.0"}}}]
        }
        result = make_debate_result(signal=Signal.STRONG_BUY, size_pct=5.0)
        size = self.engine.calculate_position_size(result)
        # 10 SOL * 5% * 1.0 (STRONG_BUY) = 0.5
        self.assertAlmostEqual(size, 0.5, places=2)

    def test_position_size_hold_returns_zero(self):
        self.mock_skill.get_balance.return_value = {
            "data": [{"list": {"": {"balance": "10.0"}}}]
        }
        result = make_debate_result(signal=Signal.HOLD, size_pct=3.0)
        size = self.engine.calculate_position_size(result)
        self.assertEqual(size, 0.0)

    def test_position_size_capped(self):
        self.mock_skill.get_balance.return_value = {
            "data": [{"list": {"": {"balance": "10.0"}}}]
        }
        result = make_debate_result(signal=Signal.STRONG_BUY, size_pct=20.0)
        size = self.engine.calculate_position_size(result)
        # Capped at 5% (config max) → 10 * 5% * 1.0 = 0.5
        self.assertAlmostEqual(size, 0.5, places=2)

    def test_position_size_no_balance(self):
        self.mock_skill.get_balance.return_value = {"data": []}
        result = make_debate_result()
        size = self.engine.calculate_position_size(result)
        self.assertEqual(size, 0.0)


class TestStats(unittest.TestCase):
    def test_initial_stats(self):
        mock_skill = MagicMock()
        wallet = WalletConfig()
        trading = TradingConfig()
        engine = TradingEngine(mock_skill, wallet, trading)
        stats = engine.get_stats()
        self.assertEqual(stats["total_trades"], 0)
        self.assertEqual(stats["win_rate"], 0)
        self.assertEqual(stats["total_pnl_sol"], 0)


class TestCheckPositions(unittest.TestCase):
    def setUp(self):
        self.mock_skill = MagicMock()
        wallet = WalletConfig(private_key="test", address="addr123")
        trading = TradingConfig(stop_loss_pct=15, take_profit_1_pct=30)
        self.engine = TradingEngine(self.mock_skill, wallet, trading)

    def test_no_positions(self):
        actions = self.engine.check_positions()
        self.assertEqual(len(actions), 0)


if __name__ == "__main__":
    unittest.main()
