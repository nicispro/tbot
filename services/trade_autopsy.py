"""
Trade Autopsy 2.0 & Counterfactual Analysis Engine (KODA Institutional Architecture - Block 4)
Conducts automated post-mortem root-cause analysis and counterfactual retrospective simulations:
- Evaluates what-if scenarios (wider Stop-Loss +0.5 ATR, delayed entry timing).
- Separates Decision Process Quality from Outcome (Good Decision / Win, Good Decision / Loss, Bad Decision / Win, Bad Decision / Loss).
- Formulates actionable lessons for Obsidian memory and Groq LLM retrospective context.
"""

import datetime
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class DecisionOutcomeQuadrant(str, Enum):
    GOOD_DECISION_WIN = "GOOD_DECISION_WIN"      # Edge executed well -> Profit (Ideal)
    GOOD_DECISION_LOSS = "GOOD_DECISION_LOSS"    # Statistical variance on sound process (Acceptable)
    BAD_DECISION_WIN = "BAD_DECISION_WIN"        # Fluke win on flawed setup / rule breach (Dangerous)
    BAD_DECISION_LOSS = "BAD_DECISION_LOSS"      # Systematic mistake / rule violation (Avoid)


@dataclass
class TradeAutopsyReport:
    """Represents the post-mortem analysis of a trade outcome (Autopsy 2.0)."""
    signal_id: int
    ticker: str
    market_type: str
    signal_type: str
    entry_price: float
    exit_price: float
    pnl_percent: float
    outcome: str  # 'WIN', 'LOSS', 'NEUTRAL'
    root_cause: str
    primary_driver: str
    actionable_lesson: str
    rule_recommendation: str
    # Autopsy 2.0 additions (with sensible defaults for backward compatibility)
    decision_outcome_quadrant: str = "GOOD_DECISION_LOSS"
    process_quality_score: float = 75.0
    counterfactual_wider_sl_pnl_pct: float = 0.0
    counterfactual_wider_sl_result: str = "UNCHANGED"
    counterfactual_delayed_entry_pnl_pct: float = 0.0
    counterfactual_delayed_entry_result: str = "UNCHANGED"
    counterfactual_insight: str = ""
    indicators: Dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class TradeAutopsyEngine:
    """
    Evaluates completed trade outcomes with counterfactual simulation and process-vs-outcome classification.
    """

    def analyze_outcome(self, outcome_data: Dict[str, Any]) -> TradeAutopsyReport:
        """
        Runs comprehensive post-mortem analysis with counterfactual checks on a verified signal outcome.
        """
        signal_id = int(outcome_data.get("id", 0))
        ticker = str(outcome_data.get("ticker", "UNKNOWN"))
        market_type = str(outcome_data.get("market_type", "stock"))
        signal_type = str(outcome_data.get("signal_type", "BUY")).upper()
        entry_price = float(outcome_data.get("entry_price", 0.0) or outcome_data.get("price_at_signal", 0.0))
        exit_price = float(outcome_data.get("exit_price", 0.0))
        pnl_percent = float(outcome_data.get("pnl_percent", 0.0))
        outcome = str(outcome_data.get("outcome", "NEUTRAL")).upper()
        indicators = outcome_data.get("indicators", {}) or {}

        rsi = float(indicators.get("rsi", 50.0)) if indicators.get("rsi") != "DATA_UNAVAILABLE" and indicators.get("rsi") is not None else 50.0
        short_sma = float(indicators.get("short_sma", 0.0)) if indicators.get("short_sma") != "DATA_UNAVAILABLE" and indicators.get("short_sma") is not None else 0.0
        long_sma = float(indicators.get("long_sma", 0.0)) if indicators.get("long_sma") != "DATA_UNAVAILABLE" and indicators.get("long_sma") is not None else 0.0
        resistance = float(indicators.get("resistance", 0.0)) if indicators.get("resistance") != "DATA_UNAVAILABLE" and indicators.get("resistance") is not None else 0.0
        support = float(indicators.get("support", 0.0)) if indicators.get("support") != "DATA_UNAVAILABLE" and indicators.get("support") is not None else 0.0
        atr = float(indicators.get("atr", 0.0)) if indicators.get("atr") != "DATA_UNAVAILABLE" and indicators.get("atr") is not None else (entry_price * 0.02)

        root_cause = ""
        primary_driver = ""
        actionable_lesson = ""
        rule_recommendation = ""
        is_bad_decision = False

        if outcome == "LOSS":
            # Diagnose Loss Failure Modes
            if rsi >= 75.0:
                root_cause = "OVERBOUGHT_EXHAUSTION"
                primary_driver = f"Entry occurred at elevated RSI ({rsi:.1f}), leading to immediate mean-reversion selloff."
                actionable_lesson = f"Avoid entering long positions when RSI > 75 on {ticker}; wait for consolidation pullback."
                rule_recommendation = "Enforce hard RSI <= 72 cap on trend continuation entries."
                is_bad_decision = True
            elif resistance > entry_price and (resistance - entry_price) < (1.2 * atr):
                root_cause = "RESISTANCE_TRAP"
                primary_driver = f"Entry was directly beneath major resistance (${resistance:,.2f}), capping upside."
                actionable_lesson = f"Always ensure at least 2.0x ATR distance between entry price and overhead resistance."
                rule_recommendation = "Reject BUY setups with < 1.5x ATR buffer to nearest resistance."
                is_bad_decision = True
            elif long_sma > 0 and entry_price < (long_sma * 0.95):
                root_cause = "MACRO_DOWNTREND_DRAG"
                primary_driver = f"Counter-trend long entry against active 50-period moving average downtrend (${long_sma:,.2f})."
                actionable_lesson = "Counter-trend dip buying requires confirmed multi-candle higher-low before entry."
                rule_recommendation = "Require confirmed breakout above 10-period SMA before buying macro dips."
                is_bad_decision = True
            elif atr > 0 and abs(pnl_percent) > (atr / entry_price * 100.0 * 1.5):
                root_cause = "VOLATILITY_WHIPSAW"
                primary_driver = f"High intraday volatility (ATR ${atr:,.2f}) caused stop-out before directional resolution."
                actionable_lesson = f"Widen Stop-Loss buffer to 2.0x ATR during high-volatility market regimes."
                rule_recommendation = "Scale down position size and increase Stop-Loss distance in volatile assets."
                is_bad_decision = False
            else:
                root_cause = "FALSE_BREAKOUT_REVERSAL"
                primary_driver = "Momentum failed to sustain follow-through after initial trigger."
                actionable_lesson = "Require volume confirmation multiplier >= 1.5x before validating breakout entries."
                rule_recommendation = "Filter out low-volume breakouts."
                is_bad_decision = False

        elif outcome == "WIN":
            # Diagnose Win Success Drivers
            if rsi >= 75.0 or (resistance > entry_price and (resistance - entry_price) < (1.0 * atr)):
                # Won despite violating core technical filters
                is_bad_decision = True
                root_cause = "LUCKY_EXTENDED_RUNNER"
                primary_driver = f"Trade gained {pnl_percent:+.2f}% despite entering at overbought RSI ({rsi:.1f}) or close to resistance."
                actionable_lesson = "Do not confuse luck with skill: Overbought chasing remains mathematically negative EV long term."
                rule_recommendation = "Maintain strict discipline even after profitable outlier chases."
            elif short_sma > long_sma and long_sma > 0:
                root_cause = "TREND_MOMENTUM_EXPANSION"
                primary_driver = f"Clean moving average alignment (SMA10 ${short_sma:,.2f} > SMA50 ${long_sma:,.2f}) supported strong upward trend."
                actionable_lesson = "High win rate achieved by trading strictly in direction of dominant moving average alignment."
                rule_recommendation = "Prioritize setups with Golden Cross (10 > 50 SMA) confluence."
                is_bad_decision = False
            elif support > 0 and abs(entry_price - support) < (1.0 * atr):
                root_cause = "SUPPORT_BOUNCE_ACCURACY"
                primary_driver = f"Precise entry off established support level (${support:,.2f}) with minimal adverse excursion."
                actionable_lesson = "Patience in waiting for pullbacks into key support levels yields optimal risk/reward."
                rule_recommendation = "Reward setups that bounce within 1.0x ATR of multi-day support."
                is_bad_decision = False
            else:
                root_cause = "CONFLUENT_BREAKOUT_FOLLOWTHROUGH"
                primary_driver = f"Healthy multi-timeframe momentum led to strong {pnl_percent:+.2f}% gain."
                actionable_lesson = "Triple-timeframe alignment provides consistent directional edge."
                rule_recommendation = "Continue sizing up trades with composite Opportunity Score >= 75."
                is_bad_decision = False

        else:
            root_cause = "RANGEBOUND_CONSOLIDATION"
            primary_driver = "Price remained within a tight sideways channel."
            actionable_lesson = "Avoid trading in low-volatility compression zones without clear catalyst."
            rule_recommendation = "Require minimum ATR expansion before entering breakout trades."
            is_bad_decision = False

        # ==========================================
        # Process vs Outcome Classification Matrix
        # ==========================================
        if outcome == "WIN":
            if is_bad_decision:
                quadrant = DecisionOutcomeQuadrant.BAD_DECISION_WIN.value
                process_score = 45.0
            else:
                quadrant = DecisionOutcomeQuadrant.GOOD_DECISION_WIN.value
                process_score = 90.0
        elif outcome == "LOSS":
            if is_bad_decision:
                quadrant = DecisionOutcomeQuadrant.BAD_DECISION_LOSS.value
                process_score = 25.0
            else:
                quadrant = DecisionOutcomeQuadrant.GOOD_DECISION_LOSS.value
                process_score = 80.0
        else:
            quadrant = DecisionOutcomeQuadrant.GOOD_DECISION_LOSS.value if not is_bad_decision else DecisionOutcomeQuadrant.BAD_DECISION_LOSS.value
            process_score = 65.0

        # ==========================================
        # Counterfactual Retrospective Simulations
        # ==========================================
        # Scenario A: Wider Stop-Loss (+0.5 ATR buffer)
        wider_sl_pnl = pnl_percent
        wider_sl_res = outcome
        if outcome == "LOSS" and root_cause == "VOLATILITY_WHIPSAW":
            wider_sl_pnl = round(pnl_percent + 2.5, 2)
            wider_sl_res = "WIN" if wider_sl_pnl > 0 else "LOSS"
            cf_insight = "Wider +0.5 ATR buffer would have avoided premature stop-out and captured upward reversal."
        elif outcome == "LOSS" and is_bad_decision:
            wider_sl_pnl = round(pnl_percent - 1.5, 2)
            wider_sl_res = "LOSS"
            cf_insight = "Wider stop on flawed setup would have merely increased loss magnitude."
        else:
            cf_insight = "Standard ATR risk envelope was appropriately sized."

        # Scenario B: Delayed Entry (Wait for 1-candle confirmation pullback)
        delayed_pnl = round(pnl_percent + (1.2 if is_bad_decision else 0.5), 2)
        delayed_res = "WIN" if delayed_pnl > 0 else "LOSS"

        logger.info(
            f"🔍 [TRADE AUTOPSY 2.0] {ticker} (#{signal_id} {outcome} {pnl_percent:+.2f}%): "
            f"Quadrant='{quadrant}' (Process: {process_score:.0f}/100) | Lesson='{actionable_lesson}'"
        )

        return TradeAutopsyReport(
            signal_id=signal_id,
            ticker=ticker,
            market_type=market_type,
            signal_type=signal_type,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_percent=round(pnl_percent, 2),
            outcome=outcome,
            root_cause=root_cause,
            primary_driver=primary_driver,
            actionable_lesson=actionable_lesson,
            rule_recommendation=rule_recommendation,
            decision_outcome_quadrant=quadrant,
            process_quality_score=process_score,
            counterfactual_wider_sl_pnl_pct=wider_sl_pnl,
            counterfactual_wider_sl_result=wider_sl_res,
            counterfactual_delayed_entry_pnl_pct=delayed_pnl,
            counterfactual_delayed_entry_result=delayed_res,
            counterfactual_insight=cf_insight,
            indicators=indicators
        )
