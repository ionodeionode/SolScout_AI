"""SolScout AI — Qwen LLM Provider"""

from __future__ import annotations

import json
import logging
from openai import OpenAI

from config.settings import LLMConfig

logger = logging.getLogger("solscout.llm")


class QwenLLM:
    """Qwen LLM client using OpenAI-compatible API."""

    def __init__(self, config: LLMConfig):
        self.config = config
        import httpx
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        self.model = config.model

    def chat(self, prompt: str, system: str = "", temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """Send a chat completion request and return the response text."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content or ""
            logger.debug(f"LLM response ({len(text)} chars)")
            return text
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return f"[LLM_ERROR] {e}"

    def chat_json(self, prompt: str, system: str = "", temperature: float = 0.3) -> dict:
        """Chat and parse response as JSON. Falls back to raw text on parse failure."""
        raw = self.chat(prompt, system=system, temperature=temperature)

        # Try to extract JSON from response
        try:
            # Handle ```json ... ``` blocks
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            if "```" in raw:
                json_str = raw.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            return json.loads(raw)
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"Failed to parse LLM JSON, returning raw text")
            return {"raw": raw, "parse_error": True}
