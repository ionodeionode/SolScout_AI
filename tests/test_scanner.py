"""Tests for the Token Scanner module."""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.scanner import TokenCandidate, TokenScanner


class TestTokenCandidate(unittest.TestCase):
    def test_has_socials_true(self):
        c = TokenCandidate(
            chain="sol", contract="abc", symbol="TEST", name="Test",
            socials={"twitter": "https://x.com/test"},
        )
        self.assertTrue(c.has_socials)

    def test_has_socials_false(self):
        c = TokenCandidate(chain="sol", contract="abc", symbol="TEST", name="Test")
        self.assertFalse(c.has_socials)


class TestTokenScanner(unittest.TestCase):
    def setUp(self):
        self.mock_skill = MagicMock()
        self.scanner = TokenScanner(self.mock_skill, min_liquidity=5000, min_holders=50)

    def test_quick_filter_pass(self):
        c = TokenCandidate(
            chain="sol", contract="abc", symbol="TEST", name="Test",
            liquidity=10000, holders=100,
        )
        passed, reason = self.scanner.quick_filter(c)
        self.assertTrue(passed)
        self.assertEqual(reason, "PASS")

    def test_quick_filter_low_liquidity(self):
        c = TokenCandidate(
            chain="sol", contract="abc", symbol="TEST", name="Test",
            liquidity=1000, holders=100,
        )
        passed, reason = self.scanner.quick_filter(c)
        self.assertFalse(passed)
        self.assertIn("Liquidity", reason)

    def test_quick_filter_high_risk(self):
        c = TokenCandidate(
            chain="sol", contract="abc", symbol="TEST", name="Test",
            liquidity=10000, holders=100,
            security={"highRisk": True},
        )
        passed, reason = self.scanner.quick_filter(c)
        self.assertFalse(passed)
        self.assertIn("HIGH RISK", reason)

    def test_quick_filter_high_sell_tax(self):
        c = TokenCandidate(
            chain="sol", contract="abc", symbol="TEST", name="Test",
            liquidity=10000, holders=100,
            security={"sellTax": 15},
        )
        passed, reason = self.scanner.quick_filter(c)
        self.assertFalse(passed)
        self.assertIn("Sell tax", reason)

    def test_quick_filter_dev_rug_history(self):
        c = TokenCandidate(
            chain="sol", contract="abc", symbol="TEST", name="Test",
            liquidity=10000, holders=100,
            dev_info={"tokens": [
                {"rug_status": 1}, {"rug_status": 1}, {"rug_status": 1},
                {"rug_status": 1}, {"rug_status": 0},
            ]},
        )
        passed, reason = self.scanner.quick_filter(c)
        self.assertFalse(passed)
        self.assertIn("rugged", reason)

    def test_deduplicate(self):
        c1 = TokenCandidate(chain="sol", contract="abc", symbol="A", name="A")
        c2 = TokenCandidate(chain="sol", contract="abc", symbol="A", name="A")
        c3 = TokenCandidate(chain="sol", contract="def", symbol="B", name="B")
        result = self.scanner._deduplicate([c1, c2, c3])
        self.assertEqual(len(result), 2)

    def test_scan_trending(self):
        self.mock_skill.rankings.return_value = {
            "data": {
                "list": [
                    {"contract": f"token{i}", "symbol": f"T{i}", "name": f"Token{i}",
                     "price": 0.01, "market_cap": 100000, "chain": "sol"}
                    for i in range(5)
                ]
            }
        }
        candidates = self.scanner.scan_trending(limit=10)
        self.assertGreater(len(candidates), 0)
        self.assertEqual(candidates[0].chain, "sol")


class TestScannerEnrich(unittest.TestCase):
    def test_enrich_updates_fields(self):
        mock_skill = MagicMock()
        mock_skill.security_audit.return_value = {"data": {"highRisk": False}}
        mock_skill.tx_info.return_value = {"data": {"buy_count": 100}}
        mock_skill.kline.return_value = {"data": {"list": [{"o": 0.01}]}}
        mock_skill.dev_analysis.return_value = {"data": {"tokens": []}}
        mock_skill.market_info.return_value = {
            "data": {"market_cap": 200000, "liquidity": 15000, "holders": 300, "price": 0.02}
        }

        scanner = TokenScanner(mock_skill)
        c = TokenCandidate(chain="sol", contract="xyz", symbol="RICH", name="RichToken")
        enriched = scanner.enrich_candidate(c)

        self.assertEqual(enriched.market_cap, 200000)
        self.assertEqual(enriched.liquidity, 15000)
        self.assertEqual(enriched.holders, 300)
        self.assertEqual(enriched.price, 0.02)
        self.assertIn("xyz", scanner.seen_tokens)


if __name__ == "__main__":
    unittest.main()
