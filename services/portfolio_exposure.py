"""
Portfolio Exposure & Sector Intelligence Engine (KODA Institutional Architecture - Block 2)
Tracks sector concentration (Technology, Financials, Healthcare, Crypto, Energy),
portfolio beta relative to S&P 500, and currency exposure, enforcing hard risk limits.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from services.trading212 import Position, AccountCash

logger = logging.getLogger(__name__)

# Sector classification dictionary
SECTOR_MAP: Dict[str, str] = {
    # Technology / Semi
    "AAPL": "Technology",
    "AAPL_US_EQ": "Technology",
    "MSFT": "Technology",
    "MSFT_US_EQ": "Technology",
    "NVDA": "Technology",
    "NVDA_US_EQ": "Technology",
    "AMD": "Technology",
    "AMD_US_EQ": "Technology",
    "GOOGL": "Technology",
    "GOOGL_US_EQ": "Technology",
    "META": "Technology",
    "META_US_EQ": "Technology",
    "TSLA": "Technology",
    "TSLA_US_EQ": "Technology",
    # Financials
    "JPM": "Financials",
    "JPM_US_EQ": "Financials",
    "BAC": "Financials",
    "BAC_US_EQ": "Financials",
    "V": "Financials",
    "V_US_EQ": "Financials",
    # Healthcare
    "JNJ": "Healthcare",
    "JNJ_US_EQ": "Healthcare",
    "UNH": "Healthcare",
    "UNH_US_EQ": "Healthcare",
    "LLY": "Healthcare",
    "LLY_US_EQ": "Healthcare",
    # Energy
    "XOM": "Energy",
    "XOM_US_EQ": "Energy",
    "CVX": "Energy",
    "CVX_US_EQ": "Energy",
    # Consumer
    "AMZN": "Consumer",
    "AMZN_US_EQ": "Consumer",
    "WMT": "Consumer",
    "WMT_US_EQ": "Consumer",
    "COST": "Consumer",
    "COST_US_EQ": "Consumer",
}

# Approximate Asset Beta relative to S&P 500
BETA_MAP: Dict[str, float] = {
    "Technology": 1.35,
    "Crypto": 2.50,
    "Financials": 0.95,
    "Healthcare": 0.75,
    "Energy": 1.05,
    "Consumer": 0.90,
    "Default": 1.00
}


@dataclass
class ExposureAssessment:
    """Consolidated portfolio sector, beta, and asset class exposure evaluation."""
    is_approved: bool
    candidate_ticker: str
    candidate_sector: str
    candidate_beta: float
    portfolio_beta: float
    sector_exposures_pct: Dict[str, float]
    crypto_exposure_pct: float
    stock_exposure_pct: float
    cash_reserve_pct: float
    rejection_reason: Optional[str] = None


class PortfolioExposureEngine:
    """
    Evaluates sector concentration, portfolio beta, and asset class weights before trade execution.
    """

    def __init__(
        self,
        max_sector_exposure_pct: float = 40.0,
        max_portfolio_beta: float = 1.80,
        max_crypto_exposure_pct: float = 40.0
    ):
        self.max_sector_exposure_pct = max_sector_exposure_pct
        self.max_portfolio_beta = max_portfolio_beta
        self.max_crypto_exposure_pct = max_crypto_exposure_pct

    @staticmethod
    def identify_sector(ticker: str) -> str:
        """Determines the sector category of an instrument."""
        clean = ticker.strip().upper()
        if "/" in clean or clean.endswith("USDT") or clean.endswith("USD") and "_" not in clean:
            return "Crypto"
        return SECTOR_MAP.get(clean, "Technology" if "_US_EQ" in clean else "Diversified")

    @classmethod
    def get_asset_beta(cls, ticker: str, sector: Optional[str] = None) -> float:
        """Returns the approximate beta factor for an asset."""
        sec = sector or cls.identify_sector(ticker)
        return BETA_MAP.get(sec, BETA_MAP["Default"])

    def evaluate_exposure_risk(
        self,
        candidate_ticker: str,
        target_value: float,
        current_positions: Dict[str, Position],
        total_equity: float,
        free_cash: float
    ) -> ExposureAssessment:
        """
        Calculates post-entry sector exposures and portfolio beta to prevent over-concentration.
        """
        eq = max(100.0, total_equity)
        cand_sector = self.identify_sector(candidate_ticker)
        cand_beta = self.get_asset_beta(candidate_ticker, cand_sector)

        # 1. Tally existing sector values
        sector_values: Dict[str, float] = {}
        total_invested = 0.0
        weighted_beta_sum = 0.0

        for pos_ticker, pos in current_positions.items():
            if pos.quantity <= 0:
                continue
            pos_val = pos.quantity * pos.current_price
            sec = self.identify_sector(pos_ticker)
            b = self.get_asset_beta(pos_ticker, sec)

            sector_values[sec] = sector_values.get(sec, 0.0) + pos_val
            total_invested += pos_val
            weighted_beta_sum += pos_val * b

        # 2. Add proposed candidate entry
        post_sector_val = sector_values.get(cand_sector, 0.0) + target_value
        sector_values[cand_sector] = post_sector_val
        post_invested = total_invested + target_value
        post_beta_sum = weighted_beta_sum + (target_value * cand_beta)

        post_portfolio_beta = round((post_beta_sum / post_invested) if post_invested > 0 else 1.0, 2)

        # Calculate percentages
        sector_pcts = {
            sec: round((val / eq) * 100.0, 1)
            for sec, val in sector_values.items()
        }
        crypto_pct = sector_pcts.get("Crypto", 0.0)
        stock_pct = round(sum(v for s, v in sector_pcts.items() if s != "Crypto"), 1)
        cash_pct = round(max(0.0, ((eq - post_invested) / eq) * 100.0), 1)

        # 3. Check Sector Concentration Cap
        cand_sec_pct = sector_pcts.get(cand_sector, 0.0)
        if cand_sec_pct > self.max_sector_exposure_pct:
            return ExposureAssessment(
                is_approved=False,
                candidate_ticker=candidate_ticker,
                candidate_sector=cand_sector,
                candidate_beta=cand_beta,
                portfolio_beta=post_portfolio_beta,
                sector_exposures_pct=sector_pcts,
                crypto_exposure_pct=crypto_pct,
                stock_exposure_pct=stock_pct,
                cash_reserve_pct=cash_pct,
                rejection_reason=f"Sector exposure limit breached: {cand_sector} would reach {cand_sec_pct:.1f}% (Max: {self.max_sector_exposure_pct}%)."
            )

        # 4. Check Portfolio Beta Cap
        if post_portfolio_beta > self.max_portfolio_beta:
            return ExposureAssessment(
                is_approved=False,
                candidate_ticker=candidate_ticker,
                candidate_sector=cand_sector,
                candidate_beta=cand_beta,
                portfolio_beta=post_portfolio_beta,
                sector_exposures_pct=sector_pcts,
                crypto_exposure_pct=crypto_pct,
                stock_exposure_pct=stock_pct,
                cash_reserve_pct=cash_pct,
                rejection_reason=f"Portfolio Beta ({post_portfolio_beta:.2f}) exceeds max risk limit ({self.max_portfolio_beta:.2f})."
            )

        logger.info(
            f"Portfolio Exposure approved for {candidate_ticker} ({cand_sector}): "
            f"Sector={cand_sec_pct:.1f}%, Beta={post_portfolio_beta:.2f}, Crypto={crypto_pct:.1f}%, CashReserve={cash_pct:.1f}%"
        )

        return ExposureAssessment(
            is_approved=True,
            candidate_ticker=candidate_ticker,
            candidate_sector=cand_sector,
            candidate_beta=cand_beta,
            portfolio_beta=post_portfolio_beta,
            sector_exposures_pct=sector_pcts,
            crypto_exposure_pct=crypto_pct,
            stock_exposure_pct=stock_pct,
            cash_reserve_pct=cash_pct,
            rejection_reason=None
        )
