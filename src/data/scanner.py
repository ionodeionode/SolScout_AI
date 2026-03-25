"""SolScout AI — Token Scanner

Discovers and pre-filters tokens from multiple sources using BWS.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.data.bws_client import BitgetWalletSkill

logger = logging.getLogger("solscout.scanner")


@dataclass
class TokenCandidate:
    """A token that passed initial screening."""
    chain: str
    contract: str
    symbol: str
    name: str
    price: float = 0.0
    market_cap: float = 0.0
    liquidity: float = 0.0
    holders: int = 0
    volume_24h: float = 0.0
    age_seconds: int = 0
    platform: str = ""
    socials: dict = field(default_factory=dict)
    security: dict = field(default_factory=dict)
    kline_data: list = field(default_factory=list)
    tx_stats: dict = field(default_factory=dict)
    dev_info: dict = field(default_factory=dict)
    market_data: dict = field(default_factory=dict)
    discovered_at: str = ""

    @property
    def has_socials(self) -> bool:
        return bool(self.socials.get("twitter") or self.socials.get("website"))


class TokenScanner:
    """Scans for new token opportunities using Bitget Wallet Skill."""

    def __init__(self, skill: BitgetWalletSkill, min_liquidity: float = 5000, min_holders: int = 50):
        self.skill = skill
        self.min_liquidity = min_liquidity
        self.min_holders = min_holders
        self.seen_tokens: set[str] = set()  # Track already-processed tokens

    def scan_trending(self, limit: int = 20) -> list[TokenCandidate]:
        """Scan top gainers and hot picks."""
        candidates = []
        # Reset seen tokens each scan cycle to allow re-evaluation
        self.seen_tokens.clear()

        for ranking_type in ["topGainers", "Hotpicks"]:
            try:
                result = self.skill.rankings(ranking_type)
                tokens = self._extract_tokens_from_rankings(result)
                candidates.extend(tokens)
                logger.info(f"[{ranking_type}] Found {len(tokens)} tokens")
            except Exception as e:
                logger.error(f"Rankings scan failed ({ranking_type}): {e}")

        return self._deduplicate(candidates)[:limit]

    def scan_launchpad(self, limit: int = 20) -> list[TokenCandidate]:
        """Scan launchpad for newly launched tokens with traction."""
        candidates = []

        try:
            result = self.skill.scan_launchpad(
                chain="sol",
                stage=2,  # Launched
                lp_min=int(self.min_liquidity),
                holder_min=self.min_holders,
                limit=limit,
            )
            data = result.get("data", {})
            tokens_raw = data.get("list") or data.get("tokens") or []
            if isinstance(data, list):
                tokens_raw = data

            for t in tokens_raw:
                contract = t.get("contract", "")
                if contract in self.seen_tokens:
                    continue

                candidate = TokenCandidate(
                    chain="sol",
                    contract=contract,
                    symbol=t.get("symbol", "???"),
                    name=t.get("name", ""),
                    price=float(t.get("price", 0) or 0),
                    market_cap=float(t.get("market_cap", 0) or 0),
                    liquidity=float(t.get("liquidity", 0) or 0),
                    holders=int(t.get("holders", 0) or 0),
                    platform=t.get("platform", ""),
                    socials=t.get("socials", {}),
                    discovered_at=datetime.utcnow().isoformat(),
                )
                candidates.append(candidate)

            logger.info(f"[Launchpad] Found {len(candidates)} launched tokens")
        except Exception as e:
            logger.error(f"Launchpad scan failed: {e}")

        return candidates[:limit]

    def enrich_candidate(self, candidate: TokenCandidate) -> TokenCandidate:
        """Enrich a candidate with security, tx stats, kline, dev, market data."""

        # Security audit
        try:
            sec = self.skill.security_audit(candidate.chain, candidate.contract)
            candidate.security = sec.get("data", {})
        except Exception as e:
            logger.warning(f"Security check failed for {candidate.symbol}: {e}")

        # Transaction stats
        try:
            tx = self.skill.tx_info(candidate.chain, candidate.contract)
            candidate.tx_stats = tx.get("data", {})
        except Exception as e:
            logger.warning(f"Tx info failed for {candidate.symbol}: {e}")

        # K-line data (15min candles, last 48 = 12 hours)
        try:
            kl = self.skill.kline(candidate.chain, candidate.contract, period="15m", size=48)
            candidate.kline_data = kl.get("data", {}).get("list", [])
        except Exception as e:
            logger.warning(f"Kline failed for {candidate.symbol}: {e}")

        # Dev history (rug detection)
        try:
            dev = self.skill.dev_analysis(candidate.chain, candidate.contract)
            candidate.dev_info = dev.get("data", {})
        except Exception as e:
            logger.warning(f"Dev analysis failed for {candidate.symbol}: {e}")

        # Full market info
        try:
            mkt = self.skill.market_info(candidate.chain, candidate.contract)
            mdata = mkt.get("data", {})
            candidate.market_data = mdata
            # Update fields from market info if available
            if mdata.get("market_cap"):
                candidate.market_cap = float(mdata["market_cap"])
            if mdata.get("liquidity"):
                candidate.liquidity = float(mdata["liquidity"])
            if mdata.get("holders"):
                candidate.holders = int(mdata["holders"])
            if mdata.get("price"):
                candidate.price = float(mdata["price"])
        except Exception as e:
            logger.warning(f"Market info failed for {candidate.symbol}: {e}")

        self.seen_tokens.add(candidate.contract)
        return candidate

    def quick_filter(self, candidate: TokenCandidate) -> tuple[bool, str]:
        """
        Quick safety filter before running the full debate.
        Returns (pass, reason).
        """
        # Check security
        sec = candidate.security
        if isinstance(sec, dict):
            # Check if it's in the audit response format
            audit_list = sec.get("list", [sec])
            for audit in audit_list:
                if isinstance(audit, dict):
                    if audit.get("highRisk"):
                        return False, f"HIGH RISK detected in security audit"
                    buy_tax = float(audit.get("buyTax", 0) or 0)
                    sell_tax = float(audit.get("sellTax", 0) or 0)
                    if sell_tax > 10:
                        return False, f"Sell tax too high: {sell_tax}%"
                    if buy_tax > 10:
                        return False, f"Buy tax too high: {buy_tax}%"

        # Check dev rug history
        dev = candidate.dev_info
        if isinstance(dev, dict):
            tokens = dev.get("tokens", [])
            rug_count = sum(1 for t in tokens if isinstance(t, dict) and t.get("rug_status") == 1)
            total = len(tokens)
            if total > 3 and rug_count / total > 0.5:
                return False, f"Dev has rugged {rug_count}/{total} previous tokens"

        # Check minimum liquidity
        if candidate.liquidity < self.min_liquidity:
            return False, f"Liquidity too low: ${candidate.liquidity:.0f} < ${self.min_liquidity}"

        return True, "PASS"

    # ── Helpers ───────────────────────────────────────────────────

    def _extract_tokens_from_rankings(self, result: dict) -> list[TokenCandidate]:
        candidates = []
        data = result.get("data", {})
        token_list = data.get("list") or data.get("tokens") or []
        if isinstance(data, list):
            token_list = data

        for t in token_list:
            contract = t.get("contract", "") or t.get("address", "")
            chain = t.get("chain", "sol")

            # Only trade on Solana
            if chain != "sol":
                continue

            if not contract or contract in self.seen_tokens:
                continue

            self.seen_tokens.add(contract)
            candidates.append(TokenCandidate(
                chain=chain,
                contract=contract,
                symbol=t.get("symbol", "???"),
                name=t.get("name", ""),
                price=float(t.get("price", 0) or 0),
                market_cap=float(t.get("market_cap", 0) or 0),
                liquidity=float(t.get("liquidity", 0) or 0),
                holders=int(t.get("holders", 0) or 0),
                discovered_at=datetime.utcnow().isoformat(),
            ))

        return candidates

    def _deduplicate(self, candidates: list[TokenCandidate]) -> list[TokenCandidate]:
        seen = set()
        unique = []
        for c in candidates:
            if c.contract not in seen:
                seen.add(c.contract)
                unique.append(c)
        return unique
