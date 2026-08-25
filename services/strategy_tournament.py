"""
Strategy Tournament Engine (KODA Institutional Architecture - Block 5)
Maintains performance metrics (Profit Factor, Win Rate %, Sharpe Ratio, Max Drawdown %)
across active strategy archetypes and dynamically ranks them based on the current Market Regime.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class TournamentStrategyStats:
    """Quantitative performance and regime affinity metrics for a strategy archetype."""
    strategy_id: str
    name: str
    archetype: str
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown_pct: float
    tournament_score: float
    regime_multiplier: float = 1.0
    recommended_allocation_pct: float = 25.0


class StrategyTournamentEngine:
    """
    Evaluates, scores, and ranks competing strategy algorithms dynamically per market regime.
    """

    def __init__(self):
        self._strategies: Dict[str, TournamentStrategyStats] = self._init_default_strategies()

    def _init_default_strategies(self) -> Dict[str, TournamentStrategyStats]:
        """Initializes benchmark baseline strategies."""
        return {
            "MOMENTUM_BREAKOUT": TournamentStrategyStats(
                strategy_id="MOMENTUM_BREAKOUT",
                name="20-Day High RVOL Momentum Breakout",
                archetype="BREAKOUT",
                total_trades=42,
                win_rate_pct=64.3,
                profit_factor=1.85,
                sharpe_ratio=1.75,
                max_drawdown_pct=4.8,
                tournament_score=78.5
            ),
            "MEAN_REVERSION_DIP": TournamentStrategyStats(
                strategy_id="MEAN_REVERSION_DIP",
                name="RSI Oversold Dip-and-SMA Bounce",
                archetype="MEAN_REVERSION",
                total_trades=58,
                win_rate_pct=70.7,
                profit_factor=1.92,
                sharpe_ratio=1.90,
                max_drawdown_pct=3.6,
                tournament_score=84.0
            ),
            "TREND_CONTINUATION_EMA": TournamentStrategyStats(
                strategy_id="TREND_CONTINUATION_EMA",
                name="Golden Cross Pullback Expansion",
                archetype="TREND_FOLLOWING",
                total_trades=35,
                win_rate_pct=62.8,
                profit_factor=1.65,
                sharpe_ratio=1.55,
                max_drawdown_pct=5.2,
                tournament_score=72.0
            ),
            "VWAP_VOLATILITY_EXPANSION": TournamentStrategyStats(
                strategy_id="VWAP_VOLATILITY_EXPANSION",
                name="Intraday VWAP Volatility Surge",
                archetype="VOLATILITY",
                total_trades=29,
                win_rate_pct=58.6,
                profit_factor=1.50,
                sharpe_ratio=1.40,
                max_drawdown_pct=6.1,
                tournament_score=68.0
            ),
        }

    def update_strategy_performance(
        self,
        strategy_id: str,
        total_trades: int,
        win_rate_pct: float,
        profit_factor: float,
        sharpe_ratio: float,
        max_drawdown_pct: float
    ) -> None:
        """Updates live performance metrics for a tournament strategy."""
        if strategy_id in self._strategies:
            st = self._strategies[strategy_id]
            st.total_trades = total_trades
            st.win_rate_pct = win_rate_pct
            st.profit_factor = profit_factor
            st.sharpe_ratio = sharpe_ratio
            st.max_drawdown_pct = max_drawdown_pct
            st.tournament_score = round(
                (win_rate_pct * 0.4) + (profit_factor * 20.0) + (sharpe_ratio * 15.0) - (max_drawdown_pct * 2.0),
                1
            )

    def rank_strategies(self, current_regime: str = "TRENDING_BULL") -> List[TournamentStrategyStats]:
        """
        Dynamically adjusts and ranks tournament strategies based on active market regime.
        """
        regime_clean = current_regime.upper()
        ranked_list: List[TournamentStrategyStats] = []

        for st_id, st in self._strategies.items():
            mult = 1.0
            if regime_clean == "TRENDING_BULL":
                if st.archetype in ("BREAKOUT", "TREND_FOLLOWING"):
                    mult = 1.30
                elif st.archetype == "MEAN_REVERSION":
                    mult = 1.05
                else:
                    mult = 0.85
            elif regime_clean == "RANGING":
                if st.archetype == "MEAN_REVERSION":
                    mult = 1.40
                elif st.archetype in ("BREAKOUT", "TREND_FOLLOWING"):
                    mult = 0.40  # Heavily penalize breakouts in ranging regimes
                else:
                    mult = 0.90
            elif regime_clean == "HIGH_VOLATILITY":
                if st.archetype == "VOLATILITY":
                    mult = 1.40
                elif st.archetype == "MEAN_REVERSION":
                    mult = 1.10
                else:
                    mult = 0.60
            elif regime_clean == "RISK_OFF":
                if st.archetype == "MEAN_REVERSION":
                    mult = 1.20
                else:
                    mult = 0.50

            adjusted_score = round(st.tournament_score * mult, 1)

            ranked_list.append(TournamentStrategyStats(
                strategy_id=st.strategy_id,
                name=st.name,
                archetype=st.archetype,
                total_trades=st.total_trades,
                win_rate_pct=st.win_rate_pct,
                profit_factor=st.profit_factor,
                sharpe_ratio=st.sharpe_ratio,
                max_drawdown_pct=st.max_drawdown_pct,
                tournament_score=adjusted_score,
                regime_multiplier=mult,
                recommended_allocation_pct=25.0
            ))

        ranked_list.sort(key=lambda x: x.tournament_score, reverse=True)

        # Distribute allocation percentages proportionally
        total_adj_score = sum(x.tournament_score for x in ranked_list)
        if total_adj_score > 0:
            for item in ranked_list:
                item.recommended_allocation_pct = round((item.tournament_score / total_adj_score) * 100.0, 1)

        return ranked_list
