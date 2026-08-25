"""
Market Data Service - yfinance Integration & Dynamic Market Scanner
Fetches latest real-time/delayed quotes, daily price history, technical indicators (SMA),
and provides a dynamic market scanner across S&P 500 / NASDAQ 100 / Trading 212 instruments
with performance-optimized batching and rate-limiting.
"""

import concurrent.futures
import io
import logging
import re
import time
from typing import List, Optional, Dict, Any, Generator
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

# Attempt to import yfinance
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


# Top liquid S&P 500 / NASDAQ 100 stocks for instant high-confidence fallback
TOP_LIQUID_US_TICKERS = [
    "AAPL_US_EQ", "MSFT_US_EQ", "NVDA_US_EQ", "AMZN_US_EQ", "GOOGL_US_EQ",
    "META_US_EQ", "TSLA_US_EQ", "BRK.B_US_EQ", "LLY_US_EQ", "AVGO_US_EQ",
    "JPM_US_EQ", "UNH_US_EQ", "V_US_EQ", "XOM_US_EQ", "MA_US_EQ",
    "JNJ_US_EQ", "HD_US_EQ", "PG_US_EQ", "COST_US_EQ", "AMD_US_EQ",
    "NFLX_US_EQ", "ABBV_US_EQ", "CRM_US_EQ", "BAC_US_EQ", "ADBE_US_EQ",
    "CVX_US_EQ", "MRK_US_EQ", "WMT_US_EQ", "KO_US_EQ", "PEP_US_EQ",
    "TMO_US_EQ", "LIN_US_EQ", "QCOM_US_EQ", "INTC_US_EQ", "CSCO_US_EQ",
    "ORCL_US_EQ", "MCD_US_EQ", "DIS_US_EQ", "TXN_US_EQ", "AMAT_US_EQ",
    "INTU_US_EQ", "GE_US_EQ", "AMGN_US_EQ", "IBM_US_EQ", "CAT_US_EQ",
    "NOW_US_EQ", "PM_US_EQ", "GS_US_EQ", "MS_US_EQ", "BKNG_US_EQ",
    "ISRG_US_EQ", "SPGI_US_EQ", "MDT_US_EQ", "RTX_US_EQ", "VRTX_US_EQ",
    "HON_US_EQ", "PLTR_US_EQ", "PANW_US_EQ", "BLK_US_EQ", "TJX_US_EQ",
    "SYK_US_EQ", "CB_US_EQ", "LRCX_US_EQ", "REGN_US_EQ", "ADP_US_EQ",
    "MU_US_EQ", "CI_US_EQ", "BSX_US_EQ", "C_US_EQ", "MMC_US_EQ",
    "DE_US_EQ", "KLAC_US_EQ", "BMY_US_EQ", "SBUX_US_EQ", "ACN_US_EQ",
    "SNPS_US_EQ", "CDNS_US_EQ", "MDLZ_US_EQ", "FI_US_EQ", "SO_US_EQ",
]


@dataclass
class MarketQuote:
    """Represents a real-time/latest stock price quote."""
    ticker: str
    price: float
    open: float
    high: float
    low: float
    volume: int
    latest_trading_day: str
    previous_close: float
    change: float
    change_percent: float


@dataclass
class DailyBar:
    """Represents a daily OHLCV candlestick bar."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class RateLimiter:
    """
    Ensures that queries do not exceed a specified maximum requests per second.
    Prevents triggering IP rate-limits during bulk market scanning.
    """

    def __init__(self, max_per_second: float = 5.0):
        self.interval = 1.0 / max_per_second if max_per_second > 0 else 0.0
        self.last_time = 0.0

    def wait(self) -> None:
        """Blocks execution if needed to maintain the target rate limit."""
        if self.interval <= 0:
            return
        now = time.time()
        elapsed = now - self.last_time
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_time = time.time()


def rate_limited_batch_iterator(items: List[Any], max_per_second: float = 5.0) -> Generator[Any, None, None]:
    """
    Generator yielding items with automatic rate limiting (e.g. max 5 items/sec).
    """
    limiter = RateLimiter(max_per_second=max_per_second)
    for item in items:
        limiter.wait()
        yield item


def fetch_sp500_tickers_from_web() -> List[str]:
    """
    Fetches the live S&P 500 company ticker list from Wikipedia using pandas / BeautifulSoup / regex.
    Formats tickers to Trading 212 compatible US equity format (e.g. AAPL_US_EQ, BRK.B_US_EQ).
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    logger.info("Fetching dynamic S&P 500 tickers from Wikipedia...")
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    tickers: List[str] = []

    # 1. Try pandas.read_html (fastest and most standard for Wikipedia tables)
    try:
        import pandas as pd
        tables = pd.read_html(io.StringIO(response.text))
        if tables:
            df = tables[0]
            col_name = "Symbol" if "Symbol" in df.columns else df.columns[0]
            for sym in df[col_name]:
                cleaned = str(sym).replace("/", ".").strip().upper()
                if cleaned and cleaned != "NAN":
                    tickers.append(f"{cleaned}_US_EQ")
            if len(tickers) >= 400:
                logger.info(f"pandas.read_html successfully parsed {len(tickers)} S&P 500 tickers from Wikipedia.")
                return tickers
    except Exception as pd_err:
        logger.debug(f"pandas.read_html parsing fallback: {pd_err}")

    # 2. Try BeautifulSoup
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", {"id": "constituents"}) or soup.find("table", {"class": "wikitable"})
        if table:
            for row in table.find_all("tr")[1:]:
                cols = row.find_all("td")
                if cols:
                    sym = cols[0].text.strip().replace("/", ".").upper()
                    if sym:
                        tickers.append(f"{sym}_US_EQ")
            if len(tickers) >= 400:
                logger.info(f"BeautifulSoup parsed {len(tickers)} S&P 500 tickers from Wikipedia.")
                return tickers
    except Exception as bs_err:
        logger.debug(f"BeautifulSoup parsing fallback: {bs_err}")

    # 3. Robust Regex fallback
    table_match = re.search(r'<table[^>]*id="constituents"[^>]*>(.*?)</table>', response.text, re.DOTALL) or \
                  re.search(r'<table[^>]*class="wikitable[^"]*"[^>]*>(.*?)</table>', response.text, re.DOTALL)

    if table_match:
        table_content = table_match.group(1)
        rows = re.findall(r'<tr>(.*?)</tr>', table_content, re.DOTALL)
        for row in rows[1:]:
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if cols:
                sym_raw = re.sub(r'<.*?>', '', cols[0]).strip()
                sym_cleaned = sym_raw.replace("/", ".").strip().upper()
                if sym_cleaned and (sym_cleaned.isalpha() or "." in sym_cleaned):
                    tickers.append(f"{sym_cleaned}_US_EQ")

    if not tickers:
        raise ValueError("Could not extract S&P 500 tickers from Wikipedia.")

    logger.info(f"Successfully extracted {len(tickers)} S&P 500 tickers from Wikipedia.")
    return tickers


def get_all_tradable_tickers(
    source: str = "sp500_nasdaq",
    limit: Optional[int] = None,
    fallback_tickers: Optional[List[str]] = None,
    t212_client: Optional[Any] = None
) -> List[str]:
    """
    Dynamic Market Scanner Ticker Fetcher.
    Fetches the active tradable universe:
    - 'sp500_nasdaq': Downloads live S&P 500 list from web, falling back to top liquid US tickers.
    - 'trading212': Fetches all tradable equity instruments directly from Trading 212 API.
    - Falls back to `fallback_tickers` if all network attempts fail.
    """
    tickers: List[str] = []

    # 1. Trading 212 API Instrument Fetching
    if source.lower() == "trading212" and t212_client:
        try:
            logger.info("Scanning all tradable instruments from Trading 212 API...")
            instruments = t212_client.get_instruments()
            if instruments:
                for inst in instruments:
                    ticker = inst.get("ticker")
                    type_str = str(inst.get("type", "")).upper()
                    if ticker and (type_str in ("EQUITY", "STOCK", "") or "_US_EQ" in ticker):
                        tickers.append(ticker)
                logger.info(f"Discovered {len(tickers)} tradable equity instruments from Trading 212.")
        except Exception as e:
            logger.warning(f"Failed to fetch instruments from Trading 212 API: {e}")

    # 2. S&P 500 / NASDAQ Web Scraping
    if not tickers:
        try:
            tickers = fetch_sp500_tickers_from_web()
        except Exception as web_err:
            logger.warning(f"Live web ticker fetch failed ({web_err}). Falling back to top liquid list.")
            tickers = list(TOP_LIQUID_US_TICKERS)

    # 3. Final Fallback to configured Watchlist if empty
    if not tickers:
        if fallback_tickers:
            tickers = list(fallback_tickers)
        else:
            tickers = ["AAPL_US_EQ", "MSFT_US_EQ", "NVDA_US_EQ", "AMZN_US_EQ", "GOOGL_US_EQ"]

    # Apply optional limit cap (e.g. scan top 50 or 100)
    if limit and limit > 0:
        tickers = tickers[:limit]

    return tickers


class YFinanceClient:
    """
    Market Data client powered by yfinance.
    Retrieves quotes, moving averages, and historical prices without strict API key limits.
    Supports single-ticker and high-performance parallel batch quote fetching.
    """

    def __init__(self, request_timeout: int = 15):
        self.request_timeout = request_timeout

    @staticmethod
    def extract_yahoo_symbol(ticker: str) -> str:
        """
        Converts broker-specific tickers (e.g. 'AAPL_US_EQ', 'VUAGl_EQ', 'VWCEd_EQ', 'IQQHd_EQ', 'ENRd_EQ')
        into Yahoo Finance compatible ticker format ('AAPL', 'VUAG.L', 'VWCE.DE', 'IQQH.DE', 'ENR.DE').
        Strips broker suffixes (_EQ, _US_EQ, l_EQ, d_EQ) and maps exchange codes.
        """
        raw = ticker.strip()

        # 1. Standard explicit exchange suffixes
        if raw.endswith("_US_EQ") or raw.endswith("_us_eq"):
            sym = raw[:-6]
            return sym.replace(".", "-").upper()
        if raw.endswith("_UK_EQ") or raw.endswith("_uk_eq"):
            return f"{raw[:-6].upper()}.L"
        if raw.endswith("_DE_EQ") or raw.endswith("_de_eq"):
            return f"{raw[:-6].upper()}.DE"
        if raw.endswith("_FR_EQ") or raw.endswith("_fr_eq"):
            return f"{raw[:-6].upper()}.PA"
        if raw.endswith("_NL_EQ") or raw.endswith("_nl_eq"):
            return f"{raw[:-6].upper()}.AS"
        if raw.endswith("_IT_EQ") or raw.endswith("_it_eq"):
            return f"{raw[:-6].upper()}.MI"
        if raw.endswith("_ES_EQ") or raw.endswith("_es_eq"):
            return f"{raw[:-6].upper()}.MC"
        if raw.endswith("_CH_EQ") or raw.endswith("_ch_eq"):
            return f"{raw[:-6].upper()}.SW"

        # 2. Compact exchange letter codes before _EQ (e.g. VUAGl_EQ, VWCEd_EQ, IQQHd_EQ, ENRd_EQ)
        if raw.endswith("_EQ") or raw.endswith("_eq"):
            base = raw[:-3]
            # Madrid (mc)
            if base.endswith("mc") or base.endswith("MC"):
                return f"{base[:-2].upper()}.MC"
            # Swiss (sw)
            if base.endswith("sw") or base.endswith("SW"):
                return f"{base[:-2].upper()}.SW"
            # London Stock Exchange (l)
            if base.endswith("l") or base.endswith("L"):
                return f"{base[:-1].upper()}.L"
            # Deutsche Börse Xetra / Germany (d)
            if base.endswith("d") or base.endswith("D"):
                return f"{base[:-1].upper()}.DE"
            # Euronext Paris (p)
            if base.endswith("p") or base.endswith("P"):
                return f"{base[:-1].upper()}.PA"
            # Euronext Amsterdam (a)
            if base.endswith("a") or base.endswith("A"):
                return f"{base[:-1].upper()}.AS"
            # Borsa Italiana (m)
            if base.endswith("m") or base.endswith("M"):
                return f"{base[:-1].upper()}.MI"

            # Plain _EQ fallback
            return base.replace(".", "-").upper()

        # 3. Strip exchange prefixes if present (e.g. "NASDAQ:AAPL")
        if ":" in raw:
            raw = raw.split(":")[-1]

        # 4. Handle plain tickers with dots (e.g. BRK.B -> BRK-B)
        known_intl_suffixes = (".L", ".DE", ".PA", ".AS", ".TO", ".V", ".AX", ".MI", ".MC", ".SW")
        upper_raw = raw.upper()
        if "." in upper_raw and not any(upper_raw.endswith(ext) for ext in known_intl_suffixes):
            return upper_raw.replace(".", "-")

        return upper_raw

    # Alias for backward compatibility
    normalize_ticker = extract_yahoo_symbol

    def get_quote(self, ticker: str) -> MarketQuote:
        """
        Fetches the latest market quote for a stock symbol using yfinance.
        """
        symbol = self.normalize_ticker(ticker)
        logger.info(f"Fetching yfinance quote for symbol '{symbol}' (from '{ticker}')")

        if not HAS_YFINANCE:
            raise ImportError(
                "yfinance is not installed. Please install it via 'pip install yfinance'."
            )

        yf_ticker = yf.Ticker(symbol)

        price = 0.0
        prev_close = 0.0
        day_open = 0.0
        day_high = 0.0
        day_low = 0.0
        volume = 0
        latest_date = ""

        try:
            fast = yf_ticker.fast_info
            price = float(fast.last_price or fast.regular_market_price or 0.0)
            prev_close = float(fast.previous_close or fast.regular_market_previous_close or price)
            day_open = float(fast.open or price)
            day_high = float(fast.day_high or price)
            day_low = float(fast.day_low or price)
            volume = int(fast.last_volume or 0)
        except Exception as e:
            logger.debug(f"fast_info retrieval failed for {symbol}: {e}")

        # If price is still missing, fallback to recent history bars
        if price <= 0.0:
            hist = yf_ticker.history(period="5d", interval="1d")
            if hist.empty:
                raise ValueError(f"No price data found for ticker '{symbol}'.")
            latest_row = hist.iloc[-1]
            price = float(latest_row["Close"])
            day_open = float(latest_row["Open"])
            day_high = float(latest_row["High"])
            day_low = float(latest_row["Low"])
            volume = int(latest_row["Volume"])
            latest_date = str(hist.index[-1].date())
            prev_close = float(hist.iloc[-2]["Close"]) if len(hist) > 1 else price

        change = price - prev_close
        change_pct = (change / prev_close * 100.0) if prev_close > 0 else 0.0

        return MarketQuote(
            ticker=ticker,
            price=round(price, 4),
            open=round(day_open, 4),
            high=round(day_high, 4),
            low=round(day_low, 4),
            volume=volume,
            latest_trading_day=latest_date,
            previous_close=round(prev_close, 4),
            change=round(change, 4),
            change_percent=round(change_pct, 2),
        )

    def get_quotes_batch(self, tickers: List[str], max_workers: int = 8) -> Dict[str, MarketQuote]:
        """
        Fetches quotes for multiple tickers in parallel using a thread pool.
        Significantly accelerates bulk market scanning across hundreds of stocks.
        """
        quotes: Dict[str, MarketQuote] = {}
        if not tickers:
            return quotes

        def _fetch_single(t: str) -> Optional[MarketQuote]:
            try:
                return self.get_quote(t)
            except Exception as err:
                logger.debug(f"Batch quote failed for {t}: {err}")
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {executor.submit(_fetch_single, ticker): ticker for ticker in tickers}
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    res = future.result()
                    if res:
                        quotes[ticker] = res
                except Exception as e:
                    logger.debug(f"Error resolving quote for {ticker}: {e}")

        return quotes

    def get_daily_history(self, ticker: str, period: str = "3mo") -> List[DailyBar]:
        """
        Fetches daily historical price bars.
        """
        symbol = self.normalize_ticker(ticker)
        logger.info(f"Fetching {period} daily history for '{symbol}'")

        if not HAS_YFINANCE:
            raise ImportError("yfinance is not installed. Please install it via 'pip install yfinance'.")

        yf_ticker = yf.Ticker(symbol)
        hist = yf_ticker.history(period=period, interval="1d")
        if hist.empty:
            raise ValueError(f"No historical data returned for ticker '{symbol}'.")

        bars: List[DailyBar] = []
        for index, row in hist.iterrows():
            bars.append(DailyBar(
                date=str(index.date()),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            ))
        return bars

    get_history = get_daily_history

    def calculate_sma(self, ticker: str, period: int = 20) -> float:
        """
        Calculates Simple Moving Average (SMA) from historical daily close prices.
        """
        symbol = self.normalize_ticker(ticker)
        if not HAS_YFINANCE:
            raise ImportError("yfinance is not installed. Please install it via 'pip install yfinance'.")

        yf_ticker = yf.Ticker(symbol)
        fetch_period = "3mo" if period <= 50 else "1y"
        hist = yf_ticker.history(period=fetch_period, interval="1d")

        if len(hist) < period:
            raise ValueError(
                f"Insufficient historical bars ({len(hist)}) to compute {period}-day SMA for {symbol}"
            )

        closes = hist["Close"].tail(period)
        sma = float(closes.mean())
        logger.info(f"Calculated {period}-day SMA for {symbol} ({ticker}): {sma:.2f}")
        return round(sma, 4)


# Aliases for backward compatibility and provider abstraction
MarketDataClient = YFinanceClient
AlphaVantageClient = YFinanceClient
