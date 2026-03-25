"""SolScout AI — Trading Engine

Executes trades via Bitget Wallet Skill based on debate results.
Manages portfolio, position sizing, and TP/SL tracking.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

from config.settings import TradingConfig, WalletConfig
from src.data.bws_client import BitgetWalletSkill
from src.agent.debate import DebateResult, Signal

logger = logging.getLogger("solscout.trader")

# SOL native token (empty contract = native)
SOL_CONTRACT = ""
SOL_SYMBOL = "SOL"


@dataclass
class Position:
    """An active trading position."""
    token_contract: str
    token_symbol: str
    chain: str
    entry_price: float
    amount: float  # Token amount
    sol_spent: float  # SOL used to buy
    entry_time: str
    order_id: str = ""
    status: str = "open"  # open, partial_tp, closed
    current_price: float = 0.0
    pnl_pct: float = 0.0
    debate_signal: str = ""


@dataclass
class TradeLog:
    """Record of a completed trade."""
    token_symbol: str
    token_contract: str
    action: str  # BUY, SELL, TP1, TP2, SL
    amount: float
    price: float
    sol_amount: float
    pnl_pct: float
    timestamp: str
    order_id: str = ""
    debate_signal: str = ""
    reasoning: str = ""


class TradingEngine:
    """Manages trading operations via Bitget Wallet Skill."""

    POSITIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "positions.json")

    def __init__(self, skill: BitgetWalletSkill, wallet: WalletConfig, trading: TradingConfig):
        self.skill = skill
        self.wallet = wallet
        self.config = trading
        self.positions: dict[str, Position] = {}  # contract -> Position
        self.trade_history: list[TradeLog] = []
        self.total_pnl_sol: float = 0.0
        self._load_positions()

    def _load_positions(self):
        """Load open positions from disk."""
        try:
            path = os.path.abspath(self.POSITIONS_FILE)
            if os.path.exists(path):
                with open(path, "r") as f:
                    saved = json.load(f)
                for contract, data in saved.items():
                    self.positions[contract] = Position(**data)
                logger.info(f"Loaded {len(self.positions)} open position(s) from disk")
        except Exception as e:
            logger.warning(f"Failed to load positions: {e}")

    def save_positions(self):
        """Save open positions to disk."""
        try:
            path = os.path.abspath(self.POSITIONS_FILE)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {}
            for contract, pos in self.positions.items():
                data[contract] = {
                    "token_contract": pos.token_contract,
                    "token_symbol": pos.token_symbol,
                    "chain": pos.chain,
                    "entry_price": pos.entry_price,
                    "amount": pos.amount,
                    "sol_spent": pos.sol_spent,
                    "entry_time": pos.entry_time,
                    "order_id": pos.order_id,
                    "status": pos.status,
                    "current_price": pos.current_price,
                    "pnl_pct": pos.pnl_pct,
                    "debate_signal": pos.debate_signal,
                }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(data)} position(s)")
        except Exception as e:
            logger.warning(f"Failed to save positions: {e}")

    # ── Portfolio Info ────────────────────────────────────────────

    def get_sol_balance(self) -> float:
        """Get current SOL balance."""
        try:
            result = self.skill.get_balance("sol", self.wallet.address)
            data = result.get("data", {})
            if isinstance(data, list) and len(data) > 0:
                balances = data[0].get("list", {})
                sol_balance = balances.get("", {}).get("balance", 0)
                return float(sol_balance)
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get SOL balance: {e}")
            return 0.0

    def calculate_position_size(self, debate_result: DebateResult) -> float:
        """Calculate SOL amount to trade based on debate recommendation."""
        sol_balance = self.get_sol_balance()
        if sol_balance <= 0:
            logger.warning("No SOL balance available")
            return 0.0

        # Use debate's recommended size, capped by config
        recommended_pct = min(debate_result.recommended_size_pct, self.config.max_position_pct)

        # Adjust by signal strength
        multiplier = {
            Signal.STRONG_BUY: 1.0,
            Signal.BUY: 0.7,
            Signal.HOLD: 0.0,
            Signal.SELL: 0.0,
            Signal.STRONG_SELL: 0.0,
        }.get(debate_result.final_signal, 0.0)

        sol_amount = sol_balance * (recommended_pct / 100) * multiplier

        # Minimum trade size (avoid fee-eaten micro trades)
        min_trade = self.config.min_trade_sol
        if sol_amount < min_trade:
            logger.info(f"Trade size {sol_amount:.4f} SOL below minimum {min_trade} SOL — skipping")
            return 0.0

        logger.info(
            f"Position size: {sol_amount:.4f} SOL "
            f"({recommended_pct:.1f}% × {multiplier:.0%} of {sol_balance:.4f} SOL)"
        )
        return round(sol_amount, 4)

    # ── Execute Trade ─────────────────────────────────────────────

    def execute_buy(self, debate_result: DebateResult) -> TradeLog | None:
        """Execute a BUY trade based on debate result."""
        token = debate_result.token
        sol_amount = self.calculate_position_size(debate_result)

        if sol_amount <= 0:
            logger.info(f"Skipping buy for ${token.symbol} — position size is 0")
            return None

        if token.contract in self.positions:
            logger.info(f"Already have position in ${token.symbol}")
            return None

        logger.info(f"🟢 BUYING ${token.symbol} with {sol_amount} SOL")

        try:
            # Use config slippage (convert % to decimal string)
            slippage_str = str(self.config.slippage_pct / 100)

            # Step 1: Get quote
            quote_result = self.skill.swap_quote(
                from_address=self.wallet.address,
                from_chain="sol",
                from_symbol=SOL_SYMBOL,
                from_contract=SOL_CONTRACT,
                from_amount=str(sol_amount),
                to_chain="sol",
                to_symbol=token.symbol,
                to_contract=token.contract,
            )

            data = quote_result.get("data", {})
            quotes = data.get("quoteResults", [])
            if not quotes:
                logger.error(f"No quotes returned for ${token.symbol}")
                return None

            # Pick best quote (first one)
            best = quotes[0]
            market = best.get("market", {})
            market_id = market.get("id", "")
            protocol = market.get("protocol", "")
            out_amount = float(best.get("outAmount", 0))
            # Use recommended slippage from quote, fallback to config
            slippage = best.get("slippageInfo", {}).get("recommendSlippage", slippage_str)

            logger.info(
                f"Quote: {sol_amount} SOL → {out_amount} {token.symbol} "
                f"via {market.get('label', market_id)}"
            )

            # Step 2: Confirm
            confirm_result = self.skill.swap_confirm(
                from_chain="sol", from_symbol=SOL_SYMBOL,
                from_contract=SOL_CONTRACT, from_amount=str(sol_amount),
                from_address=self.wallet.address,
                to_chain="sol", to_symbol=token.symbol,
                to_contract=token.contract, to_address=self.wallet.address,
                market=market_id, protocol=protocol, slippage=slippage,
            )

            order_id = confirm_result.get("data", {}).get("orderId", "")
            if not order_id:
                logger.error(f"No orderId from confirm: {json.dumps(confirm_result)[:200]}")
                return None

            logger.info(f"Confirmed order: {order_id}")

            # Step 3: Make order (get unsigned tx)
            make_result = self.skill.swap_make_order(
                order_id=order_id,
                from_chain="sol", from_contract=SOL_CONTRACT,
                from_symbol=SOL_SYMBOL, from_address=self.wallet.address,
                to_chain="sol", to_contract=token.contract,
                to_symbol=token.symbol, to_address=self.wallet.address,
                from_amount=str(sol_amount), slippage=slippage,
                market=market_id, protocol=protocol,
            )

            txs = make_result.get("data", {}).get("txs", [])
            if not txs:
                logger.error(f"No txs from makeOrder")
                return None

            # Step 4: Sign transaction
            # NOTE: Signing requires private key — uses order_sign.py
            signed_txs = self._sign_transactions(txs)
            if not signed_txs:
                logger.error("Transaction signing failed")
                return None

            # Step 5: Send
            send_result = self.skill.swap_send(order_id, signed_txs)
            logger.info(f"Send result: {json.dumps(send_result)[:200]}")

            # Step 6: Track position
            position = Position(
                token_contract=token.contract,
                token_symbol=token.symbol,
                chain="sol",
                entry_price=token.price,
                amount=out_amount,
                sol_spent=sol_amount,
                entry_time=datetime.utcnow().isoformat(),
                order_id=order_id,
                debate_signal=debate_result.final_signal.name,
            )
            self.positions[token.contract] = position
            self.save_positions()

            trade_log = TradeLog(
                token_symbol=token.symbol,
                token_contract=token.contract,
                action="BUY",
                amount=out_amount,
                price=token.price,
                sol_amount=sol_amount,
                pnl_pct=0.0,
                timestamp=datetime.utcnow().isoformat(),
                order_id=order_id,
                debate_signal=debate_result.final_signal.name,
                reasoning=debate_result.judge_reasoning[:200],
            )
            self.trade_history.append(trade_log)

            logger.info(f"✅ BUY complete: {sol_amount} SOL → {out_amount} ${token.symbol}")
            return trade_log

        except Exception as e:
            logger.error(f"Buy execution failed for ${token.symbol}: {e}")
            return None

    def check_positions(self) -> list[TradeLog]:
        """Check all positions for TP/SL triggers."""
        actions = []

        for contract, pos in list(self.positions.items()):
            if pos.status == "closed":
                continue

            try:
                price_data = self.skill.token_price(pos.chain, contract)
                current_price = float(price_data.get("price", 0))
                if current_price <= 0:
                    continue

                pos.current_price = current_price
                pos.pnl_pct = ((current_price - pos.entry_price) / pos.entry_price) * 100

                # Stop Loss
                if pos.pnl_pct <= -self.config.stop_loss_pct:
                    logger.warning(f"🔴 STOP LOSS ${pos.token_symbol}: {pos.pnl_pct:.1f}%")
                    trade = self._execute_sell(pos, "SL", 1.0)
                    if trade:
                        actions.append(trade)

                # Take Profit 1  (sell 50%)
                elif pos.pnl_pct >= self.config.take_profit_1_pct and pos.status == "open":
                    logger.info(f"🟡 TP1 ${pos.token_symbol}: {pos.pnl_pct:.1f}%")
                    trade = self._execute_sell(pos, "TP1", 0.5)
                    if trade:
                        pos.status = "partial_tp"
                        actions.append(trade)

                # Take Profit 2 (sell remaining)
                elif pos.pnl_pct >= self.config.take_profit_2_pct and pos.status == "partial_tp":
                    logger.info(f"🟢 TP2 ${pos.token_symbol}: {pos.pnl_pct:.1f}%")
                    trade = self._execute_sell(pos, "TP2", 1.0)
                    if trade:
                        actions.append(trade)

            except Exception as e:
                logger.error(f"Position check failed for {pos.token_symbol}: {e}")

        return actions

    def _execute_sell(self, pos: Position, reason: str, fraction: float) -> TradeLog | None:
        """Execute a sell of fraction of a position."""
        sell_amount = pos.amount * fraction

        logger.info(f"{'🔴' if reason == 'SL' else '🟢'} SELLING {sell_amount} ${pos.token_symbol} ({reason})")

        try:
            # Use config slippage (convert % to decimal string)
            slippage_str = str(self.config.slippage_pct / 100)

            # Step 1: Get quote
            quote_result = self.skill.swap_quote(
                from_address=self.wallet.address,
                from_chain="sol",
                from_symbol=pos.token_symbol,
                from_contract=pos.token_contract,
                from_amount=str(sell_amount),
                to_chain="sol",
                to_symbol=SOL_SYMBOL,
                to_contract=SOL_CONTRACT,
            )

            data = quote_result.get("data", {})
            quotes = data.get("quoteResults", [])
            if not quotes:
                logger.error(f"No sell quotes for ${pos.token_symbol}")
                return None

            best = quotes[0]
            market = best.get("market", {})
            market_id = market.get("id", "")
            protocol = market.get("protocol", "")
            sol_received = float(best.get("outAmount", 0))
            # Use recommended slippage from quote, fallback to config
            slippage = best.get("slippageInfo", {}).get("recommendSlippage", slippage_str)

            logger.info(
                f"Sell quote: {sell_amount} {pos.token_symbol} → {sol_received} SOL "
                f"via {market.get('label', market_id)}"
            )

            # Step 2: Confirm
            confirm_result = self.skill.swap_confirm(
                from_chain="sol", from_symbol=pos.token_symbol,
                from_contract=pos.token_contract, from_amount=str(sell_amount),
                from_address=self.wallet.address,
                to_chain="sol", to_symbol=SOL_SYMBOL,
                to_contract=SOL_CONTRACT, to_address=self.wallet.address,
                market=market_id, protocol=protocol, slippage=slippage,
            )

            order_id = confirm_result.get("data", {}).get("orderId", "")
            if not order_id:
                logger.error(f"No orderId from sell confirm: {json.dumps(confirm_result)[:200]}")
                return None

            logger.info(f"Sell confirmed order: {order_id}")

            # Step 3: Make order (get unsigned tx)
            make_result = self.skill.swap_make_order(
                order_id=order_id,
                from_chain="sol", from_contract=pos.token_contract,
                from_symbol=pos.token_symbol, from_address=self.wallet.address,
                to_chain="sol", to_contract=SOL_CONTRACT,
                to_symbol=SOL_SYMBOL, to_address=self.wallet.address,
                from_amount=str(sell_amount), slippage=slippage,
                market=market_id, protocol=protocol,
            )

            txs = make_result.get("data", {}).get("txs", [])
            if not txs:
                logger.error(f"No txs from sell makeOrder")
                return None

            # Step 4: Sign transaction
            signed_txs = self._sign_transactions(txs)
            if not signed_txs:
                logger.error("Sell transaction signing failed")
                return None

            # Step 5: Send
            send_result = self.skill.swap_send(order_id, signed_txs)
            logger.info(f"Sell send result: {json.dumps(send_result)[:200]}")

            # Calculate PnL
            sol_cost = pos.sol_spent * fraction
            pnl_sol = sol_received - sol_cost
            self.total_pnl_sol += pnl_sol

            # Update position
            pos.amount -= sell_amount
            if pos.amount <= 0.001 or fraction >= 1.0:
                pos.status = "closed"
                del self.positions[pos.token_contract]
            self.save_positions()

            trade = TradeLog(
                token_symbol=pos.token_symbol,
                token_contract=pos.token_contract,
                action=reason,
                amount=sell_amount,
                price=pos.current_price,
                sol_amount=sol_received,
                pnl_pct=pos.pnl_pct,
                timestamp=datetime.utcnow().isoformat(),
                order_id=order_id,
                reasoning=f"{reason}: PnL {pos.pnl_pct:+.1f}% | {pnl_sol:+.4f} SOL",
            )
            self.trade_history.append(trade)

            logger.info(f"✅ SELL complete: {sell_amount} ${pos.token_symbol} → {sol_received} SOL (PnL: {pnl_sol:+.4f} SOL)")
            return trade

        except Exception as e:
            logger.error(f"Sell failed for ${pos.token_symbol}: {e}")
            return None

    def _sign_transactions(self, txs: list[dict]) -> list[dict] | None:
        """Sign transactions using order_sign.py logic."""
        if not self.wallet.private_key:
            logger.error("No private key configured — cannot sign")
            return None

        try:
            import sys, os
            bws_scripts = os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "bitget-wallet-skill", "scripts")
            sys.path.insert(0, os.path.abspath(bws_scripts))
            from order_sign import sign_order_txs_solana

            # sign_order_txs_solana expects {"txs": [...]} and returns list of signed base58 strings
            order_data = {"txs": txs}
            signed_b58_list = sign_order_txs_solana(order_data, self.wallet.private_key)

            # Set sig field on each tx item for the send API
            for i, sig in enumerate(signed_b58_list):
                txs[i]["sig"] = sig

            logger.info(f"Signed {len(signed_b58_list)} transaction(s)")
            return txs
        except ImportError as e:
            logger.error(f"order_sign.py import failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Signing error: {e}")
            return None

    # ── Stats ─────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get trading statistics."""
        total_trades = len(self.trade_history)
        buys = [t for t in self.trade_history if t.action == "BUY"]
        sells = [t for t in self.trade_history if t.action != "BUY"]
        wins = [t for t in sells if t.pnl_pct > 0]

        return {
            "total_trades": total_trades,
            "open_positions": len(self.positions),
            "total_buys": len(buys),
            "total_sells": len(sells),
            "wins": len(wins),
            "losses": len(sells) - len(wins),
            "win_rate": len(wins) / max(len(sells), 1),
            "total_pnl_sol": round(self.total_pnl_sol, 4),
        }
