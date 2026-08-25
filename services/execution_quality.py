"""
Execution Quality Engine (KODA Institutional Architecture - Block 3)
Tracks expected vs. actual fill prices, slippage in basis points (bps),
execution latency (ms), and exchange/broker fees, persisting metrics for auditability.
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ExecutionMetrics:
    """Quantitative measurement of trade execution quality."""
    order_id: str
    ticker: str
    action: str
    market_type: str
    expected_price: float
    filled_price: float
    slippage_pct: float
    slippage_bps: float
    execution_latency_ms: float
    fee_usd: float
    filled_quantity: float
    status: str
    timestamp: float = 0.0


class ExecutionQualityEngine:
    """
    Measures and logs broker execution efficiency, slippage, and latencies.
    """

    DB_FILE = "trading_outcomes.db"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self.DB_FILE
        self._init_db()

    def _init_db(self) -> None:
        """Initializes execution metrics table in SQLite/Postgres."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS execution_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id TEXT,
                        ticker TEXT,
                        action TEXT,
                        market_type TEXT,
                        expected_price REAL,
                        filled_price REAL,
                        slippage_pct REAL,
                        slippage_bps REAL,
                        execution_latency_ms REAL,
                        fee_usd REAL,
                        filled_quantity REAL,
                        status TEXT,
                        timestamp REAL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize execution metrics DB: {e}")

    def calculate_slippage(
        self,
        action: str,
        expected_price: float,
        filled_price: float
    ) -> tuple[float, float]:
        """
        Calculates slippage percentage and basis points (bps).
        For BUY: Positive slippage = filled higher than expected (adverse).
        For SELL: Positive slippage = filled lower than expected (adverse).
        """
        if expected_price <= 0.0:
            return 0.0, 0.0

        if action.upper() == "BUY":
            slippage_pct = ((filled_price - expected_price) / expected_price) * 100.0
        else:
            slippage_pct = ((expected_price - filled_price) / expected_price) * 100.0

        slippage_bps = slippage_pct * 100.0
        return round(slippage_pct, 4), round(slippage_bps, 2)

    def record_execution(
        self,
        order_id: str,
        ticker: str,
        action: str,
        market_type: str,
        expected_price: float,
        filled_price: float,
        filled_quantity: float,
        latency_ms: float,
        fee_usd: float = 0.0,
        status: str = "FILLED"
    ) -> ExecutionMetrics:
        """
        Records execution outcome, computes slippage and latency metrics, and stores to DB.
        """
        effective_fill = filled_price if filled_price > 0 else expected_price
        slip_pct, slip_bps = self.calculate_slippage(action, expected_price, effective_fill)
        ts = time.time()

        metrics = ExecutionMetrics(
            order_id=str(order_id),
            ticker=ticker,
            action=action.upper(),
            market_type=market_type.lower(),
            expected_price=expected_price,
            filled_price=effective_fill,
            slippage_pct=slip_pct,
            slippage_bps=slip_bps,
            execution_latency_ms=round(latency_ms, 2),
            fee_usd=round(fee_usd, 4),
            filled_quantity=filled_quantity,
            status=status,
            timestamp=ts
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO execution_metrics (
                        order_id, ticker, action, market_type, expected_price, filled_price,
                        slippage_pct, slippage_bps, execution_latency_ms, fee_usd, filled_quantity, status, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metrics.order_id, metrics.ticker, metrics.action, metrics.market_type,
                    metrics.expected_price, metrics.filled_price, metrics.slippage_pct,
                    metrics.slippage_bps, metrics.execution_latency_ms, metrics.fee_usd,
                    metrics.filled_quantity, metrics.status, metrics.timestamp
                ))
                conn.commit()
            logger.info(
                f"⚡ [EXECUTION QUALITY] {ticker} {action} | Fill=${effective_fill:,.2f} vs Exp=${expected_price:,.2f} "
                f"| Slippage: {slip_bps:+.1f} bps | Latency: {latency_ms:.1f}ms | Fee: ${fee_usd:.2f}"
            )
        except Exception as e:
            logger.error(f"Failed to persist execution metrics for {ticker}: {e}")

        return metrics

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Computes aggregate execution statistics (average slippage bps, latency, fees).
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        COUNT(*),
                        AVG(slippage_bps),
                        MAX(slippage_bps),
                        AVG(execution_latency_ms),
                        SUM(fee_usd)
                    FROM execution_metrics
                """)
                row = cursor.fetchone()
                if row and row[0] and row[0] > 0:
                    return {
                        "total_executions": row[0],
                        "avg_slippage_bps": round(row[1] or 0.0, 2),
                        "max_slippage_bps": round(row[2] or 0.0, 2),
                        "avg_latency_ms": round(row[3] or 0.0, 2),
                        "total_fees_usd": round(row[4] or 0.0, 2)
                    }
        except Exception as e:
            logger.debug(f"Failed to fetch execution summary: {e}")

        return {
            "total_executions": 0,
            "avg_slippage_bps": 0.0,
            "max_slippage_bps": 0.0,
            "avg_latency_ms": 0.0,
            "total_fees_usd": 0.0
        }

    def get_recent_executions(self, limit: int = 10) -> List[ExecutionMetrics]:
        """Returns the most recent executed trade fill records."""
        results: List[ExecutionMetrics] = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT order_id, ticker, action, market_type, expected_price,
                           filled_price, slippage_pct, slippage_bps, execution_latency_ms,
                           fee_usd, filled_quantity, status, timestamp
                    FROM execution_metrics
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                for row in cursor.fetchall():
                    results.append(ExecutionMetrics(
                        order_id=row[0],
                        ticker=row[1],
                        action=row[2],
                        market_type=row[3],
                        expected_price=row[4],
                        filled_price=row[5],
                        slippage_pct=row[6],
                        slippage_bps=row[7],
                        execution_latency_ms=row[8],
                        fee_usd=row[9],
                        filled_quantity=row[10],
                        status=row[11],
                        timestamp=row[12]
                    ))
        except Exception as e:
            logger.debug(f"Failed to fetch recent executions: {e}")
        return results
