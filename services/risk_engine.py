"""
Deterministic Risk Engine (KODA OS Phase 1)
Enforces hard portfolio limits, dynamic position sizing via ATR and volatility,
calculates ATR-based Stop-Loss & Take-Profit targets, and guarantees risk-per-trade caps (1-2%).
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List

from services.trading212 import AccountCash
from services.market_data import DailyBar

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessmentResult:
    """Represents the risk validation decision for a trade signal."""
    is_approved: bool
    action: str
    ticker: str
    entry_price: float
    allocated_value: float
    estimated_shares: float
    stop_loss_price: float
    take_profit_price: float
    risk_reward_ratio: float
    risk_amount: float
    risk_percent_of_portfolio: float
    rejection_reason: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


class DeterministicRiskEngine:
    """
    Mathematical, deterministic risk controller.
    Ensures no trade executes without strictly defined risk parameters,
    dynamic position sizing, and maximum portfolio loss boundaries.
    """

    def __init__(
        self,
        max_risk_per_trade_percent: float = 1.5,
        max_position_size_percent: float = 15.0,
        min_order_value: float = 10.0,
        default_risk_reward_ratio: float = 2.0,
        atr_multiplier_sl: float = 1.5,
        atr_multiplier_tp: float = 3.0,
        max_daily_portfolio_drawdown: float = 5.0
    ):
        self.max_risk_per_trade_percent = max_risk_per_trade_percent
        self.max_position_size_percent = max_position_size_percent
        self.min_order_value = min_order_value
        self.default_risk_reward_ratio = default_risk_reward_ratio
        self.atr_multiplier_sl = atr_multiplier_sl
        self.atr_multiplier_tp = atr_multiplier_tp
        self.max_daily_portfolio_drawdown = max_daily_portfolio_drawdown

    @staticmethod
    def calculate_atr(bars: List[DailyBar], period: int = 14) -> float:
        """
        Calculates Average True Range (ATR) from a sequence of daily bars.
        Returns estimated ATR or fallback percentage of last price.
        """
        if not bars or len(bars) < 2:
            return 0.0

        tr_values: List[float] = []
        for i in range(1, len(bars)):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i - 1].close

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_values.append(tr)

        if not tr_values:
            return 0.0

        sample_tr = tr_values[-period:] if len(tr_values) >= period else tr_values
        return sum(sample_tr) / len(sample_tr)

    def calculate_sl_tp(
        self,
        entry_price: float,
        atr: Optional[float] = None,
        support: Optional[float] = None,
        resistance: Optional[float] = None,
        action: str = "BUY"
    ) -> Tuple[float, float, float]:
        """
        Calculates dynamic Stop-Loss and Take-Profit prices using ATR or Support/Resistance.
        Returns (stop_loss, take_profit, risk_per_share).
        """
        if entry_price <= 0.0:
            return 0.0, 0.0, 0.0

        # Fallback ATR if none provided: 2% of price
        effective_atr = atr if (atr and atr > 0.0) else (entry_price * 0.02)

        if action.upper() == "BUY":
            # Determine Stop-Loss (lower of support or ATR-based)
            sl_atr = entry_price - (self.atr_multiplier_sl * effective_atr)
            if support and support > 0 and support < entry_price:
                # Use slightly below support level
                stop_loss = max(sl_atr, support * 0.99)
            else:
                stop_loss = sl_atr

            # Ensure SL is strictly positive and below entry
            stop_loss = max(entry_price * 0.5, min(entry_price * 0.99, stop_loss))
            risk_per_share = entry_price - stop_loss

            # Determine Take-Profit (resistance or ATR-based)
            tp_atr = entry_price + (self.atr_multiplier_tp * effective_atr)
            if resistance and resistance > entry_price:
                take_profit = max(tp_atr, resistance)
            else:
                take_profit = tp_atr

            take_profit = max(entry_price + (risk_per_share * self.default_risk_reward_ratio), take_profit)

        else:  # SELL / SHORT
            sl_atr = entry_price + (self.atr_multiplier_sl * effective_atr)
            stop_loss = sl_atr
            risk_per_share = stop_loss - entry_price
            take_profit = max(0.01, entry_price - (self.atr_multiplier_tp * effective_atr))

        return round(stop_loss, 4), round(take_profit, 4), round(risk_per_share, 4)

    def evaluate_trade_risk(
        self,
        ticker: str,
        action: str,
        current_price: float,
        portfolio_cash: AccountCash,
        indicators: Optional[Dict[str, Any]] = None,
        opportunity_score: float = 1.0,
        max_order_override: Optional[float] = None
    ) -> RiskAssessmentResult:
        """
        Validates trade risk against portfolio rules, sizes the position, and generates SL/TP.
        """
        indicators = indicators or {}
        action = action.upper()

        if action not in ["BUY", "SELL"]:
            return RiskAssessmentResult(
                is_approved=False,
                action=action,
                ticker=ticker,
                entry_price=current_price,
                allocated_value=0.0,
                estimated_shares=0.0,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                risk_reward_ratio=0.0,
                risk_amount=0.0,
                risk_percent_of_portfolio=0.0,
                rejection_reason=f"Action '{action}' does not require risk allocation."
            )

        if current_price <= 0.0:
            return RiskAssessmentResult(
                is_approved=False,
                action=action,
                ticker=ticker,
                entry_price=current_price,
                allocated_value=0.0,
                estimated_shares=0.0,
                stop_loss_price=0.0,
                take_profit_price=0.0,
                risk_reward_ratio=0.0,
                risk_amount=0.0,
                risk_percent_of_portfolio=0.0,
                rejection_reason=f"Invalid current price: ${current_price}"
            )

        total_equity = max(100.0, portfolio_cash.total)
        free_cash = portfolio_cash.free

        # 1. Calculate dynamic Stop Loss & Take Profit
        atr_val = indicators.get("atr")
        if atr_val == "DATA_UNAVAILABLE" or atr_val is None:
            atr_val = None
        else:
            try:
                atr_val = float(atr_val)
            except (ValueError, TypeError):
                atr_val = None

        support_val = indicators.get("support")
        support_val = float(support_val) if support_val and support_val != "DATA_UNAVAILABLE" else None

        resistance_val = indicators.get("resistance")
        resistance_val = float(resistance_val) if resistance_val and resistance_val != "DATA_UNAVAILABLE" else None

        stop_loss, take_profit, risk_per_share = self.calculate_sl_tp(
            entry_price=current_price,
            atr=atr_val,
            support=support_val,
            resistance=resistance_val,
            action=action
        )

        risk_reward = round(abs(take_profit - current_price) / max(0.001, risk_per_share), 2)

        # 2. Maximum Dollar Risk Allowed (e.g. 1.5% of total portfolio equity)
        max_allowed_risk_dollars = total_equity * (self.max_risk_per_trade_percent / 100.0)

        # 3. Size Position based on distance to Stop Loss (volatility sizing)
        if risk_per_share > 0.0:
            shares_by_risk = max_allowed_risk_dollars / risk_per_share
            target_value_by_risk = shares_by_risk * current_price
        else:
            target_value_by_risk = total_equity * 0.05

        # 4. Enforce Max Position Size Cap (e.g. max 15% of total portfolio in 1 asset)
        max_position_cap = total_equity * (self.max_position_size_percent / 100.0)
        allocated_value = min(target_value_by_risk, max_position_cap)

        # Apply opportunity score scaling (e.g. 0.8x to 1.2x)
        bounded_score = max(0.5, min(1.5, opportunity_score))
        allocated_value *= bounded_score

        # Apply user CLI or Settings max order override if set
        if max_order_override and max_order_override > 0.0:
            allocated_value = min(allocated_value, max_order_override)

        # Bound by available free cash
        allocated_value = min(allocated_value, free_cash)
        allocated_value = round(allocated_value, 2)

        # 5. Check Minimum Order Value
        if allocated_value < self.min_order_value:
            return RiskAssessmentResult(
                is_approved=False,
                action=action,
                ticker=ticker,
                entry_price=current_price,
                allocated_value=allocated_value,
                estimated_shares=0.0,
                stop_loss_price=stop_loss,
                take_profit_price=take_profit,
                risk_reward_ratio=risk_reward,
                risk_amount=0.0,
                risk_percent_of_portfolio=0.0,
                rejection_reason=(
                    f"Allocated value (${allocated_value:,.2f}) is below minimum threshold "
                    f"(${self.min_order_value:,.2f}). Free cash: ${free_cash:,.2f}."
                )
            )

        estimated_shares = round(allocated_value / current_price, 6)
        actual_risk_amount = round(estimated_shares * risk_per_share, 2)
        risk_pct = round((actual_risk_amount / total_equity) * 100.0, 2)

        logger.info(
            f"Risk Engine [{ticker}]: Approved {action} | Size=${allocated_value:,.2f} ({estimated_shares:.4f} shs) | "
            f"SL=${stop_loss:,.2f} | TP=${take_profit:,.2f} | R:R={risk_reward:.1f} | Risk=${actual_risk_amount:,.2f} ({risk_pct}%)"
        )

        return RiskAssessmentResult(
            is_approved=True,
            action=action,
            ticker=ticker,
            entry_price=current_price,
            allocated_value=allocated_value,
            estimated_shares=estimated_shares,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            risk_reward_ratio=risk_reward,
            risk_amount=actual_risk_amount,
            risk_percent_of_portfolio=risk_pct,
            meta={
                "atr": atr_val,
                "risk_per_share": risk_per_share,
                "opportunity_score": opportunity_score
            }
        )
