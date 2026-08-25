"""
Configuration Module for Trading Bot
Loads, validates, and exposes environment variables and settings.
Supports Pydantic Settings with automatic fallback to standard environment parsing.
Includes configuration for Groq AI and Telegram Bot.
"""

import os
from typing import List, Literal, Union, Optional

# Try loading from .env if python-dotenv is present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Read .env manually if dotenv library isn't available
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))

try:
    from pydantic import Field, field_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        """
        Application Settings schema loaded from environment variables and .env file via Pydantic.
        """
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore"
        )

        # --- Trading 212 API Credentials (HTTP Basic Auth) ---
        t212_api_key: str = Field(
            default="",
            description="Trading 212 API Key / Key ID"
        )
        t212_api_key_id: Optional[str] = Field(
            default="",
            description="Trading 212 API Key ID alias"
        )
        t212_secret_key: Optional[str] = Field(
            default="",
            description="Trading 212 API Secret Key"
        )
        t212_api_secret: Optional[str] = Field(
            default="",
            description="Trading 212 API Secret alias"
        )
        t212_environment: Literal["demo", "live"] = Field(
            default="demo",
            description="Trading 212 API environment: 'demo' or 'live'"
        )
        t212_max_order_value: float = Field(
            default=50.0,
            gt=0.0,
            description="Maximum cash limit allocated to a single trade order"
        )

        # --- Market Data (yfinance default / Alpha Vantage optional fallback) ---
        market_data_provider: str = Field(
            default="yfinance",
            description="Market data provider: 'yfinance' (default)"
        )
        alpha_vantage_api_key: Optional[str] = Field(
            default="",
            description="Optional Alpha Vantage API key"
        )

        # --- Groq AI Integration ---
        groq_api_key: Optional[str] = Field(
            default="",
            description="Groq Cloud API key for ultra-fast LLM analysis"
        )
        groq_model: str = Field(
            default="llama-3.3-70b-versatile",
            description="Groq AI model identifier (e.g. llama-3.3-70b-versatile, mixtral-8x7b-32768)"
        )
        # Legacy alias for backward compatibility
        openrouter_api_key: Optional[str] = Field(
            default="",
            description="Legacy fallback API key"
        )
        openrouter_model: Optional[str] = Field(
            default="llama-3.3-70b-versatile",
            description="Legacy fallback model"
        )
        enable_ai_analysis: bool = Field(
            default=True,
            description="Whether to run Groq AI analysis before executions"
        )

        # --- Crypto Exchange Configuration (Binance Demo / Futures / CCXT / Coinbase) ---
        crypto_exchange_name: str = Field(
            default="binance",
            description="Crypto exchange identifier for CCXT (default: binance)"
        )
        binance_demo_api_key: Optional[str] = Field(
            default="",
            description="Binance Demo Trading API Key"
        )
        binance_demo_secret: Optional[str] = Field(
            default="",
            description="Binance Demo Trading Secret Key"
        )
        binance_demo_enabled: bool = Field(
            default=True,
            description="Whether to route crypto orders to Binance Demo Trading environment"
        )
        binance_testnet_api_key: Optional[str] = Field(
            default="",
            description="Binance Futures Testnet API Key (Alias)"
        )
        binance_testnet_secret: Optional[str] = Field(
            default="",
            description="Binance Futures Testnet Secret Key (Alias)"
        )
        binance_testnet_enabled: bool = Field(
            default=True,
            description="Whether to route crypto futures orders to Binance Testnet"
        )
        crypto_default_type: str = Field(
            default="future",
            description="Default market type for crypto exchange (spot, future, margin)"
        )
        coinbase_api_key: Optional[str] = Field(
            default="",
            description="Coinbase API Key (CDP API Key)"
        )
        coinbase_secret_key: Optional[str] = Field(
            default="",
            description="Coinbase API Secret (Private Key)"
        )
        crypto_exchange_api_key: Optional[str] = Field(
            default="",
            description="Generic Crypto Exchange API Key fallback"
        )
        crypto_exchange_secret: Optional[str] = Field(
            default="",
            description="Generic Crypto Exchange API Secret fallback"
        )

        # --- Telegram Notifier Bot ---
        telegram_bot_token: Optional[str] = Field(
            default="",
            description="Telegram Bot API Token (from @BotFather)"
        )
        telegram_chat_id: Optional[str] = Field(
            default="",
            description="Telegram Chat ID or Group ID for real-time trade alerts"
        )
        telegram_allowed_user_id: Optional[str] = Field(
            default="",
            description="Authorized Telegram User ID for management commands"
        )
        enable_telegram_alerts: bool = Field(
            default=True,
            description="Whether to dispatch instant Telegram notifications"
        )

        # --- Obsidian Local REST API ---
        obsidian_rest_api_key: str = Field(
            default="",
            description="API token generated by the Obsidian Local REST API plugin"
        )
        obsidian_host: str = Field(
            default="127.0.0.1",
            description="Host IP/Domain running Obsidian with Local REST API"
        )
        obsidian_port: int = Field(
            default=27124,
            description="Port for Obsidian Local REST API (27124 HTTPS or 27123 HTTP)"
        )
        obsidian_use_https: bool = Field(
            default=True,
            description="Whether to connect to Obsidian REST API over HTTPS"
        )
        obsidian_verify_ssl: bool = Field(
            default=False,
            description="Whether to verify SSL certificates"
        )
        obsidian_vault_folder: str = Field(
            default="Trading-Logs",
            description="Relative path inside Obsidian vault where trade notes are written"
        )

        # --- Strategy & Execution Settings ---
        watchlist_tickers: Union[str, List[str]] = Field(
            default="AAPL_US_EQ,MSFT_US_EQ,NVDA_US_EQ",
            description="Comma-separated or list of ticker symbols to monitor and trade"
        )
        buy_allocation_value: float = Field(
            default=25.0,
            gt=0.0,
            description="Base currency amount spent per executed buy trade"
        )
        dip_threshold_percent: float = Field(
            default=2.0,
            ge=0.0,
            description="Percentage dip below SMA or target to trigger a buy signal"
        )
        sma_short_period: int = Field(
            default=10,
            gt=0,
            description="Short period Simple Moving Average in days"
        )
        sma_long_period: int = Field(
            default=50,
            gt=0,
            description="Long period Simple Moving Average in days"
        )
        check_interval_minutes: int = Field(
            default=15,
            gt=0,
            description="Interval in minutes between strategy execution runs"
        )
        dry_run: bool = Field(
            default=False,
            description="If True, runs analysis and Obsidian logging without placing broker orders"
        )

        @field_validator("watchlist_tickers", mode="after")
        @classmethod
        def parse_tickers(cls, v: Union[str, List[str]]) -> List[str]:
            if isinstance(v, str):
                return [ticker.strip().upper() for ticker in v.split(",") if ticker.strip()]
            return [ticker.strip().upper() for ticker in v if isinstance(ticker, str) and ticker.strip()]

        @property
        def effective_ai_api_key(self) -> str:
            return (self.groq_api_key or self.openrouter_api_key or "").strip()

        @property
        def effective_ai_model(self) -> str:
            return (self.groq_model or self.openrouter_model or "llama-3.3-70b-versatile").strip()

        @property
        def effective_crypto_api_key(self) -> str:
            return (self.coinbase_api_key or self.crypto_exchange_api_key or "").strip()

        @property
        def effective_crypto_secret_key(self) -> str:
            return (self.coinbase_secret_key or self.crypto_exchange_secret or "").strip()

        @property
        def effective_crypto_exchange(self) -> str:
            if self.coinbase_api_key or self.coinbase_secret_key:
                return "coinbase"
            return (self.crypto_exchange_name or "coinbase").strip().lower()

        @property
        def t212_effective_key(self) -> str:
            return (self.t212_api_key_id or self.t212_api_key or "").strip()

        @property
        def t212_effective_secret(self) -> str:
            return (self.t212_secret_key or self.t212_api_secret or "").strip()

        @property
        def t212_base_url(self) -> str:
            if self.t212_environment.lower() == "live":
                return "https://live.trading212.com/api/v0"
            return "https://demo.trading212.com/api/v0"

        @property
        def obsidian_base_url(self) -> str:
            protocol = "https" if self.obsidian_use_https else "http"
            return f"{protocol}://{self.obsidian_host}:{self.obsidian_port}"

except ImportError:
    # Standard Python Fallback if Pydantic is not installed
    class Settings:
        """
        Lightweight fallback settings container using standard library.
        """
        def __init__(self, **kwargs):
            self.t212_api_key = kwargs.get("t212_api_key", os.getenv("T212_API_KEY", ""))
            self.t212_api_key_id = kwargs.get("t212_api_key_id", os.getenv("T212_API_KEY_ID", ""))
            self.t212_secret_key = kwargs.get("t212_secret_key", os.getenv("T212_SECRET_KEY", ""))
            self.t212_api_secret = kwargs.get("t212_api_secret", os.getenv("T212_API_SECRET", ""))
            self.t212_environment = kwargs.get("t212_environment", os.getenv("T212_ENVIRONMENT", "demo")).lower()
            self.t212_max_order_value = float(kwargs.get("t212_max_order_value", os.getenv("T212_MAX_ORDER_VALUE", 50.0)))

            self.market_data_provider = kwargs.get("market_data_provider", os.getenv("MARKET_DATA_PROVIDER", "yfinance"))
            self.alpha_vantage_api_key = kwargs.get("alpha_vantage_api_key", os.getenv("ALPHA_VANTAGE_API_KEY", ""))

            self.groq_api_key = kwargs.get("groq_api_key", os.getenv("GROQ_API_KEY", ""))
            self.groq_model = kwargs.get("groq_model", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
            self.openrouter_api_key = kwargs.get("openrouter_api_key", os.getenv("OPENROUTER_API_KEY", self.groq_api_key))
            self.openrouter_model = kwargs.get("openrouter_model", os.getenv("OPENROUTER_MODEL", self.groq_model))
            self.enable_ai_analysis = str(kwargs.get("enable_ai_analysis", os.getenv("ENABLE_AI_ANALYSIS", "true"))).lower() in ("1", "true", "yes")

            self.crypto_exchange_name = kwargs.get("crypto_exchange_name", os.getenv("CRYPTO_EXCHANGE_NAME", "coinbase"))
            self.coinbase_api_key = kwargs.get("coinbase_api_key", os.getenv("COINBASE_API_KEY", ""))
            self.coinbase_secret_key = kwargs.get("coinbase_secret_key", os.getenv("COINBASE_SECRET_KEY", ""))
            self.crypto_exchange_api_key = kwargs.get("crypto_exchange_api_key", os.getenv("CRYPTO_EXCHANGE_API_KEY", ""))
            self.crypto_exchange_secret = kwargs.get("crypto_exchange_secret", os.getenv("CRYPTO_EXCHANGE_SECRET", ""))

            self.telegram_bot_token = kwargs.get("telegram_bot_token", os.getenv("TELEGRAM_BOT_TOKEN", ""))
            self.telegram_chat_id = kwargs.get("telegram_chat_id", os.getenv("TELEGRAM_CHAT_ID", ""))
            self.telegram_allowed_user_id = kwargs.get("telegram_allowed_user_id", os.getenv("TELEGRAM_ALLOWED_USER_ID", self.telegram_chat_id))
            self.enable_telegram_alerts = str(kwargs.get("enable_telegram_alerts", os.getenv("ENABLE_TELEGRAM_ALERTS", "true"))).lower() in ("1", "true", "yes")

            self.obsidian_rest_api_key = kwargs.get("obsidian_rest_api_key", os.getenv("OBSIDIAN_REST_API_KEY", ""))
            self.obsidian_host = kwargs.get("obsidian_host", os.getenv("OBSIDIAN_HOST", "127.0.0.1"))
            self.obsidian_port = int(kwargs.get("obsidian_port", os.getenv("OBSIDIAN_PORT", 27124)))
            self.obsidian_use_https = str(kwargs.get("obsidian_use_https", os.getenv("OBSIDIAN_USE_HTTPS", "true"))).lower() in ("1", "true", "yes")
            self.obsidian_verify_ssl = str(kwargs.get("obsidian_verify_ssl", os.getenv("OBSIDIAN_VERIFY_SSL", "false"))).lower() in ("1", "true", "yes")
            self.obsidian_vault_folder = kwargs.get("obsidian_vault_folder", os.getenv("OBSIDIAN_VAULT_FOLDER", "Trading-Logs"))

            raw_tickers = kwargs.get("watchlist_tickers", os.getenv("WATCHLIST_TICKERS", "AAPL_US_EQ,MSFT_US_EQ,NVDA_US_EQ"))
            if isinstance(raw_tickers, str):
                self.watchlist_tickers = [t.strip().upper() for t in raw_tickers.split(",") if t.strip()]
            else:
                self.watchlist_tickers = [t.strip().upper() for t in raw_tickers]

            self.buy_allocation_value = float(kwargs.get("buy_allocation_value", os.getenv("BUY_ALLOCATION_VALUE", 25.0)))
            self.dip_threshold_percent = float(kwargs.get("dip_threshold_percent", os.getenv("DIP_THRESHOLD_PERCENT", 2.0)))
            self.sma_short_period = int(kwargs.get("sma_short_period", os.getenv("SMA_SHORT_PERIOD", 10)))
            self.sma_long_period = int(kwargs.get("sma_long_period", os.getenv("SMA_LONG_PERIOD", 50)))
            self.check_interval_minutes = int(kwargs.get("check_interval_minutes", os.getenv("CHECK_INTERVAL_MINUTES", 15)))
            self.dry_run = str(kwargs.get("dry_run", os.getenv("DRY_RUN", "false"))).lower() in ("1", "true", "yes")

        @property
        def effective_ai_api_key(self) -> str:
            return (self.groq_api_key or self.openrouter_api_key or "").strip()

        @property
        def effective_ai_model(self) -> str:
            return (self.groq_model or self.openrouter_model or "llama-3.3-70b-versatile").strip()

        @property
        def effective_crypto_api_key(self) -> str:
            return (self.coinbase_api_key or self.crypto_exchange_api_key or "").strip()

        @property
        def effective_crypto_secret_key(self) -> str:
            return (self.coinbase_secret_key or self.crypto_exchange_secret or "").strip()

        @property
        def effective_crypto_exchange(self) -> str:
            if self.coinbase_api_key or self.coinbase_secret_key:
                return "coinbase"
            return (self.crypto_exchange_name or "coinbase").strip().lower()

        @property
        def t212_effective_key(self) -> str:
            return (self.t212_api_key_id or self.t212_api_key or "").strip()

        @property
        def t212_effective_secret(self) -> str:
            return (self.t212_secret_key or self.t212_api_secret or "").strip()

        @property
        def t212_base_url(self) -> str:
            if self.t212_environment.lower() == "live":
                return "https://live.trading212.com/api/v0"
            return "https://demo.trading212.com/api/v0"

        @property
        def obsidian_base_url(self) -> str:
            protocol = "https" if self.obsidian_use_https else "http"
            return f"{protocol}://{self.obsidian_host}:{self.obsidian_port}"


# Global settings instance
settings = Settings()
