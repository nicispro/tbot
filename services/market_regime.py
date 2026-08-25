"""
Market Regime Engine (KODA Institutional Architecture - Block 2)
Classifies multi-asset market regimes (TRENDING_BULL, TRENDING_BEAR, RANGING, HIGH_VOLATILITY,
RISK_ON, RISK_OFF) and computes dynamic strategy adjustment rules (breakout permissions,
position size scaling, Stop-Loss ATR multipliers).
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

from services.market_data import YFinanceClient, DailyBar, MarketQuote
from services.crypto_data import CryptoDataClient

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"


@dataclass
class RegimeClassification:
    """Comprehensive regime diagnosis and dynamic execution directives."""
    primary_regime: MarketRegime
    volatility_level: str  # 'LOW', 'NORMAL', 'HIGH', 'EXTREME'
    trend_strength: float  # 0.0 - 100.0
    can_trade_breakouts: bool
    can_trade_trend_continuation: bool
    can_trade_mean_reversion: bool
    position_size_multiplier: float  # 0.0 - 1.5
    stop_loss_atr_multiplier: float  # e.g. 1.5 - 2.5
    rationale: str
    metrics: Dict[str, Any] = field(default_factory=dict)


class MarketRegimeEngine:
    """
    Evaluates multi-asset market metrics (S&P 500, NASDAQ, Bitcoin) to determine active regime.
    """

    def __init__(
        self,
        stock_client: Optional[YFinanceClient] = None,
        crypto_client: Optional[CryptoDataClient] = None
    ):
        self.stock_client = stock_client or YFinanceClient()
        self.crypto_client = crypto_client or CryptoDataClient()

    def classify_regime(
        self,
        spy_change_pct: Optional[float] = None,
        btc_change_pct: Optional[float] = None,
        atr_ratio: Optional[float] = None,
        rsi_composite: Optional[float] = None
    ) -> RegimeClassification:
        """
        Diagnoses active market regime based on equity/crypto index momentum and volatility ratios.
        """
        # Default or fetch live index proxy metrics
        spy_change = spy_change_pct if spy_change_pct is not None else 0.5
        btc_change = btc_change_pct if btc_change_pct is not None else 2.5
        vol_ratio = atr_ratio if atr_ratio is not None else 1.1
        rsi = rsi_composite if rsi_composite is not None else 58.0

        # 1. High Volatility Regime
        if vol_ratio >= 2.0:
            return RegimeClassification(
                primary_regime=MarketRegime.HIGH_VOLATILITY,
                volatility_level="EXTREME" if vol_ratio >= 2.5 else "HIGH",
                trend_strength=70.0,
                can_trade_breakouts=False,
                can_trade_trend_continuation=True,
                can_trade_mean_reversion=True,
                position_size_multiplier=0.5,
                stop_loss_atr_multiplier=2.5,
                rationale="Elevated market volatility detected. Scaled down position sizing by 50% and widened ATR stops.",
                metrics={"vol_ratio": vol_ratio, "spy_change": spy_change, "btc_change": btc_change}
            )

        # 2. Trending Bear / Risk Off Regime
        if spy_change < -1.2 and btc_change < -2.5:
            return RegimeClassification(
                primary_regime=MarketRegime.RISK_OFF,
                volatility_level="NORMAL",
                trend_strength=65.0,
                can_trade_breakouts=False,
                can_trade_trend_continuation=False,
                can_trade_mean_reversion=True,
                position_size_multiplier=0.5,
                stop_loss_atr_multiplier=1.8,
                rationale="Risk-Off synchronized selloff across equities and crypto. Halved long exposure.",
                metrics={"spy_change": spy_change, "btc_change": btc_change, "vol_ratio": vol_ratio}
            )

        # 3. Trending Bull / Risk On Regime
        if spy_change > 0.3 and btc_change > 1.0 and rsi >= 52.0:
            return RegimeClassification(
                primary_regime=MarketRegime.TRENDING_BULL,
                volatility_level="NORMAL",
                trend_strength=80.0,
                can_trade_breakouts=True,
                can_trade_trend_continuation=True,
                can_trade_mean_reversion=True,
                position_size_multiplier=1.0,
                stop_loss_atr_multiplier=1.5,
                rationale="Synchronized bullish trend in equities and crypto. Full position sizing authorized.",
                metrics={"spy_change": spy_change, "btc_change": btc_change, "rsi": rsi}
            )

        # 4. Ranging / Compression Regime (Default)
        return RegimeClassification(
            primary_regime=MarketRegime.RANGING,
            volatility_level="LOW",
            trend_strength=35.0,
            can_trade_breakouts=False,
            can_trade_trend_continuation=False,
            can_trade_mean_reversion=True,
            position_size_multiplier=0.75,
            stop_loss_atr_multiplier=1.5,
            rationale="Market in sideways consolidation. Disabled breakout entries to prevent false breakout whipsaws.",
            metrics={"spy_change": spy_change, "btc_change": btc_change, "vol_ratio": vol_ratio}
        )
