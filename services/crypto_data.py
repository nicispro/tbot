"""
Crypto Market Data Service
Retrieves standardized real-time quotes, OHLCV historical candlestick bars,
computes technical indicators (SMA), and fetches optional authenticated wallet balances
across top cryptocurrencies using CCXT (Binance/KuCoin/Bybit) with automatic public REST API fallback.
"""

import datetime
import os
import time
import logging
from typing import List, Optional, Dict, Any
import requests
import urllib3

from services.market_data import MarketQuote, DailyBar
from services.trading212 import AccountCash

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Attempt to import ccxt
try:
    import ccxt
    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False


DEFAULT_CRYPTO_UNIVERSE = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "DOGE/USDT",
    "LINK/USDT",
    "DOT/USDT",
    "NEAR/USDT",
    "MATIC/USDT",
    "UNI/USDT",
    "ATOM/USDT",
    "LTC/USDT",
    "APT/USDT",
    "ARB/USDT",
    "OP/USDT",
    "SUI/USDT",
    "INJ/USDT",
    "TIA/USDT",
    "RENDER/USDT",
    "FET/USDT",
    "SEI/USDT",
]


class CryptoDataClient:
    """
    Standardized Crypto Market Data and Execution Client powered by CCXT / Binance Demo & Futures.
    Supports Binance Demo Trading (Spot testnet.binance.vision & Futures testnet.binancefuture.com),
    real-time tickers, OHLCV candles, moving averages, wallet balances, and automated trade execution.
    """

    def __init__(
        self,
        exchange_id: Optional[str] = None,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        is_testnet: Optional[bool] = None,
        default_type: Optional[str] = None,
        timeout: int = 15
    ):
        # 1. Determine testnet / demo mode
        if is_testnet is not None:
            self.is_testnet = is_testnet
        else:
            self.is_testnet = (
                os.getenv("BINANCE_DEMO_ENABLED", "").lower() in ("true", "1", "yes")
                or os.getenv("BINANCE_TESTNET_ENABLED", "true").lower() in ("true", "1", "yes")
                or bool(os.getenv("BINANCE_DEMO_API_KEY"))
                or bool(os.getenv("BINANCE_TESTNET_API_KEY"))
            )

        # 2. Resolve exchange identifier (strictly enforce Binance when in testnet/demo mode)
        raw_exchange = (
            exchange_id
            or os.getenv("CRYPTO_EXCHANGE_NAME")
            or "binance"
        ).lower()

        if self.is_testnet or os.getenv("BINANCE_DEMO_API_KEY") or os.getenv("BINANCE_TESTNET_API_KEY"):
            if not exchange_id or raw_exchange in ("coinbase", "generic", "", "none"):
                raw_exchange = "binance"

        self.exchange_id = raw_exchange

        # 3. Read Binance Demo / Testnet keys or general crypto exchange keys
        if api_key is not None:
            raw_key = api_key
        else:
            raw_key = (
                os.getenv("BINANCE_DEMO_API_KEY")
                or os.getenv("BINANCE_TESTNET_API_KEY")
                or os.getenv("BINANCE_API_KEY")
                or os.getenv("COINBASE_API_KEY")
                or os.getenv("CRYPTO_EXCHANGE_API_KEY")
                or ""
            )

        if secret is not None:
            raw_secret = secret
        else:
            raw_secret = (
                os.getenv("BINANCE_DEMO_SECRET")
                or os.getenv("BINANCE_TESTNET_SECRET")
                or os.getenv("BINANCE_API_SECRET")
                or os.getenv("COINBASE_SECRET_KEY")
                or os.getenv("CRYPTO_EXCHANGE_SECRET")
                or ""
            )

        self.api_key = raw_key.strip()
        self.secret = raw_secret.strip()

        self.default_type = (default_type or os.getenv("CRYPTO_DEFAULT_TYPE") or "future").lower()
        self.timeout = timeout
        self._exchange = None

        if HAS_CCXT:
            try:
                if self.exchange_id in ("binance", "binanceusdm"):
                    if self.default_type in ("future", "futures", "delivery"):
                        exchange_class = (
                            getattr(ccxt, "binanceusdm", None)
                            or getattr(ccxt, self.exchange_id, None)
                            or getattr(ccxt, "binance", None)
                            or ccxt.binance
                        )
                    else:
                        exchange_class = getattr(ccxt, self.exchange_id, None) or getattr(ccxt, "binance", None) or ccxt.binance
                else:
                    exchange_class = getattr(ccxt, self.exchange_id, None) or getattr(ccxt, "binance", None) or ccxt.binance

                exchange_config = {
                    "timeout": self.timeout * 1000,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": self.default_type,
                        "adjustForTimeDifference": True,
                    }
                }
                if self.has_credentials():
                    exchange_config["apiKey"] = self.api_key
                    exchange_config["secret"] = self.secret

                self._exchange = exchange_class(exchange_config)

                if self.is_testnet:
                    # 1. Enable official CCXT Demo Trading mode for Binance
                    if hasattr(self._exchange, "enableDemoTrading"):
                        try:
                            self._exchange.enableDemoTrading(True)
                        except Exception as demo_err:
                            logger.debug(f"enableDemoTrading notice: {demo_err}")
                    elif hasattr(self._exchange, "enable_demo_trading"):
                        try:
                            self._exchange.enable_demo_trading(True)
                        except Exception as demo_err:
                            logger.debug(f"enable_demo_trading notice: {demo_err}")

                    # 2. Configure official Binance Demo Trading API endpoints
                    if self.exchange_id in ("binance", "binanceusdm"):
                        if hasattr(self._exchange, "urls") and isinstance(self._exchange.urls, dict):
                            if "api" in self._exchange.urls and isinstance(self._exchange.urls["api"], dict):
                                self._exchange.urls["api"]["fapi"] = "https://demo-fapi.binance.com/fapi/v1"
                                self._exchange.urls["api"]["fapiPublic"] = "https://demo-fapi.binance.com/fapi/v1"
                                self._exchange.urls["api"]["fapiPrivate"] = "https://demo-fapi.binance.com/fapi/v1"
                                self._exchange.urls["api"]["dapi"] = "https://demo-dapi.binance.com/dapi/v1"
                                self._exchange.urls["api"]["public"] = "https://testnet.binance.vision/api/v3"
                                self._exchange.urls["api"]["private"] = "https://testnet.binance.vision/api/v3"

                logger.info(
                    f"Initialized CCXT exchange client: {self.exchange_id} (Demo: {self.is_testnet}, "
                    f"Type: {self.default_type}, Auth: {self.has_credentials()})"
                )
            except Exception as e:
                logger.warning(f"Could not initialize CCXT exchange '{self.exchange_id}': {e}. Using REST fallback.")
                self._exchange = None

        self._session = requests.Session()
        try:
            import certifi
            self._session.verify = certifi.where()
        except ImportError:
            pass

    def _http_get(self, url: str) -> requests.Response:
        """Performs HTTP GET with automatic SSL fallback if local certificates are unverified."""
        try:
            response = self._session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.SSLError:
            logger.debug(f"SSLError encountered for {url}. Retrying with verify=False.")
            response = self._session.get(url, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response

    def has_credentials(self) -> bool:
        """Checks if authenticated crypto exchange API keys are provided."""
        return bool(self.api_key and self.secret)

    def get_balance(self) -> Optional[AccountCash]:
        """
        Retrieves live crypto wallet balance (USD / USDC / USDT / Total portfolio balance)
        from Coinbase or the configured CCXT exchange if API keys are set.
        Returns None if API keys are omitted.
        """
        if not self.has_credentials():
            logger.info("Coinbase / Crypto Exchange API keys not set. Running crypto scan in simulation mode without wallet balance.")
            return None

        if not self._exchange:
            logger.warning(f"CCXT exchange client '{self.exchange_id}' not initialized for balance retrieval.")
            return None

        try:
            balance = self._exchange.fetch_balance()

            # 1. Calculate Free Liquid Cash (USD + USDC + USDT)
            free_usd = float(balance.get("USD", {}).get("free", 0.0) or balance.get("free", {}).get("USD", 0.0))
            free_usdc = float(balance.get("USDC", {}).get("free", 0.0) or balance.get("free", {}).get("USDC", 0.0))
            free_usdt = float(balance.get("USDT", {}).get("free", 0.0) or balance.get("free", {}).get("USDT", 0.0))
            total_free_cash = free_usd + free_usdc + free_usdt

            # 2. Calculate Total Portfolio Balance
            total_usd = float(balance.get("USD", {}).get("total", 0.0) or balance.get("total", {}).get("USD", 0.0))
            total_usdc = float(balance.get("USDC", {}).get("total", 0.0) or balance.get("total", {}).get("USDC", 0.0))
            total_usdt = float(balance.get("USDT", {}).get("total", 0.0) or balance.get("total", {}).get("USDT", 0.0))
            fiat_and_stable_total = total_usd + total_usdc + total_usdt

            # If exchange provides overall total or total USD estimation
            overall_total = float(balance.get("total", {}).get("USD", 0.0) or balance.get("info", {}).get("total_balance", 0.0) or fiat_and_stable_total)
            if overall_total < fiat_and_stable_total:
                overall_total = fiat_and_stable_total

            invested_val = max(0.0, overall_total - total_free_cash)

            logger.info(
                f"Crypto Wallet ({self.exchange_id.upper()}): "
                f"Free Cash=${total_free_cash:,.2f} (USD:${free_usd:,.2f}, USDC:${free_usdc:,.2f}, USDT:${free_usdt:,.2f}) | "
                f"Total Balance=${overall_total:,.2f}"
            )
            return AccountCash(
                free=round(total_free_cash, 2),
                total=round(overall_total, 2),
                invested=round(invested_val, 2),
                ppl=0.0,
                result=0.0
            )
        except Exception as err:
            logger.error(f"Failed to fetch {self.exchange_id.upper()} crypto wallet balance: {err}")
            return None

    # Alias for backward compatibility
    get_account_balance = get_balance

    @staticmethod
    def normalize_crypto_symbol(symbol: str) -> str:
        """
        Standardizes crypto symbol format into BASE/QUOTE (e.g. 'BTC/USDT', 'BTCUSDT' -> 'BTC/USDT').
        """
        raw = symbol.strip().upper()
        if "/" in raw:
            return raw
        if raw.endswith("USDT"):
            base = raw[:-4]
            return f"{base}/USDT"
        if raw.endswith("USD"):
            base = raw[:-3]
            return f"{base}/USD"
        return raw

    def get_all_tradable_crypto(self, limit: Optional[int] = None) -> List[str]:
        """
        Returns the top liquid crypto scanner universe.
        """
        universe = list(DEFAULT_CRYPTO_UNIVERSE)
        if limit and limit > 0:
            return universe[:limit]
        return universe

    def get_quote(self, symbol: str) -> MarketQuote:
        """
        Fetches the latest ticker market quote for a cryptocurrency.
        """
        pair = self.normalize_crypto_symbol(symbol)
        logger.info(f"Fetching crypto quote for '{pair}'")

        # 1. Try CCXT first if available
        if self._exchange:
            try:
                ticker_data = self._exchange.fetch_ticker(pair)
                last_price = float(ticker_data.get("last") or ticker_data.get("close") or 0.0)
                open_price = float(ticker_data.get("open") or last_price)
                high_price = float(ticker_data.get("high") or last_price)
                low_price = float(ticker_data.get("low") or last_price)
                prev_close = float(ticker_data.get("previousClose") or open_price)
                volume = int(float(ticker_data.get("baseVolume") or ticker_data.get("quoteVolume") or 0))
                change = float(ticker_data.get("change") or (last_price - prev_close))
                change_pct = float(ticker_data.get("percentage") or ((change / prev_close * 100.0) if prev_close > 0 else 0.0))
                date_str = str(datetime.datetime.now(datetime.timezone.utc).date())

                return MarketQuote(
                    ticker=pair,
                    price=round(last_price, 4),
                    open=round(open_price, 4),
                    high=round(high_price, 4),
                    low=round(low_price, 4),
                    volume=volume,
                    latest_trading_day=date_str,
                    previous_close=round(prev_close, 4),
                    change=round(change, 4),
                    change_percent=round(change_pct, 2)
                )
            except Exception as ccxt_err:
                logger.debug(f"CCXT fetch_ticker failed for {pair} ({ccxt_err}), falling back to direct REST.")

        # 2. Direct Public Binance REST API Fallback
        binance_symbol = pair.replace("/", "")
        if self.is_testnet:
            if self.default_type in ("future", "futures", "delivery"):
                url = f"https://demo-fapi.binance.com/fapi/v1/ticker/24hr?symbol={binance_symbol}"
            else:
                url = f"https://testnet.binance.vision/api/v3/ticker/24hr?symbol={binance_symbol}"
        else:
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={binance_symbol}"

        response = self._http_get(url)
        data = response.json()

        last_price = float(data.get("lastPrice", 0.0))
        open_price = float(data.get("openPrice", last_price))
        high_price = float(data.get("highPrice", last_price))
        low_price = float(data.get("lowPrice", last_price))
        prev_close = float(data.get("prevClosePrice", open_price))
        volume = int(float(data.get("volume", 0)))
        change = float(data.get("priceChange", 0.0))
        change_pct = float(data.get("priceChangePercent", 0.0))
        date_str = str(datetime.datetime.now(datetime.timezone.utc).date())

        return MarketQuote(
            ticker=pair,
            price=round(last_price, 4),
            open=round(open_price, 4),
            high=round(high_price, 4),
            low=round(low_price, 4),
            volume=volume,
            latest_trading_day=date_str,
            previous_close=round(prev_close, 4),
            change=round(change, 4),
            change_percent=round(change_pct, 2)
        )

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 100) -> List[DailyBar]:
        """
        Fetches historical OHLCV candlestick bars for a cryptocurrency pair.
        """
        pair = self.normalize_crypto_symbol(symbol)
        logger.info(f"Fetching {limit} '{timeframe}' OHLCV bars for crypto '{pair}'")

        # 1. Try CCXT
        if self._exchange:
            try:
                raw_ohlcv = self._exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
                bars: List[DailyBar] = []
                for entry in raw_ohlcv:
                    ts_ms = entry[0]
                    date_str = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
                    bars.append(DailyBar(
                        date=date_str,
                        open=float(entry[1]),
                        high=float(entry[2]),
                        low=float(entry[3]),
                        close=float(entry[4]),
                        volume=int(float(entry[5]))
                    ))
                if bars:
                    return bars
            except Exception as ccxt_err:
                logger.debug(f"CCXT fetch_ohlcv failed for {pair} ({ccxt_err}), falling back to direct REST.")

        # 2. Public REST Fallback
        binance_symbol = pair.replace("/", "")
        if self.is_testnet:
            if self.default_type in ("future", "futures", "delivery"):
                url = f"https://demo-fapi.binance.com/fapi/v1/klines?symbol={binance_symbol}&interval={timeframe}&limit={limit}"
            else:
                url = f"https://testnet.binance.vision/api/v3/klines?symbol={binance_symbol}&interval={timeframe}&limit={limit}"
        else:
            url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={timeframe}&limit={limit}"

        response = self._http_get(url)
        raw_klines = response.json()

        bars: List[DailyBar] = []
        for entry in raw_klines:
            ts_ms = entry[0]
            date_str = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            bars.append(DailyBar(
                date=date_str,
                open=float(entry[1]),
                high=float(entry[2]),
                low=float(entry[3]),
                close=float(entry[4]),
                volume=int(float(entry[5]))
            ))

        return bars

    get_history = fetch_ohlcv

    def calculate_sma(self, symbol: str, period: int = 20, timeframe: str = "1d") -> float:
        """
        Calculates Simple Moving Average (SMA) from historical crypto closing prices.
        """
        pair = self.normalize_crypto_symbol(symbol)
        fetch_limit = max(period + 10, 50)
        bars = self.fetch_ohlcv(pair, timeframe=timeframe, limit=fetch_limit)

        if len(bars) < period:
            raise ValueError(f"Insufficient historical bars ({len(bars)}) to compute {period}-{timeframe} SMA for {pair}")

        recent_closes = [bar.close for bar in bars[-period:]]
        sma = sum(recent_closes) / len(recent_closes)
        logger.info(f"Calculated {period}-{timeframe} SMA for crypto {pair}: ${sma:,.2f}")
        return round(sma, 4)

    def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "market",
        strategy_reason: str = "Quantitative Futures Signal Trigger",
        params: Optional[Dict[str, Any]] = None,
        ai_analysis: Optional[Any] = None,
        export_to_obsidian: bool = True
    ) -> Dict[str, Any]:
        """
        Executes a crypto order (spot/futures) via CCXT or Binance Futures Testnet,
        and logs the executed trade note with AI reasoning directly to the Obsidian Vault.
        """
        pair = self.normalize_crypto_symbol(symbol)
        side_norm = side.upper()
        if os.getenv("BINANCE_DEMO_ENABLED", "").lower() in ("true", "1", "yes") or bool(os.getenv("BINANCE_DEMO_API_KEY")):
            env_str = "demo"
        elif self.is_testnet:
            env_str = "testnet"
        elif self.has_credentials():
            env_str = "live"
        else:
            env_str = "paper"

        logger.info(f"Executing crypto {side_norm} order for {pair}: amount={amount}, type={order_type}, env={env_str}")

        order_id = f"CRYPTO-{int(time.time()*1000)}"
        filled_price = price or 0.0
        # Normalize quantity precision according to contract standards
        if "BTC" in pair:
            norm_amount = max(0.001, round(amount, 3))
        elif "ETH" in pair or "SOL" in pair or "BNB" in pair:
            norm_amount = max(0.01, round(amount, 2))
        else:
            norm_amount = max(0.1, round(amount, 1))

        filled_qty = norm_amount
        status = "FILLED"
        error_msg = None

        if self._exchange and self.has_credentials():
            try:
                order_params = {"defaultType": self.default_type, **(params or {})} if self.default_type in ("future", "futures") else (params or {})
                # For market orders, omit price parameter to avoid Binance contract errors
                exec_price = price if order_type.lower() == "limit" else None
                ccxt_order = self._exchange.create_order(
                    symbol=pair,
                    type=order_type.lower(),
                    side=side.lower(),
                    amount=norm_amount,
                    price=exec_price,
                    params=order_params
                )
                if isinstance(ccxt_order, dict):
                    order_id = str(ccxt_order.get("id") or ccxt_order.get("orderId") or ccxt_order.get("info", {}).get("orderId") or order_id)
                    raw_st = str(ccxt_order.get("status") or ccxt_order.get("info", {}).get("status") or "").upper()
                    if raw_st in ("CLOSED", "FILLED", "TRADE", "COMPLETED"):
                        status = "FILLED"
                    elif raw_st in ("OPEN", "NEW", "PENDING_NEW", "PARTIALLY_FILLED", "ACCEPTED"):
                        status = "OPEN"
                    elif raw_st in ("REJECTED", "EXPIRED", "CANCELED", "CANCELLED", "FAILED"):
                        status = "FAILED"
                    else:
                        status = "FILLED"

                    filled_price = float(ccxt_order.get("price") or ccxt_order.get("average") or ccxt_order.get("info", {}).get("avgPrice") or ccxt_order.get("info", {}).get("price") or price or 0.0)
                    filled_qty = float(ccxt_order.get("amount") or ccxt_order.get("filled") or ccxt_order.get("info", {}).get("origQty") or norm_amount)
                    logger.info(f"Binance USDⓈ-M Futures order placed: {order_id} ({pair} {side_norm} @ ${filled_price:,.2f}, Status: {status})")
            except Exception as ex:
                logger.warning(f"Binance Demo/Futures order placement notice for {pair}: {ex}")
                status = "FAILED"
                error_msg = str(ex)

        if filled_price <= 0.0:
            try:
                q = self.get_quote(pair)
                filled_price = q.price
            except Exception:
                filled_price = price or 100.0

        order_val = filled_price * filled_qty

        # Log to Obsidian Vault (/opt/koda_bot/obsidian_vault) with full AI reasoning
        if export_to_obsidian:
            try:
                from services.obsidian import TradeLogRecord
                from services.obsidian_exporter import ObsidianVaultExporter
                rec = TradeLogRecord(
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                    ticker=pair,
                    action=side_norm,
                    price=filled_price,
                    quantity=filled_qty,
                    order_value=order_val,
                    strategy_reason=f"[{env_str.upper()} / {self.default_type.upper()}] {strategy_reason}",
                    execution_success=(status not in ("FAILED", "REJECTED", "EXPIRED")),
                    order_id=order_id,
                    broker_status=status,
                    environment=env_str,
                    error_message=error_msg
                )
                exporter = ObsidianVaultExporter()
                exporter.export_trade(record=rec, ai_analysis=ai_analysis)
            except Exception as obs_err:
                logger.debug(f"Obsidian trade logging notice: {obs_err}")

        return {
            "order_id": order_id,
            "ticker": pair,
            "symbol": pair,
            "action": side_norm,
            "side": side_norm,
            "price": filled_price,
            "quantity": filled_qty,
            "order_value": order_val,
            "status": status,
            "environment": env_str,
            "ai_analysis": ai_analysis,
            "error": error_msg
        }

    execute_futures_order = create_order
