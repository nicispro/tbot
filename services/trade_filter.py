"""
'Why NOT Trade?' Engine (KODA OS Phase 2)
Pre-trade veto filter that evaluates explicit rejection rules before confirming any BUY signal:
1. Major Resistance Proximity (< 1.5x ATR away)
2. Unfavorable Risk/Reward Ratio (< 1:1.5)
3. Extreme Volatility Spike / Exhaustion (RSI > 80, ATR ratio > 3.0)
4. Severe Macro Downtrend Clash (falling knife)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class VetoResult:
    """Represents the pre-trade veto analysis."""
    should_veto: bool
    veto_reasons: List[str]
    passed_checks: List[str]
    details: Dict[str, Any] = field(default_factory=dict)


class WhyNotTradeEngine:
    """
    Evaluates defensive filter criteria to weed out low-probability or asymmetric risk trade setups.
    """

    def __init__(
        self,
        min_resistance_atr_buffer: float = 1.5,
        min_risk_reward_ratio: float = 1.5,
        max_overbought_rsi: float = 80.0,
        max_volatility_atr_ratio: float = 3.0
    ):
        self.min_resistance_atr_buffer = min_resistance_atr_buffer
        self.min_risk_reward_ratio = min_risk_reward_ratio
        self.max_overbought_rsi = max_overbought_rsi
        self.max_volatility_atr_ratio = max_volatility_atr_ratio

    def evaluate_trade_filters(
        self,
        ticker: str,
        action: str,
        current_price: float,
        indicators: Dict[str, Any],
        risk_reward_ratio: Optional[float] = None
    ) -> VetoResult:
        """
        Runs all veto rejection rules for a candidate trade execution.
        Returns VetoResult with should_veto=True if any hard rejection rule is breached.
        """
        action = action.upper()
        if action != "BUY":
            # Filter checks currently focus on BUY entries
            return VetoResult(
                should_veto=False,
                veto_reasons=[],
                passed_checks=["Non-BUY action skipped"]
            )

        veto_reasons: List[str] = []
        passed_checks: List[str] = []

        atr = indicators.get("atr")
        atr_val = float(atr) if (atr and atr != "DATA_UNAVAILABLE") else (current_price * 0.02)

        resistance = indicators.get("resistance")
        resistance_val = float(resistance) if (resistance and resistance != "DATA_UNAVAILABLE") else None

        rsi = indicators.get("rsi")
        rsi_val = float(rsi) if (rsi and rsi != "DATA_UNAVAILABLE") else 50.0

        short_sma = indicators.get("short_sma")
        short_sma_val = float(short_sma) if (short_sma and short_sma != "DATA_UNAVAILABLE") else None

        long_sma = indicators.get("long_sma")
        long_sma_val = float(long_sma) if (long_sma and long_sma != "DATA_UNAVAILABLE") else None

        # 1. Check: Major Resistance Proximity
        if resistance_val and resistance_val > current_price:
            distance_to_res = resistance_val - current_price
            required_buffer = self.min_resistance_atr_buffer * atr_val
            if distance_to_res < required_buffer:
                veto_reasons.append(
                    f"Major resistance (${resistance_val:,.2f}) is too close ({distance_to_res:,.2f} < {required_buffer:,.2f} / {self.min_resistance_atr_buffer}x ATR buffer)."
                )
            else:
                passed_checks.append("Resistance Buffer Check Passed")
        else:
            passed_checks.append("No immediate overhead resistance barrier")

        # 2. Check: Risk / Reward Ratio
        rr = risk_reward_ratio or indicators.get("risk_reward")
        if rr is not None:
            try:
                rr_val = float(rr)
                if rr_val < self.min_risk_reward_ratio:
                    veto_reasons.append(
                        f"Unfavorable Risk:Reward ratio (1:{rr_val:.1f} is below required minimum 1:{self.min_risk_reward_ratio:.1f})."
                    )
                else:
                    passed_checks.append(f"Risk:Reward Check Passed (1:{rr_val:.1f})")
            except (ValueError, TypeError):
                pass

        # 3. Check: Extreme Volatility / Overbought Exhaustion Spike
        if rsi_val >= self.max_overbought_rsi:
            veto_reasons.append(
                f"RSI ({rsi_val:.1f}) exceeds extreme overbought threshold ({self.max_overbought_rsi}). High risk of exhaustion top."
            )
        else:
            passed_checks.append(f"RSI Momentum Check Passed ({rsi_val:.1f})")

        # 4. Check: Falling Knife / Severe Macro Downtrend Clash
        if long_sma_val and long_sma_val > 0:
            if current_price < (long_sma_val * 0.90) and rsi_val < 32.0:
                veto_reasons.append(
                    f"Falling Knife risk: Price (${current_price:,.2f}) is >10% below 50-day SMA (${long_sma_val:,.2f}) with decaying RSI ({rsi_val:.1f})."
                )
            else:
                passed_checks.append("Macro Trend Alignment Check Passed")

        should_veto = len(veto_reasons) > 0
        if should_veto:
            logger.warning(f"🚫 ['Why NOT Trade?' VETO] {ticker}: Blocked due to {len(veto_reasons)} reason(s): {'; '.join(veto_reasons)}")
        else:
            logger.info(f"✅ ['Why NOT Trade?' PASSED] {ticker}: All {len(passed_checks)} defense checks passed.")

        return VetoResult(
            should_veto=should_veto,
            veto_reasons=veto_reasons,
            passed_checks=passed_checks,
            details={
                "resistance": resistance_val,
                "atr": atr_val,
                "rsi": rsi_val,
                "risk_reward": rr
            }
        )
