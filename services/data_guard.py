"""
AI Hallucination Guard & Market Data Sanitizer (KODA OS Phase 1)
Validates market prices, quotes, technical indicators, and news before injecting into AI prompt contexts.
Explicitly tags missing or unverified fields as 'DATA_UNAVAILABLE' to prevent LLM hallucinations.
"""

import math
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


class DataGuard:
    """
    Validates and sanitizes market indicators, quotes, and signals before passing to AI or Risk Engines.
    Guarantees strict type safety and flags corrupted or missing metrics.
    """

    @staticmethod
    def validate_number(
        val: Any,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None
    ) -> Optional[float]:
        """
        Validates whether a value is a finite, valid float within given bounds.
        Returns float if valid, None otherwise.
        """
        if val is None or val == DATA_UNAVAILABLE:
            return None
        try:
            num = float(val)
            if math.isnan(num) or math.isinf(num):
                return None
            if min_val is not None and num < min_val:
                return None
            if max_val is not None and num > max_val:
                return None
            return num
        except (ValueError, TypeError):
            return None

    @classmethod
    def sanitize_quote(cls, quote_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitizes a quote dictionary (or MarketQuote fields).
        Ensures prices are positive and bounds are consistent.
        """
        sanitized = {}
        ticker = str(quote_dict.get("ticker", "")).strip().upper()
        sanitized["ticker"] = ticker if ticker else DATA_UNAVAILABLE

        # Price validation (must be > 0)
        price = cls.validate_number(quote_dict.get("price"), min_val=0.000001)
        sanitized["price"] = round(price, 4) if price is not None else DATA_UNAVAILABLE

        # Open / High / Low
        open_p = cls.validate_number(quote_dict.get("open"), min_val=0.000001)
        high_p = cls.validate_number(quote_dict.get("high"), min_val=0.000001)
        low_p = cls.validate_number(quote_dict.get("low"), min_val=0.000001)
        prev_close = cls.validate_number(quote_dict.get("previous_close"), min_val=0.000001)

        sanitized["open"] = round(open_p, 4) if open_p is not None else DATA_UNAVAILABLE
        sanitized["high"] = round(high_p, 4) if high_p is not None else DATA_UNAVAILABLE
        sanitized["low"] = round(low_p, 4) if low_p is not None else DATA_UNAVAILABLE
        sanitized["previous_close"] = round(prev_close, 4) if prev_close is not None else DATA_UNAVAILABLE

        # Coherence check: if high < low, tag as unavailable
        if (
            sanitized["high"] != DATA_UNAVAILABLE
            and sanitized["low"] != DATA_UNAVAILABLE
            and sanitized["high"] < sanitized["low"]
        ):
            logger.warning(f"DataGuard: Inconsistent high ({high_p}) < low ({low_p}) for {ticker}.")
            sanitized["high"] = DATA_UNAVAILABLE
            sanitized["low"] = DATA_UNAVAILABLE

        # Volume
        volume = quote_dict.get("volume")
        try:
            if volume is not None and not math.isnan(float(volume)):
                sanitized["volume"] = max(0, int(volume))
            else:
                sanitized["volume"] = DATA_UNAVAILABLE
        except (ValueError, TypeError):
            sanitized["volume"] = DATA_UNAVAILABLE

        # Daily change %
        change_pct = cls.validate_number(quote_dict.get("change_percent"))
        sanitized["change_percent"] = round(change_pct, 2) if change_pct is not None else DATA_UNAVAILABLE

        return sanitized

    @classmethod
    def sanitize_indicators(cls, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitizes technical indicators (SMA, RSI, ATR, Dip %, etc.).
        Missing or out-of-range metrics are explicitly set to DATA_UNAVAILABLE.
        """
        sanitized = {}

        # Short SMA (> 0)
        short_sma = cls.validate_number(indicators.get("short_sma"), min_val=0.000001)
        sanitized["short_sma"] = round(short_sma, 4) if short_sma is not None else DATA_UNAVAILABLE

        # Long SMA (> 0)
        long_sma = cls.validate_number(indicators.get("long_sma"), min_val=0.000001)
        sanitized["long_sma"] = round(long_sma, 4) if long_sma is not None else DATA_UNAVAILABLE

        # Dip % (can be positive or negative)
        dip_pct = cls.validate_number(indicators.get("dip_percentage"))
        sanitized["dip_percentage"] = round(dip_pct, 2) if dip_pct is not None else DATA_UNAVAILABLE

        # RSI (0.0 to 100.0)
        rsi = cls.validate_number(indicators.get("rsi"), min_val=0.0, max_val=100.0)
        sanitized["rsi"] = round(rsi, 2) if rsi is not None else DATA_UNAVAILABLE

        # ATR (> 0)
        atr = cls.validate_number(indicators.get("atr"), min_val=0.000001)
        sanitized["atr"] = round(atr, 4) if atr is not None else DATA_UNAVAILABLE

        # Support & Resistance levels
        support = cls.validate_number(indicators.get("support"), min_val=0.000001)
        resistance = cls.validate_number(indicators.get("resistance"), min_val=0.000001)
        sanitized["support"] = round(support, 4) if support is not None else DATA_UNAVAILABLE
        sanitized["resistance"] = round(resistance, 4) if resistance is not None else DATA_UNAVAILABLE

        # Copy over boolean flags if present
        if "below_short_sma" in indicators:
            sanitized["below_short_sma"] = bool(indicators["below_short_sma"])
        if "sma_crossover" in indicators:
            sanitized["sma_crossover"] = bool(indicators["sma_crossover"])

        return sanitized

    @classmethod
    def check_price_anomaly(
        cls,
        current_price: float,
        previous_price: Optional[float],
        max_jump_percent: float = 50.0
    ) -> Tuple[bool, str]:
        """
        Detects anomalous market price jumps or invalid non-positive prices.
        Returns (is_anomaly, reason).
        """
        if current_price <= 0.0 or math.isnan(current_price) or math.isinf(current_price):
            return True, f"Invalid non-positive or NaN price: {current_price}"

        if previous_price and previous_price > 0.0:
            jump = abs((current_price - previous_price) / previous_price) * 100.0
            if jump >= max_jump_percent:
                return True, f"Anomalous price jump detected: {jump:.1f}% change (from ${previous_price:,.2f} to ${current_price:,.2f})"

        return False, ""

    @classmethod
    def format_ai_context(
        cls,
        ticker: str,
        current_price: float,
        action: str,
        reason: str,
        indicators: Dict[str, Any],
        news_headlines: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Produces a strictly validated, hallucination-resistant context dictionary for AI Prompts.
        """
        clean_indicators = cls.sanitize_indicators(indicators)
        clean_price = round(current_price, 4) if cls.validate_number(current_price, min_val=0.000001) else DATA_UNAVAILABLE

        context = {
            "ticker": ticker.strip().upper(),
            "action": action.upper(),
            "validated_price": clean_price,
            "trigger_reason": reason,
            "indicators": clean_indicators,
            "news": news_headlines if news_headlines else DATA_UNAVAILABLE,
            "hallucination_guard": "STRICT_ACTIVE"
        }
        return context
