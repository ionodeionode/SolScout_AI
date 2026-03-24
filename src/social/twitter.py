"""SolScout AI — X/Twitter Integration

Posts trading debates and reports to X/Twitter.
Uses tweepy for OAuth1.0a authentication.
Falls back to console-only output if not configured.
"""

from __future__ import annotations

import logging
from config.settings import TwitterConfig

logger = logging.getLogger("solscout.twitter")


class TwitterClient:
    """Handles posting to X/Twitter."""

    def __init__(self, config: TwitterConfig):
        self.config = config
        self.client = None
        self.enabled = False

        if config.is_configured:
            try:
                import tweepy
                self.client = tweepy.Client(
                    consumer_key=config.api_key,
                    consumer_secret=config.api_secret,
                    access_token=config.access_token,
                    access_token_secret=config.access_secret,
                )
                self.enabled = True
                logger.info("✅ X/Twitter client initialized")
            except ImportError:
                logger.warning("tweepy not installed. Run: pip install tweepy")
            except Exception as e:
                logger.error(f"Twitter init failed: {e}")
        else:
            logger.info("X/Twitter not configured — running in console-only mode")

    def post_tweet(self, text: str) -> dict | None:
        """Post a single tweet. Returns tweet data or None."""
        if not self.enabled:
            logger.info(f"[CONSOLE] Would post: {text[:80]}...")
            return {"id": "console", "text": text}

        try:
            # Truncate to 280 chars
            if len(text) > 280:
                text = text[:277] + "..."

            response = self.client.create_tweet(text=text)
            tweet_id = response.data["id"]
            logger.info(f"✅ Posted tweet: {tweet_id}")
            return {"id": tweet_id, "text": text}
        except Exception as e:
            logger.error(f"Tweet failed: {e}")
            return None

    def post_thread(self, tweets: list[str]) -> list[dict]:
        """Post a thread (chain of replies)."""
        results = []
        reply_to_id = None

        for i, tweet_text in enumerate(tweets):
            if not self.enabled:
                logger.info(f"[CONSOLE] Thread [{i+1}/{len(tweets)}]: {tweet_text[:60]}...")
                results.append({"id": f"console_{i}", "text": tweet_text})
                continue

            try:
                if len(tweet_text) > 280:
                    tweet_text = tweet_text[:277] + "..."

                kwargs = {"text": tweet_text}
                if reply_to_id:
                    kwargs["in_reply_to_tweet_id"] = reply_to_id

                response = self.client.create_tweet(**kwargs)
                tweet_id = response.data["id"]
                reply_to_id = tweet_id
                results.append({"id": tweet_id, "text": tweet_text})
                logger.info(f"✅ Thread [{i+1}/{len(tweets)}] posted: {tweet_id}")
            except Exception as e:
                logger.error(f"Thread tweet [{i+1}] failed: {e}")
                results.append({"id": None, "text": tweet_text, "error": str(e)})

        return results

    def post_debate_result(self, tweets: list[str]) -> list[dict]:
        """Post a debate narration thread."""
        if not tweets:
            return []
        
        logger.info(f"📢 Posting debate thread ({len(tweets)} tweets)")
        return self.post_thread(tweets)
