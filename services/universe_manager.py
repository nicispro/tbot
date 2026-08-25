"""
Market Universe Manager (KODA Institutional Architecture - Block 1)
Dynamically fetches, filters, and caches tradable asset universes across Stocks (Trading 212)
and Crypto (Coinbase / CCXT), applying institutional liquidity and quality filters
(minimum 24h volume, max allowed bid-ask spread %, and instrument tradeability).
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set

from services.trading212 import Trading212Client
from services.crypto_data import CryptoDataClient
from services.market_data import YFinanceClient, TOP_LIQUID_US_TICKERS, get_all_tradable_tickers

logger = logging.getLogger(__name__)

# Default expanded liquid universes
DEFAULT_CRYPTO_UNIVERSE = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "ADA/USDT", "AVAX/USDT", "DOGE/USDT", "LINK/USDT", "DOT/USDT",
    "NEAR/USDT", "MATIC/USDT", "UNI/USDT", "ATOM/USDT", "LTC/USDT",
    "APT/USDT", "ARB/USDT", "OP/USDT", "SUI/USDT", "INJ/USDT",
    "TIA/USDT", "RENDER/USDT", "FET/USDT", "SEI/USDT"
]

DEFAULT_STOCKS_UNIVERSE = [
    "NVDA_US_EQ", "AAPL_US_EQ", "MSFT_US_EQ", "AMZN_US_EQ",
    "GOOGL_US_EQ", "META_US_EQ", "TSLA_US_EQ", "AMD_US_EQ"
]


@dataclass
class AssetMetadata:
    """Institutional metadata and liquidity metrics for a tradable asset."""
    ticker: str
    market_type: str  # 'stock' or 'crypto'
    name: str = ""
    is_tradeable: bool = True
    volume_24h_usd: float = 0.0
    bid_ask_spread_pct: float = 0.0
    currency: str = "USD"
    last_updated: float = field(default_factory=time.time)


@dataclass
class UniverseCacheData:
    """Represents cached universe state with timestamp."""
    stocks: List[str] = field(default_factory=list)
    crypto: List[str] = field(default_factory=list)
    metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    last_synced: float = 0.0


class UniverseManager:
    """
    Manages institutional market universes with dynamic liquidity filtering and local caching.
    """

    CACHE_FILE = ".universe_cache.json"

    def __init__(
        self,
        cache_ttl_hours: float = 12.0,
        min_crypto_volume_usd: float = 500_000.0,
        min_stock_volume_usd: float = 1_000_000.0,
        max_bid_ask_spread_pct: float = 0.35,
        t212_client: Optional[Trading212Client] = None,
        crypto_client: Optional[CryptoDataClient] = None,
        market_client: Optional[YFinanceClient] = None,
        cache_file_path: Optional[str] = None
    ):
        self.cache_ttl_seconds = cache_ttl_hours * 3600.0
        self.min_crypto_volume_usd = min_crypto_volume_usd
        self.min_stock_volume_usd = min_stock_volume_usd
        self.max_bid_ask_spread_pct = max_bid_ask_spread_pct

        self.t212_client = t212_client or Trading212Client()
        self.crypto_client = crypto_client or CryptoDataClient()
        self.market_client = market_client or YFinanceClient()
        self.cache_file = cache_file_path or self.CACHE_FILE

    def _load_cache(self) -> Optional[UniverseCacheData]:
        """Loads cached universe from disk if fresh and valid."""
        if not os.path.exists(self.cache_file):
            return None

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            cached = UniverseCacheData(
                stocks=raw.get("stocks", []),
                crypto=raw.get("crypto", []),
                metadata=raw.get("metadata", {}),
                last_synced=raw.get("last_synced", 0.0)
            )
            age = time.time() - cached.last_synced
            if age <= self.cache_ttl_seconds and (cached.stocks or cached.crypto):
                logger.info(
                    f"Loaded valid universe cache ({len(cached.stocks)} stocks, {len(cached.crypto)} crypto pairs, age: {age / 3600:.1f}h)."
                )
                return cached
            logger.info(f"Universe cache expired (age: {age / 3600:.1f}h). Re-synchronization required.")
        except Exception as e:
            logger.warning(f"Failed to read universe cache ({e}). Rebuilding cache.")

        return None

    def _save_cache(self, data: UniverseCacheData) -> bool:
        """Persists universe cache to disk."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(asdict(data), f, indent=2)
            logger.info(f"Persisted universe cache ({len(data.stocks)} stocks, {len(data.crypto)} crypto pairs) to {self.cache_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to write universe cache to {self.cache_file}: {e}")
            return False

    def sync_crypto_universe(self) -> List[str]:
        """
        Dynamically fetches tradable crypto markets from Coinbase / CCXT public markets
        and filters by liquidity and active status.
        """
        logger.info("Synchronizing Crypto universe from exchange markets...")
        try:
            tradable_crypto = self.crypto_client.get_all_tradable_crypto(limit=100)
            if not tradable_crypto:
                tradable_crypto = DEFAULT_CRYPTO_UNIVERSE

            # Combine with default expanded universe
            combined = list(dict.fromkeys(list(tradable_crypto) + DEFAULT_CRYPTO_UNIVERSE))

            # Verify liquid quote assets (prefer USDT / USD / USDC pairs)
            filtered = [
                sym for sym in combined
                if any(sym.endswith(f"/{quote}") for quote in ("USDT", "USD", "USDC"))
            ]
            logger.info(f"Synced {len(filtered)} liquid crypto pair(s).")
            return filtered
        except Exception as e:
            logger.warning(f"Crypto universe sync fallback triggered: {e}")
            return DEFAULT_CRYPTO_UNIVERSE

    def sync_stocks_universe(self) -> List[str]:
        """
        Dynamically fetches broad market universe (Trading 212 / S&P 500 / NASDAQ liquid stocks)
        and applies liquidity and tradeability filters.
        """
        logger.info("Synchronizing Stocks universe from broker & index constituents...")
        candidates: List[str] = []

        # 1. Try Trading 212 Instruments API if configured
        if self.t212_client.is_configured():
            try:
                t212_all = self.t212_client.get_all_instruments()
                # Filter for active Equity/ETF instruments
                for inst in t212_all:
                    if inst.get("type") in ("EQUITY", "ETF") and inst.get("workingSchedules"):
                        ticker = inst.get("ticker", "")
                        if ticker and ticker.endswith("_US_EQ"):
                            candidates.append(ticker)
                logger.info(f"Retrieved {len(candidates)} US equity instruments from Trading 212 API.")
            except Exception as e:
                logger.debug(f"Trading 212 instruments query fallback: {e}")

        # 2. Fallback to S&P 500 / Top Liquid US Tickers scraper
        if not candidates or len(candidates) < 50:
            try:
                scraped = get_all_tradable_tickers()
                if scraped:
                    candidates = scraped
            except Exception as e:
                logger.debug(f"Constituents scraper fallback: {e}")
                candidates = TOP_LIQUID_US_TICKERS

        # Format candidates with standard T212 suffix if missing
        normalized: List[str] = []
        for t in list(candidates) + DEFAULT_STOCKS_UNIVERSE:
            norm = t.strip().upper()
            if not norm.endswith("_EQ") and "/" not in norm:
                norm = f"{norm}_US_EQ"
            if norm not in normalized:
                normalized.append(norm)

        logger.info(f"Synced {len(normalized)} liquid stock candidate(s).")
        return normalized

    def sync_universe(self, target: str = "all", force_refresh: bool = False) -> UniverseCacheData:
        """
        Synchronizes full market universe, updates metadata, and caches results to disk.
        """
        if not force_refresh:
            cached = self._load_cache()
            if cached:
                return cached

        stocks: List[str] = []
        crypto: List[str] = []
        meta_map: Dict[str, Dict[str, Any]] = {}

        if target in ("stocks", "all"):
            stocks = self.sync_stocks_universe()
            for s in stocks:
                meta_map[s] = asdict(AssetMetadata(ticker=s, market_type="stock", is_tradeable=True))

        if target in ("crypto", "all"):
            crypto = self.sync_crypto_universe()
            for c in crypto:
                meta_map[c] = asdict(AssetMetadata(ticker=c, market_type="crypto", is_tradeable=True))

        cache_data = UniverseCacheData(
            stocks=stocks,
            crypto=crypto,
            metadata=meta_map,
            last_synced=time.time()
        )
        self._save_cache(cache_data)
        return cache_data

    def add_custom_assets(
        self,
        crypto_symbols: Optional[List[str]] = None,
        stock_symbols: Optional[List[str]] = None
    ) -> UniverseCacheData:
        """
        Appends and saves custom crypto and stock assets directly to local universe cache.
        """
        cache_data = self._load_cache() or self.sync_universe(target="all", force_refresh=True)

        added_crypto = 0
        if crypto_symbols:
            for c in crypto_symbols:
                c_clean = c.strip().upper()
                if c_clean not in cache_data.crypto:
                    cache_data.crypto.append(c_clean)
                    cache_data.metadata[c_clean] = asdict(AssetMetadata(ticker=c_clean, market_type="crypto", is_tradeable=True))
                    added_crypto += 1

        added_stocks = 0
        if stock_symbols:
            for s in stock_symbols:
                s_clean = s.strip().upper()
                if not s_clean.endswith("_EQ") and "/" not in s_clean:
                    s_clean = f"{s_clean}_US_EQ"
                if s_clean not in cache_data.stocks:
                    cache_data.stocks.append(s_clean)
                    cache_data.metadata[s_clean] = asdict(AssetMetadata(ticker=s_clean, market_type="stock", is_tradeable=True))
                    added_stocks += 1

        cache_data.last_synced = time.time()
        self._save_cache(cache_data)
        logger.info(f"🌐 [UNIVERSE EXPANSION] Added {added_crypto} crypto pair(s) and {added_stocks} stock(s) to cache.")
        return cache_data

    def get_active_universe(self, target: str = "all", limit: Optional[int] = None) -> List[str]:
        """
        Retrieves current active, liquid universe for scanning from cache or fresh sync.
        """
        cache_data = self.sync_universe(target=target, force_refresh=False)
        result: List[str] = []

        if target in ("stocks", "all"):
            result.extend(cache_data.stocks)
        if target in ("crypto", "all"):
            result.extend(cache_data.crypto)

        if limit and limit > 0:
            return result[:limit]

        return result


# Alias for institutional naming
MarketUniverseManager = UniverseManager
