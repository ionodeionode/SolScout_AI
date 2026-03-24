"""SolScout AI — Configuration"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-max"

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.getenv("QWEN_API_KEY", ""),
            base_url=os.getenv("QWEN_BASE_URL", cls.base_url),
            model=os.getenv("QWEN_MODEL", cls.model),
        )


@dataclass
class WalletConfig:
    private_key: str = ""
    address: str = ""

    @classmethod
    def from_env(cls):
        return cls(
            private_key=os.getenv("SOLANA_PRIVATE_KEY", ""),
            address=os.getenv("SOLANA_WALLET_ADDRESS", ""),
        )


@dataclass
class TradingConfig:
    max_position_pct: float = 15.0       # Max % of SOL balance per trade
    take_profit_1_pct: float = 25.0      # TP1: sell 50% at this % gain
    take_profit_2_pct: float = 50.0      # TP2: sell remaining at this % gain
    stop_loss_pct: float = 20.0          # SL: exit at this % loss
    min_trade_sol: float = 0.1           # Min trade size (avoid fee-eaten micro trades)
    slippage_pct: float = 15.0           # Slippage tolerance for memecoin swaps
    min_liquidity_usd: float = 5000.0    # Min liquidity to consider a token
    min_holders: int = 50                # Min holders to consider a token
    scan_interval_seconds: int = 120     # Seconds between scan cycles

    @classmethod
    def from_env(cls):
        return cls(
            max_position_pct=float(os.getenv("MAX_POSITION_PCT", "15")),
            take_profit_1_pct=float(os.getenv("TAKE_PROFIT_1", "25")),
            take_profit_2_pct=float(os.getenv("TAKE_PROFIT_2", "50")),
            stop_loss_pct=float(os.getenv("STOP_LOSS", "20")),
            min_trade_sol=float(os.getenv("MIN_TRADE_SOL", "0.1")),
            slippage_pct=float(os.getenv("SLIPPAGE_PCT", "15")),
            min_liquidity_usd=float(os.getenv("MIN_LIQUIDITY_USD", "5000")),
            min_holders=int(os.getenv("MIN_HOLDERS", "50")),
            scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "120")),
        )


@dataclass
class TwitterConfig:
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    access_secret: str = ""

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.getenv("X_API_KEY", ""),
            api_secret=os.getenv("X_API_SECRET", ""),
            access_token=os.getenv("X_ACCESS_TOKEN", ""),
            access_secret=os.getenv("X_ACCESS_SECRET", ""),
        )

    @property
    def is_configured(self) -> bool:
        return all([self.api_key, self.api_secret, self.access_token, self.access_secret])


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    wallet: WalletConfig = field(default_factory=WalletConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    twitter: TwitterConfig = field(default_factory=TwitterConfig)

    @classmethod
    def from_env(cls):
        return cls(
            llm=LLMConfig.from_env(),
            wallet=WalletConfig.from_env(),
            trading=TradingConfig.from_env(),
            twitter=TwitterConfig.from_env(),
        )
