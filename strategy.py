"""
Trading Strategy Module
Implements customizable trading rules, technical indicator evaluation (SMA & Dip threshold),
risk management checks, and signal generation.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Any, Literal
from services.market_data import YFinanceClient, MarketDataClient, AlphaVantageClient, MarketQuote
from services.trading212 import Trading212Client, Position, AccountCash
from config import Settings

logger = logging.getLogger(__name__)


@dataclass
class TradeDecision:
    """Represents the output decision of the strategy evaluation."""
    ticker: str
    action: Literal["BUY", "SELL", "HOLD"]
    current_price: float
    target_quantity: float
    target_value: float
    reason: str
    indicators: Dict[str, Any]
    should_execute: bool = False


class DipAndMovingAverageStrategy:
    """
    Evaluates market conditions for watchlist tickers based on:
    1. Dip below Simple Moving Average (SMA) or recent high.
    2. Short-term vs Long-term SMA trend direction.
    3. Portfolio cash availability and risk exposure limits.
    """

    def __init__(
        self,
        config: Settings,
        market_client: YFinanceClient,
        broker_client: Trading212Client
    ):
        self.config = config
        self.market_client = market_client
        self.broker_client = broker_client

    def evaluate_ticker(
        self,
        ticker: str,
        cash: AccountCash,
        current_position: Optional[Position]
    ) -> TradeDecision:
        """
        Evaluates a single ticker and returns a TradeDecision.
        """
        logger.info(f"Evaluating strategy for ticker: {ticker}")

        # 1. Fetch live market quote
        try:
            quote = self.market_client.get_quote(ticker)
        except Exception as e:
            logger.error(f"Failed to fetch quote for {ticker}: {e}")
            return TradeDecision(
                ticker=ticker,
                action="HOLD",
                current_price=0.0,
                target_quantity=0.0,
                target_value=0.0,
                reason=f"Failed to fetch market quote: {e}",
                indicators={},
                should_execute=False
            )

        current_price = quote.price
        if current_price <= 0:
            return TradeDecision(
                ticker=ticker,
                action="HOLD",
                current_price=0.0,
                target_quantity=0.0,
                target_value=0.0,
                reason="Invalid price ($0.00)",
                indicators={},
                should_execute=False
            )

        # 2. Fetch or calculate moving averages
        short_sma = 0.0
        long_sma = 0.0
        try:
            short_sma = self.market_client.calculate_sma(ticker, period=self.config.sma_short_period)
        except Exception as e:
            logger.warning(f"Could not calculate short SMA({self.config.sma_short_period}) for {ticker}: {e}")

        try:
            long_sma = self.market_client.calculate_sma(ticker, period=self.config.sma_long_period)
        except Exception as e:
            logger.warning(f"Could not calculate long SMA({self.config.sma_long_period}) for {ticker}: {e}")

        indicators = {
            "current_price": current_price,
            "change_percent": quote.change_percent,
            "short_sma": short_sma,
            "long_sma": long_sma,
            "available_cash": cash.free,
            "current_position_qty": current_position.quantity if current_position else 0.0,
            "position_ppl": current_position.ppl if current_position else 0.0,
        }

        # 3. Calculate dip metrics
        benchmark_sma = short_sma if short_sma > 0 else (long_sma if long_sma > 0 else quote.previous_close)
        dip_percentage = 0.0
        if benchmark_sma > 0:
            dip_percentage = ((benchmark_sma - current_price) / benchmark_sma) * 100.0
        indicators["dip_percentage"] = round(dip_percentage, 2)

        # --- Decision Rules ---

        # Rule A: Risk Check - Do we have enough cash for allocation?
        allocation_value = min(self.config.buy_allocation_value, self.config.t212_max_order_value)
        if cash.free < allocation_value:
            return TradeDecision(
                ticker=ticker,
                action="HOLD",
                current_price=current_price,
                target_quantity=0.0,
                target_value=0.0,
                reason=f"Insufficient free cash (${cash.free:.2f}) for minimum buy allocation (${allocation_value:.2f})",
                indicators=indicators,
                should_execute=False
            )

        # Rule B: BUY Condition - Dip Threshold Met (Price is X% below SMA benchmark)
        if dip_percentage >= self.config.dip_threshold_percent:
            calculated_shares = round(allocation_value / current_price, 6)
            reason = (
                f"BUY Signal Triggered: Price (${current_price:,.2f}) dropped "
                f"{dip_percentage:.2f}% below benchmark SMA (${benchmark_sma:,.2f}), "
                f"exceeding threshold of {self.config.dip_threshold_percent}%."
            )
            return TradeDecision(
                ticker=ticker,
                action="BUY",
                current_price=current_price,
                target_quantity=calculated_shares,
                target_value=allocation_value,
                reason=reason,
                indicators=indicators,
                should_execute=True
            )

        # Rule C: Optional Golden Cross Trend (Short SMA > Long SMA and Daily Change > 0)
        if short_sma > long_sma > 0 and quote.change_percent > 1.5:
            calculated_shares = round(allocation_value / current_price, 6)
            reason = (
                f"BUY Signal Triggered (Trend Momentum): Short SMA {self.config.sma_short_period} (${short_sma:.2f}) "
                f"above Long SMA {self.config.sma_long_period} (${long_sma:.2f}) with +{quote.change_percent:.2f}% daily gain."
            )
            return TradeDecision(
                ticker=ticker,
                action="BUY",
                current_price=current_price,
                target_quantity=calculated_shares,
                target_value=allocation_value,
                reason=reason,
                indicators=indicators,
                should_execute=True
            )

        # Default: No trade triggers met
        reason = (
            f"HOLD: No entry condition met. Price is ${current_price:,.2f} "
            f"(Dip: {dip_percentage:.2f}% vs {self.config.dip_threshold_percent}% required)."
        )
        return TradeDecision(
            ticker=ticker,
            action="HOLD",
            current_price=current_price,
            target_quantity=0.0,
            target_value=0.0,
            reason=reason,
            indicators=indicators,
            should_execute=False
        )
