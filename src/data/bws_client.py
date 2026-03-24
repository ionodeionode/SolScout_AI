"""SolScout AI — Bitget Wallet Skill Wrapper

Thin async-friendly wrapper around bitget_agent_api.py functions.
Provides clean Python interface for all market data + swap operations.
"""

from __future__ import annotations

import sys
import os
import logging
from typing import Optional

# Add vendor BWS scripts to path
BWS_SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "bitget-wallet-skill", "scripts")
sys.path.insert(0, os.path.abspath(BWS_SCRIPTS))

import bitget_agent_api as bws

logger = logging.getLogger("solscout.bws")


class BitgetWalletSkill:
    """Clean wrapper for Bitget Wallet Skill API."""

    # ── Market Data ──────────────────────────────────────────────

    def token_info(self, chain: str, contract: str) -> dict:
        """Get token base info (name, symbol, price, market_cap, etc.)."""
        return bws.token_info(chain, contract)

    def token_price(self, chain: str, contract: str) -> dict:
        """Get simplified token price."""
        return bws.token_price(chain, contract)

    def batch_token_info(self, tokens: list[dict]) -> dict:
        """Batch get token info. tokens: [{"chain": "sol", "contract": "..."}]"""
        return bws.batch_token_info(tokens)

    def kline(self, chain: str, contract: str, period: str = "15m", size: int = 48) -> dict:
        """Get K-line OHLC data. period: 1m,5m,15m,30m,1h,4h,1d"""
        return bws.kline(chain, contract, period, size)

    def tx_info(self, chain: str, contract: str) -> dict:
        """Get recent transaction stats (buy/sell volume, counts)."""
        return bws.tx_info(chain, contract)

    def market_info(self, chain: str, contract: str) -> dict:
        """Get full market info: price, mcap, fdv, liquidity, holders, price changes, pools."""
        return bws.coin_market_info(chain, contract)

    def dev_analysis(self, chain: str, contract: str) -> dict:
        """Get dev analysis: dev's history, rug status, migration info."""
        return bws.coin_dev(chain, contract)

    def security_audit(self, chain: str, contract: str) -> dict:
        """Security audit: highRisk, riskCount, buyTax, sellTax, etc."""
        return bws.security(chain, contract)

    def liquidity_pools(self, chain: str, contract: str) -> dict:
        """Get liquidity pool info."""
        return bws.liquidity(chain, contract)

    def rankings(self, name: str = "topGainers") -> dict:
        """Get token rankings. Options: topGainers, topLosers, Hotpicks."""
        return bws.rankings(name)

    def search_tokens(self, keyword: str, chain: str = "sol") -> dict:
        """Search tokens by keyword or contract address."""
        return bws.search_tokens(keyword, chain)

    # ── Launchpad / New Tokens ───────────────────────────────────

    def scan_launchpad(
        self,
        chain: str = "sol",
        platforms: list[str] | None = None,
        stage: int | None = None,
        mc_min: int | None = None,
        mc_max: int | None = None,
        lp_min: int | None = None,
        holder_min: int | None = None,
        limit: int = 50,
    ) -> dict:
        """
        Scan launchpad for new tokens.
        
        platforms (sol): pump.fun, raydium.Launchlab, trends.fun, etc.
        stage: 0=new, 1=launching, 2=launched
        """
        return bws.launchpad_tokens(
            chain=chain,
            platforms=platforms,
            stage=stage,
            mc_min=mc_min,
            mc_max=mc_max,
            lp_min=lp_min,
            holder_min=holder_min,
            limit=limit,
        )

    # ── Wallet / Balance ─────────────────────────────────────────

    def get_balance(self, chain: str, address: str, contracts: list[str] | None = None) -> dict:
        """Get on-chain balance for an address."""
        items = [{"chain": chain, "address": address, "contract": contracts or [""]}]
        return bws.get_processed_balance(items)

    def get_portfolio(self, chain: str, address: str) -> dict:
        """Get portfolio with balances and prices."""
        items = [{"chain": chain, "address": address, "contract": [""]}]
        return bws.batch_v2(items)

    # ── Trading (Swap Flow) ──────────────────────────────────────

    def swap_quote(
        self,
        from_address: str,
        from_chain: str,
        from_symbol: str,
        from_contract: str,
        from_amount: str,
        to_chain: str,
        to_symbol: str,
        to_contract: str = "",
    ) -> dict:
        """Step 1: Get multi-market swap quotes."""
        result = bws.quote(
            from_address=from_address,
            from_chain=from_chain,
            from_symbol=from_symbol,
            from_contract=from_contract,
            from_amount=from_amount,
            to_chain=to_chain,
            to_symbol=to_symbol,
            to_contract=to_contract,
        )
        return bws.simplify_quote_response(result)

    def swap_confirm(
        self,
        from_chain: str, from_symbol: str, from_contract: str, from_amount: str, from_address: str,
        to_chain: str, to_symbol: str, to_contract: str, to_address: str,
        market: str, protocol: str, slippage: str = "0.01",
        features: list[str] | None = None,
    ) -> dict:
        """Step 2: Confirm quote, get orderId."""
        return bws.confirm(
            from_chain=from_chain, from_symbol=from_symbol, from_contract=from_contract,
            from_amount=from_amount, from_address=from_address,
            to_chain=to_chain, to_symbol=to_symbol, to_contract=to_contract,
            to_address=to_address,
            market=market, protocol=protocol, slippage=slippage,
            features=features or ["user_gas"],
        )

    def swap_make_order(
        self,
        order_id: str,
        from_chain: str, from_contract: str, from_symbol: str, from_address: str,
        to_chain: str, to_contract: str, to_symbol: str, to_address: str,
        from_amount: str, slippage: str, market: str, protocol: str,
    ) -> dict:
        """Step 3: Create order, get unsigned tx data."""
        return bws.make_order(
            order_id=order_id,
            from_chain=from_chain, from_contract=from_contract,
            from_symbol=from_symbol, from_address=from_address,
            to_chain=to_chain, to_contract=to_contract,
            to_symbol=to_symbol, to_address=to_address,
            from_amount=from_amount, slippage=slippage,
            market=market, protocol=protocol,
        )

    def swap_send(self, order_id: str, txs: list[dict]) -> dict:
        """Step 4: Submit signed order."""
        return bws.send(order_id=order_id, txs=txs)

    def swap_status(self, order_id: str) -> dict:
        """Step 5: Check order status."""
        return bws.get_order_details(order_id)

    def check_token_risk(self, chain: str, contract: str, symbol: str) -> dict:
        """Check if a token has trading risks (honeypot, forbidden-buy, etc.)."""
        return bws.check_swap_token([{"chain": chain, "contract": contract, "symbol": symbol}])
