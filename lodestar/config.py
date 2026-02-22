"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class RobinhoodSettings(BaseSettings):
    username: str = ""
    password: str = ""
    mfa_code: str = ""
    totp_secret: str = ""

    model_config = {"env_prefix": "ROBINHOOD_"}


class TradingSettings(BaseSettings):
    mode: str = Field(default="paper", pattern="^(paper|live)$")
    max_position_pct: float = 0.05
    max_daily_trades: int = 20
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.08
    interval_minutes: int = 15

    model_config = {"env_prefix": "TRADING_"}


class StrategySettings(BaseSettings):
    enabled_strategies: str = "momentum,mean_reversion,sentiment"

    @property
    def enabled_list(self) -> list[str]:
        return [s.strip() for s in self.enabled_strategies.split(",") if s.strip()]

    model_config = {"env_prefix": ""}


class DashboardSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_prefix": "DASHBOARD_"}


class Settings(BaseSettings):
    robinhood: RobinhoodSettings = Field(default_factory=RobinhoodSettings)
    trading: TradingSettings = Field(default_factory=TradingSettings)
    strategies: StrategySettings = Field(default_factory=StrategySettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)
    news_api_key: str = ""

    model_config = {"env_prefix": ""}


def load_settings() -> Settings:
    """Load settings from environment / .env file."""
    from dotenv import load_dotenv

    load_dotenv()
    return Settings()
