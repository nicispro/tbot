"""
Opportunity & Quality Scoring Engine (KODA OS Phase 2)
Calculates a composite Opportunity Score (0-100) across 4 pillars:
1. Technical Alignment (30%)
2. Momentum Strength (25%)
3. Volume & Volatility Surge (20%)
4. Multi-Timeframe Confluence (25%)
Ranks and filters the Top High-Probability trading opportunities.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from services.market_radar import RadarAssetScanResult, MarketEventType, TimeframeTrend

logger = logging.getLogger(__name__)


@dataclass
class ScoredOpportunity:
    """Represents a scored and graded trading opportunity."""
    ticker: str
    market_type: str
    price: float
    composite_score: float  # 0.0 - 100.0
    technical_score: float
    momentum_score: float
    volume_volatility_score: float
    confluence_score: float
    grade: str  # 'A+', 'A', 'B', 'C', 'D'
    key_events: List[str]
    indicators: Dict[str, Any] = field(default_factory=dict)


class OpportunityScorer:
    """
    Evaluates and ranks scanned assets to highlight high-conviction trade setups.
    """

    def __init__(
        self,
        weight_technical: float = 0.30,
        weight_momentum: float = 0.25,
        weight_volume_volatility: float = 0.20,
        weight_confluence: float = 0.25
    ):
        self.weight_technical = weight_technical
        self.weight_momentum = weight_momentum
        self.weight_volume_volatility = weight_volume_volatility
        self.weight_confluence = weight_confluence

    def score_asset(self, scan_res: RadarAssetScanResult) -> ScoredOpportunity:
        """
        Calculates individual pillar scores and composite score for a scanned asset.
        """
        indicators = scan_res.indicators
        rsi = float(indicators.get("rsi", 50.0)) if indicators.get("rsi") != "DATA_UNAVAILABLE" else 50.0
        dip_pct = float(indicators.get("dip_percentage", 0.0)) if indicators.get("dip_percentage") != "DATA_UNAVAILABLE" else 0.0

        # 1. Technical Score (0-100)
        # Rewards healthy pullbacks to short SMA or clean breakout setups
        tech_score = 50.0
        events_types = [e.event_type for e in scan_res.detected_events]

        if MarketEventType.BREAKOUT in events_types:
            tech_score += 35.0
        if MarketEventType.TREND_CHANGE in events_types:
            tech_score += 25.0
        if 1.0 <= dip_pct <= 5.0:  # Ideal buy-the-dip zone
            tech_score += 20.0
        tech_score = max(0.0, min(100.0, tech_score))

        # 2. Momentum Score (0-100)
        # Optimal bullish momentum is RSI between 50 and 70 (neither oversold dump nor overbought blow-off)
        if 50.0 <= rsi <= 68.0:
            mom_score = 85.0 + (rsi - 50.0)
        elif 40.0 <= rsi < 50.0:
            mom_score = 65.0  # Mild oversold consolidation
        elif 68.0 < rsi <= 78.0:
            mom_score = 75.0  # Strong but approaching high band
        elif rsi > 78.0:
            mom_score = 45.0  # Overextended
        else:
            mom_score = 30.0  # Bearish momentum

        if MarketEventType.MOMENTUM_SURGE in events_types:
            mom_score = min(100.0, mom_score + 15.0)
        mom_score = max(0.0, min(100.0, mom_score))

        # 3. Volume & Volatility Score (0-100)
        # Rewards volume confirmation without chaotic volatility
        vol_score = 50.0
        vol_mult = scan_res.volume_surge_multiplier
        if vol_mult >= 2.0:
            vol_score += 35.0
        elif vol_mult >= 1.5:
            vol_score += 20.0
        elif vol_mult < 0.7:
            vol_score -= 15.0  # Low liquidity warning

        atr_ratio = scan_res.volatility_atr_ratio
        if 1.0 <= atr_ratio <= 2.2:
            vol_score += 15.0  # Healthy volatility expansion
        elif atr_ratio > 3.0:
            vol_score -= 20.0  # Erratic volatility spike
        vol_score = max(0.0, min(100.0, vol_score))

        # 4. Multi-Timeframe Confluence Score (0-100)
        conf_score = scan_res.timeframe_analysis.confluence_score

        # Composite Weighted Score
        composite = (
            (tech_score * self.weight_technical)
            + (mom_score * self.weight_momentum)
            + (vol_score * self.weight_volume_volatility)
            + (conf_score * self.weight_confluence)
        )
        composite = round(composite, 1)

        # Opportunity Grade
        if composite >= 85.0:
            grade = "A+"
        elif composite >= 75.0:
            grade = "A"
        elif composite >= 65.0:
            grade = "B"
        elif composite >= 50.0:
            grade = "C"
        else:
            grade = "D"

        highlights = [e.description for e in scan_res.detected_events]
        if scan_res.timeframe_analysis.is_confluent_bullish:
            highlights.append("Triple Timeframe Bullish Alignment (5m + 1h + 1D)")

        return ScoredOpportunity(
            ticker=scan_res.ticker,
            market_type=scan_res.market_type,
            price=scan_res.current_price,
            composite_score=composite,
            technical_score=round(tech_score, 1),
            momentum_score=round(mom_score, 1),
            volume_volatility_score=round(vol_score, 1),
            confluence_score=round(conf_score, 1),
            grade=grade,
            key_events=highlights,
            indicators=indicators
        )

    def rank_opportunities(
        self,
        scan_results: List[RadarAssetScanResult],
        top_n: int = 10,
        min_score: float = 60.0
    ) -> List[ScoredOpportunity]:
        """
        Scores, filters, and sorts scanned assets by composite score in descending order.
        """
        scored_list = [self.score_asset(res) for res in scan_results]
        # Filter by minimum score threshold
        filtered = [s for s in scored_list if s.composite_score >= min_score]
        # Sort by composite score descending
        ranked = sorted(filtered, key=lambda x: x.composite_score, reverse=True)
        return ranked[:top_n]
