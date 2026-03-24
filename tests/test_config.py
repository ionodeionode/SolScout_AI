"""Tests for config module."""

import os
import sys
import unittest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestLLMConfig(unittest.TestCase):
    def test_defaults(self):
        from config.settings import LLMConfig
        c = LLMConfig()
        self.assertEqual(c.api_key, "")
        self.assertEqual(c.model, "qwen-max")
        self.assertIn("dashscope", c.base_url)

    def test_from_env(self):
        from config.settings import LLMConfig
        os.environ["QWEN_API_KEY"] = "test-key-123"
        os.environ["QWEN_MODEL"] = "qwen-turbo"
        c = LLMConfig.from_env()
        self.assertEqual(c.api_key, "test-key-123")
        self.assertEqual(c.model, "qwen-turbo")
        # cleanup
        del os.environ["QWEN_API_KEY"]
        del os.environ["QWEN_MODEL"]


class TestTradingConfig(unittest.TestCase):
    def test_defaults(self):
        from config.settings import TradingConfig
        c = TradingConfig()
        self.assertEqual(c.max_position_pct, 5.0)
        self.assertEqual(c.stop_loss_pct, 15.0)
        self.assertEqual(c.min_holders, 50)

    def test_from_env(self):
        from config.settings import TradingConfig
        os.environ["MAX_POSITION_PCT"] = "3"
        os.environ["STOP_LOSS"] = "20"
        c = TradingConfig.from_env()
        self.assertEqual(c.max_position_pct, 3.0)
        self.assertEqual(c.stop_loss_pct, 20.0)
        del os.environ["MAX_POSITION_PCT"]
        del os.environ["STOP_LOSS"]


class TestTwitterConfig(unittest.TestCase):
    def test_is_configured_false(self):
        from config.settings import TwitterConfig
        c = TwitterConfig()
        self.assertFalse(c.is_configured)

    def test_is_configured_true(self):
        from config.settings import TwitterConfig
        c = TwitterConfig(api_key="a", api_secret="b", access_token="c", access_secret="d")
        self.assertTrue(c.is_configured)


class TestAppConfig(unittest.TestCase):
    def test_from_env(self):
        from config.settings import AppConfig
        c = AppConfig.from_env()
        self.assertIsNotNone(c.llm)
        self.assertIsNotNone(c.wallet)
        self.assertIsNotNone(c.trading)
        self.assertIsNotNone(c.twitter)


if __name__ == "__main__":
    unittest.main()
