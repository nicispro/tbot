"""
Portfolio & Correlation Engine (KODA OS Phase 3)
Evaluates portfolio diversification, asset allocation limits, and calculates
asset price correlation matrix to prevent concentrated risk exposure.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

from services.trading212 import AccountCash, Position
from services.market_data import DailyBar, YFinanceClient
from services.crypto_data import CryptoDataClient

logger = logging.getLogger(__name__)


@dataclass
class CorrelationAssessment:
    """Represents the portfolio correlation and allocation risk assessment."""
    is_approved: bool
    candidate_ticker: str
    max_correlation: float
    highly_correlated_positions: List[Tuple[str, float]]
    crypto_allocation_percent: float
    stock_allocation_percent: float
    cash_reserve_percent: float
    rejection_reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class PortfolioBrain:
    """
    Manages portfolio correlation and asset allocation constraints.
    """

    def __init__(
        self,
        max_correlation_threshold: float = 0.85,
        max_highly_correlated_count: int = 2,
        max_crypto_allocation_percent: float = 40.0,
        max_single_asset_percent: float = 20.0,
        min_cash_reserve_percent: float = 10.0,
        stock_client: Optional[YFinanceClient] = None,
        crypto_client: Optional[CryptoDataClient] = None
    ):
        self.max_correlation_threshold = max_correlation_threshold
        self.max_highly_correlated_count = max_highly_correlated_count
        self.max_crypto_allocation_percent = max_crypto_allocation_percent
        self.max_single_asset_percent = max_single_asset_percent
        self.min_cash_reserve_percent = min_cash_reserve_percent
        self.stock_client = stock_client or YFinanceClient()
        self.crypto_client = crypto_client or CryptoDataClient()

    @staticmethod
    def calculate_returns_correlation(series_a: List[float], series_b: List[float]) -> float:
        """
        Calculates Pearson correlation coefficient between two price series' percentage returns.
        """
        if len(series_a) < 5 or len(series_b) < 5:
            return 0.0

        min_len = min(len(series_a), len(series_b))
        a = series_a[-min_len:]
        b = series_b[-min_len:]

        # Calculate daily percentage returns
        returns_a = [(a[i] - a[i - 1]) / a[i - 1] for i in range(1, len(a)) if a[i - 1] > 0]
        returns_b = [(b[i] - b[i - 1]) / b[i - 1] for i in range(1, len(b)) if b[i - 1] > 0]

        n = min(len(returns_a), len(returns_b))
        if n < 4:
            return 0.0

        r_a = returns_a[-n:]
        r_b = returns_b[-n:]

        mean_a = sum(r_a) / n
        mean_b = sum(r_b) / n

        numerator = sum((r_a[i] - mean_a) * (r_b[i] - mean_b) for i in range(n))
        denom_a = sum((r_a[i] - mean_a) ** 2 for i in range(n))
        denom_b = sum((r_b[i] - mean_b) ** 2 for i in range(n))

        denominator = math.sqrt(denom_a * denom_b)
        if denominator == 0.0:
            return 0.0

        corr = numerator / denominator
        return max(-1.0, min(1.0, round(corr, 3)))

    def _get_history_closes(self, ticker: str, market_type: str = "stock") -> List[float]:
        """Fetches historical closing prices for correlation calculation."""
        try:
            if market_type == "crypto" or "/" in ticker:
                bars = self.crypto_client.fetch_ohlcv(ticker, timeframe="1d", limit=30)
            else:
                bars = self.stock_client.get_daily_history(ticker, period="1mo")
            return [b.close for b in bars if b.close > 0]
        except Exception as e:
            logger.debug(f"Could not fetch closes for correlation for {ticker}: {e}")
            return []

    def evaluate_entry_risk(
        self,
        candidate_ticker: str,
        market_type: str,
        target_value: float,
        current_positions: Dict[str, Position],
        stock_cash: Optional[AccountCash] = None,
        crypto_cash: Optional[AccountCash] = None,
        candidate_history_closes: Optional[List[float]] = None
    ) -> CorrelationAssessment:
        """
        Evaluates portfolio correlation and allocation risk before entering a new position.
        """
        total_equity = 0.0
        free_cash = 0.0
        stock_invested = 0.0
        crypto_invested = 0.0

        if stock_cash:
            total_equity += stock_cash.total
            free_cash += stock_cash.free
            stock_invested += stock_cash.invested

        if crypto_cash:
            total_equity += crypto_cash.total
            free_cash += crypto_cash.free
            crypto_invested += crypto_cash.invested

        if total_equity <= 0.0:
            total_equity = max(100.0, free_cash + target_value)

        # 1. Allocation Checks
        crypto_pct = (crypto_invested / total_equity) * 100.0 if total_equity > 0 else 0.0
        stock_pct = (stock_invested / total_equity) * 100.0 if total_equity > 0 else 0.0
        cash_pct = (free_cash / total_equity) * 100.0 if total_equity > 0 else 100.0

        # Check Crypto Allocation Cap
        if market_type == "crypto" and (crypto_pct + (target_value / total_equity * 100.0)) > self.max_crypto_allocation_percent:
            return CorrelationAssessment(
                is_approved=False,
                candidate_ticker=candidate_ticker,
                max_correlation=0.0,
                highly_correlated_positions=[],
                crypto_allocation_percent=round(crypto_pct, 1),
                stock_allocation_percent=round(stock_pct, 1),
                cash_reserve_percent=round(cash_pct, 1),
                rejection_reason=f"Crypto allocation ({crypto_pct:.1f}%) would exceed max limit ({self.max_crypto_allocation_percent}%)."
            )

        # Check Single Asset Max Allocation Cap
        single_asset_pct = (target_value / total_equity) * 100.0
        if single_asset_pct > self.max_single_asset_percent:
            return CorrelationAssessment(
                is_approved=False,
                candidate_ticker=candidate_ticker,
                max_correlation=0.0,
                highly_correlated_positions=[],
                crypto_allocation_percent=round(crypto_pct, 1),
                stock_allocation_percent=round(stock_pct, 1),
                cash_reserve_percent=round(cash_pct, 1),
                rejection_reason=f"Single asset size ({single_asset_pct:.1f}%) exceeds max limit ({self.max_single_asset_percent}%)."
            )

        # 2. Correlation Checks against existing active positions
        candidate_closes = candidate_history_closes or self._get_history_closes(candidate_ticker, market_type)
        highly_correlated: List[Tuple[str, float]] = []
        max_corr = 0.0

        if candidate_closes and current_positions:
            for pos_ticker, pos in current_positions.items():
                if pos_ticker == candidate_ticker or pos.quantity <= 0:
                    continue

                pos_m_type = "crypto" if "/" in pos_ticker else "stock"
                pos_closes = self._get_history_closes(pos_ticker, pos_m_type)
                if pos_closes:
                    corr = self.calculate_returns_correlation(candidate_closes, pos_closes)
                    if abs(corr) > max_corr:
                        max_corr = abs(corr)
                    if corr >= self.max_correlation_threshold:
                        highly_correlated.append((pos_ticker, corr))

        if len(highly_correlated) >= self.max_highly_correlated_count:
            reasons = [f"{t} (r={c:.2f})" for t, c in highly_correlated]
            return CorrelationAssessment(
                is_approved=False,
                candidate_ticker=candidate_ticker,
                max_correlation=max_corr,
                highly_correlated_positions=highly_correlated,
                crypto_allocation_percent=round(crypto_pct, 1),
                stock_allocation_percent=round(stock_pct, 1),
                cash_reserve_percent=round(cash_pct, 1),
                rejection_reason=f"Excessive portfolio correlation: {candidate_ticker} is strongly correlated with {len(highly_correlated)} position(s): {', '.join(reasons)}."
            )

        logger.info(
            f"Portfolio Brain approved entry for {candidate_ticker}: "
            f"Max Corr={max_corr:.2f}, CryptoAlloc={crypto_pct:.1f}%, StockAlloc={stock_pct:.1f}%, CashReserve={cash_pct:.1f}%"
        )

        return CorrelationAssessment(
            is_approved=True,
            candidate_ticker=candidate_ticker,
            max_correlation=max_corr,
            highly_correlated_positions=highly_correlated,
            crypto_allocation_percent=round(crypto_pct, 1),
            stock_allocation_percent=round(stock_pct, 1),
            cash_reserve_percent=round(cash_pct, 1),
            rejection_reason=None,
            details={
                "total_equity": total_equity,
                "free_cash": free_cash
            }
        )
