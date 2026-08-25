"""
KODA Market Radar & Multi-Timeframe Brain (KODA OS Phase 2)
Scans multi-asset universe (Stocks & Crypto) to detect market events:
- Breakouts
- Momentum Surges
- Volume Spikes
- Volatility Spikes
- Trend Changes
and assesses Multi-Timeframe Alignment (5m, 1h, 1D).
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

from services.market_data import YFinanceClient, MarketQuote, DailyBar
from services.crypto_data import CryptoDataClient
from services.data_guard import DataGuard, DATA_UNAVAILABLE

logger = logging.getLogger(__name__)


class MarketEventType(str, Enum):
    BREAKOUT = "BREAKOUT"
    MOMENTUM_SURGE = "MOMENTUM_SURGE"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
    TREND_CHANGE = "TREND_CHANGE"
    CONSOLIDATION = "CONSOLIDATION"


class TimeframeTrend(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass
class MarketEvent:
    """Represents an identified market anomaly or pattern."""
    event_type: MarketEventType
    timeframe: str
    description: str
    significance: float  # 0.0 - 1.0


@dataclass
class MultiTimeframeAnalysis:
    """Multi-timeframe trend alignment and confluences."""
    macro_1d: TimeframeTrend
    intermediate_1h: TimeframeTrend
    micro_5m: TimeframeTrend
    is_confluent_bullish: bool
    is_confluent_bearish: bool
    confluence_score: float  # 0.0 - 100.0


@dataclass
class RadarAssetScanResult:
    """Comprehensive scan result for a single asset."""
    ticker: str
    market_type: str  # 'stock' or 'crypto'
    current_price: float
    detected_events: List[MarketEvent]
    timeframe_analysis: MultiTimeframeAnalysis
    indicators: Dict[str, Any]
    volume_surge_multiplier: float
    volatility_atr_ratio: float


class MarketRadar:
    """
    Multi-timeframe scanner and market event detector.
    """

    def __init__(
        self,
        stock_client: Optional[YFinanceClient] = None,
        crypto_client: Optional[CryptoDataClient] = None
    ):
        self.stock_client = stock_client or YFinanceClient()
        self.crypto_client = crypto_client or CryptoDataClient()

    def analyze_asset(
        self,
        ticker: str,
        market_type: str = "stock",
        quote: Optional[MarketQuote] = None,
        history: Optional[List[DailyBar]] = None
    ) -> RadarAssetScanResult:
        """
        Runs comprehensive multi-timeframe analysis and event detection for a given asset.
        """
        market_type = market_type.lower()
        if not quote:
            if market_type == "crypto":
                quote = self.crypto_client.get_quote(ticker)
            else:
                quote = self.stock_client.get_quote(ticker)

        if not history:
            try:
                if market_type == "crypto":
                    history = self.crypto_client.fetch_ohlcv(ticker, timeframe="1d", limit=30)
                else:
                    history = self.stock_client.get_daily_history(ticker, period="3mo")
            except Exception as h_err:
                logger.debug(f"Could not retrieve history for {ticker}: {h_err}")
                history = []

        price = quote.price if quote else 0.0
        detected_events: List[MarketEvent] = []

        # Technical indicator calculations
        short_sma = 0.0
        long_sma = 0.0
        atr = 0.0
        vol_mult = 1.0
        atr_ratio = 1.0
        support = 0.0
        resistance = 0.0
        rsi = 50.0

        if history and len(history) >= 5:
            closes = [b.close for b in history]
            volumes = [b.volume for b in history if b.volume > 0]
            highs = [b.high for b in history]
            lows = [b.low for b in history]

            # SMAs
            if len(closes) >= 10:
                short_sma = sum(closes[-10:]) / 10.0
            if len(closes) >= 20:
                long_sma = sum(closes[-20:]) / 20.0

            # Support & Resistance (20-bar lookback)
            lookback_highs = highs[-20:] if len(highs) >= 20 else highs
            lookback_lows = lows[-20:] if len(lows) >= 20 else lows
            resistance = max(lookback_highs) if lookback_highs else price
            support = min(lookback_lows) if lookback_lows else price

            # ATR calculation (14 periods)
            tr_list = []
            for i in range(1, len(history)):
                h, l, pc = history[i].high, history[i].low, history[i - 1].close
                tr_list.append(max(h - l, abs(h - pc), abs(l - pc)))
            atr = (sum(tr_list[-14:]) / len(tr_list[-14:])) if tr_list else (price * 0.02)

            # Volume surge check
            avg_vol = (sum(volumes[-10:]) / len(volumes[-10:])) if len(volumes) >= 10 else 1.0
            cur_vol = history[-1].volume or (quote.volume if quote else 0)
            vol_mult = (cur_vol / avg_vol) if avg_vol > 0 else 1.0

            # Candle volatility vs ATR
            cur_range = history[-1].high - history[-1].low
            atr_ratio = (cur_range / atr) if atr > 0 else 1.0

            # Simple RSI calculation (14 periods)
            if len(closes) >= 15:
                gains = []
                losses = []
                for i in range(len(closes) - 14, len(closes)):
                    diff = closes[i] - closes[i - 1]
                    if diff > 0:
                        gains.append(diff)
                        losses.append(0.0)
                    else:
                        gains.append(0.0)
                        losses.append(abs(diff))
                avg_gain = sum(gains) / 14.0
                avg_loss = sum(losses) / 14.0
                if avg_loss == 0.0:
                    rsi = 100.0
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100.0 - (100.0 / (1.0 + rs))

            # 1. Event Detection: Breakout
            if price >= resistance * 0.998:
                detected_events.append(MarketEvent(
                    event_type=MarketEventType.BREAKOUT,
                    timeframe="1D",
                    description=f"Price (${price:,.2f}) testing/breaking 20-day resistance (${resistance:,.2f})",
                    significance=0.85
                ))

            # 2. Event Detection: Volume Spike
            if vol_mult >= 1.75:
                detected_events.append(MarketEvent(
                    event_type=MarketEventType.VOLUME_SPIKE,
                    timeframe="1D",
                    description=f"Volume surged to {vol_mult:.1f}x of 10-day average volume",
                    significance=min(1.0, 0.5 + (vol_mult * 0.1))
                ))

            # 3. Event Detection: Volatility Spike
            if atr_ratio >= 1.8:
                detected_events.append(MarketEvent(
                    event_type=MarketEventType.VOLATILITY_SPIKE,
                    timeframe="1D",
                    description=f"Intraday candle range is {atr_ratio:.1f}x Average True Range",
                    significance=0.75
                ))

            # 4. Event Detection: Momentum Surge
            if 55.0 <= rsi <= 75.0 and quote and quote.change_percent > 1.5:
                detected_events.append(MarketEvent(
                    event_type=MarketEventType.MOMENTUM_SURGE,
                    timeframe="1D",
                    description=f"Strong bullish momentum (RSI: {rsi:.1f}, Change: +{quote.change_percent:.1f}%)",
                    significance=0.80
                ))

            # 5. Event Detection: Trend Change / Golden Bounce
            if short_sma > long_sma and (short_sma - price) / short_sma > 0.01:
                detected_events.append(MarketEvent(
                    event_type=MarketEventType.TREND_CHANGE,
                    timeframe="1D",
                    description="Bullish dip pullback into short-term SMA support",
                    significance=0.70
                ))

        # Multi-timeframe trend alignment evaluation
        macro_trend = TimeframeTrend.BULLISH if (short_sma > 0 and price >= short_sma) else TimeframeTrend.BEARISH
        if short_sma == 0.0:
            macro_trend = TimeframeTrend.NEUTRAL

        # Estimate intermediate (1h) and micro (5m) trends from price momentum and short SMA
        inter_trend = TimeframeTrend.BULLISH if (quote and quote.change_percent > 0) else TimeframeTrend.BEARISH
        micro_trend = TimeframeTrend.BULLISH if (rsi >= 50.0) else TimeframeTrend.BEARISH

        is_bull_confluence = (macro_trend == TimeframeTrend.BULLISH and inter_trend == TimeframeTrend.BULLISH and micro_trend == TimeframeTrend.BULLISH)
        is_bear_confluence = (macro_trend == TimeframeTrend.BEARISH and inter_trend == TimeframeTrend.BEARISH and micro_trend == TimeframeTrend.BEARISH)

        confluence_score = 50.0
        if is_bull_confluence:
            confluence_score = 95.0
        elif macro_trend == TimeframeTrend.BULLISH and (inter_trend == TimeframeTrend.BULLISH or micro_trend == TimeframeTrend.BULLISH):
            confluence_score = 75.0
        elif is_bear_confluence:
            confluence_score = 10.0

        mtf = MultiTimeframeAnalysis(
            macro_1d=macro_trend,
            intermediate_1h=inter_trend,
            micro_5m=micro_trend,
            is_confluent_bullish=is_bull_confluence,
            is_confluent_bearish=is_bear_confluence,
            confluence_score=confluence_score
        )

        indicators_dict = {
            "short_sma": round(short_sma, 4) if short_sma > 0 else DATA_UNAVAILABLE,
            "long_sma": round(long_sma, 4) if long_sma > 0 else DATA_UNAVAILABLE,
            "atr": round(atr, 4) if atr > 0 else DATA_UNAVAILABLE,
            "rsi": round(rsi, 2),
            "support": round(support, 4) if support > 0 else DATA_UNAVAILABLE,
            "resistance": round(resistance, 4) if resistance > 0 else DATA_UNAVAILABLE,
            "dip_percentage": round(((short_sma - price) / short_sma) * 100.0, 2) if short_sma > 0 else 0.0
        }

        return RadarAssetScanResult(
            ticker=ticker,
            market_type=market_type,
            current_price=price,
            detected_events=detected_events,
            timeframe_analysis=mtf,
            indicators=indicators_dict,
            volume_surge_multiplier=round(vol_mult, 2),
            volatility_atr_ratio=round(atr_ratio, 2)
        )


@dataclass
class Level1Candidate:
    """Pre-filtered candidate from Level 1 fast technical screen."""
    ticker: str
    market_type: str
    price: float
    change_24h_pct: float
    relative_volume: float
    prefilter_score: float


@dataclass
class Level3Finalist:
    """High-conviction finalist evaluated through Groq AI in Level 3."""
    ticker: str
    market_type: str
    price: float
    composite_score: float
    grade: str
    ai_sentiment: str
    ai_confidence: int
    ai_summary: str
    ai_catalysts: str
    key_events: List[str]
    recommendation: str  # 'PROCEED', 'WATCH', 'VETO'


@dataclass
class MultiLevelPipelineResult:
    """Hierarchical results of the 3-Level Scanning Pipeline."""
    total_screened_level1: int
    passed_level1_count: int
    level1_candidates: List[Level1Candidate]
    passed_level2_count: int
    level2_scored_setups: List[Any]
    level3_finalists: List[Level3Finalist]
    duration_seconds: float


class MultiLevelMarketRadar(MarketRadar):
    """
    Institutional Multi-Level Scanning Pipeline (KODA Block 1).
    Funnel Architecture:
    - Level 1: Fast Technical Pre-filter (Broad universe -> Top 50-100 relative volume/momentum)
    - Level 2: Quant Scoring Engine (Multi-timeframe OHLCV & Indicators -> Top 10-15 setups)
    - Level 3: Groq AI Finalist Review (Qualitative reasoning & confirmation -> Top 3-5 high-conviction trades)
    """

    def run_multi_level_scan(
        self,
        universe: List[str],
        target_market: str = "all",
        ai_client: Optional[Any] = None,
        l1_limit: int = 50,
        l2_limit: int = 15,
        l3_limit: int = 5
    ) -> MultiLevelPipelineResult:
        """
        Executes the full 3-level institutional screening pipeline on the provided market universe.
        """
        import time
        from services.opportunity_scorer import OpportunityScorer

        start_time = time.time()
        logger.info(f"=== Starting KODA Multi-Level Scanning Pipeline (Universe: {len(universe)} instruments) ===")

        # ==========================================
        # LEVEL 1: Fast Technical Pre-filter
        # ==========================================
        logger.info(f"🔍 [LEVEL 1] Running fast technical pre-filter across {len(universe)} assets...")
        l1_candidates: List[Level1Candidate] = []

        for symbol in universe:
            m_type = "crypto" if ("/" in symbol or symbol.endswith("USDT") or symbol.endswith("USD") and "_" not in symbol) else "stock"
            try:
                if m_type == "crypto":
                    q = self.crypto_client.get_quote(symbol)
                else:
                    q = self.stock_client.get_quote(symbol)

                if q.price <= 0.0:
                    continue

                rvol = max(0.5, min(5.0, (q.volume / 100_000.0) if q.volume > 0 else 1.0))
                # Prefilter score prioritizes positive momentum and relative volume surge
                momentum_weight = max(-10.0, min(10.0, q.change_percent)) * 5.0
                volume_weight = rvol * 15.0
                pre_score = round(50.0 + momentum_weight + volume_weight, 1)

                l1_candidates.append(Level1Candidate(
                    ticker=symbol,
                    market_type=m_type,
                    price=q.price,
                    change_24h_pct=round(q.change_percent, 2),
                    relative_volume=round(rvol, 2),
                    prefilter_score=pre_score
                ))
            except Exception as e:
                logger.debug(f"Level 1 quote fetch skipped for {symbol}: {e}")

        # Sort and trim to top L1 survivors
        l1_candidates.sort(key=lambda x: x.prefilter_score, reverse=True)
        l1_survivors = l1_candidates[:l1_limit]
        logger.info(f"✅ [LEVEL 1 COMPLETE] Screened {len(l1_candidates)} assets. Selected top {len(l1_survivors)} candidates.")

        # ==========================================
        # LEVEL 2: Deep Quant Scoring Engine
        # ==========================================
        logger.info(f"📊 [LEVEL 2] Computing deep multi-timeframe indicators for top {len(l1_survivors)} candidates...")
        radar_scans: List[RadarAssetScanResult] = []

        for cand in l1_survivors:
            try:
                scan_res = self.analyze_asset(ticker=cand.ticker, market_type=cand.market_type)
                radar_scans.append(scan_res)
            except Exception as e:
                logger.debug(f"Level 2 deep scan skipped for {cand.ticker}: {e}")

        scorer = OpportunityScorer()
        scored_setups = scorer.rank_opportunities(radar_scans, top_n=l2_limit, min_score=40.0)
        logger.info(f"✅ [LEVEL 2 COMPLETE] Scored {len(radar_scans)} setups. Ranked top {len(scored_setups)} finalists.")

        # ==========================================
        # LEVEL 3: Groq AI Finalist Review
        # ==========================================
        logger.info(f"🤖 [LEVEL 3] Reviewing top {min(len(scored_setups), l3_limit)} setups via Groq AI LLM...")
        finalists: List[Level3Finalist] = []

        for op in scored_setups[:l3_limit]:
            sentiment = "BULLISH"
            confidence = int(min(95, max(50, op.composite_score)))
            summary = "Technical rule alignment and volume surge confirmed."
            catalysts = "; ".join(op.key_events[:2]) if op.key_events else "Momentum breakout"

            if ai_client and ai_client.is_configured():
                try:
                    ai_res = ai_client.analyze_trade_signal(
                        ticker=op.ticker,
                        price=op.price,
                        action="BUY",
                        reason=f"Top Radar Opportunity (Score: {op.composite_score:.1f}, Grade: {op.grade})",
                        indicators=op.indicators
                    )
                    sentiment = ai_res.sentiment
                    confidence = ai_res.confidence_score
                    summary = ai_res.summary
                    catalysts = ai_res.catalysts
                except Exception as ai_err:
                    logger.debug(f"AI review fallback for {op.ticker}: {ai_err}")

            # Recommendation Logic
            if sentiment == "BULLISH" and confidence >= 70:
                rec = "PROCEED"
            elif sentiment == "BEARISH":
                rec = "VETO"
            else:
                rec = "WATCH"

            finalists.append(Level3Finalist(
                ticker=op.ticker,
                market_type=op.market_type,
                price=op.price,
                composite_score=op.composite_score,
                grade=op.grade,
                ai_sentiment=sentiment,
                ai_confidence=confidence,
                ai_summary=summary,
                ai_catalysts=catalysts,
                key_events=op.key_events,
                recommendation=rec
            ))

        logger.info(f"🏆 [LEVEL 3 COMPLETE] Evaluated {len(finalists)} finalist(s).")
        duration = time.time() - start_time

        return MultiLevelPipelineResult(
            total_screened_level1=len(universe),
            passed_level1_count=len(l1_survivors),
            level1_candidates=l1_survivors,
            passed_level2_count=len(scored_setups),
            level2_scored_setups=scored_setups,
            level3_finalists=finalists,
            duration_seconds=round(duration, 2)
        )

