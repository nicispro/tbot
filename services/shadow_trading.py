"""
Shadow Trading & Execution Sandbox (KODA Institutional Architecture - Block 5)
Executes simulated shadow trades in parallel with real-time market ticks without risking real money:
- Measures live tick slippage against theoretical trigger price.
- Tracks mark-to-market valuations and automated Stop-Loss / Take-Profit trigger hits.
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ShadowTrade:
    """Represents an active or closed paper trade in the Shadow Trading Sandbox."""
    shadow_id: str
    ticker: str
    market_type: str
    action: str
    signal_price: float
    simulated_fill_price: float
    simulated_slippage_bps: float
    quantity: float
    stop_loss: float
    take_profit: float
    current_price: float
    unrealized_pnl_pct: float = 0.0
    realized_pnl_pct: float = 0.0
    status: str = "OPEN"  # 'OPEN', 'CLOSED_TP', 'CLOSED_SL', 'CLOSED_MANUAL'
    created_at: float = field(default_factory=time.time)
    closed_at: Optional[float] = None


class ShadowTradingEngine:
    """
    Simulates real-time order execution and lifecycle tracking in shadow sandbox.
    """

    DB_FILE = "trading_outcomes.db"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self.DB_FILE
        self._init_db()

    def _init_db(self) -> None:
        """Initializes shadow trades table in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS shadow_trades (
                        shadow_id TEXT PRIMARY KEY,
                        ticker TEXT,
                        market_type TEXT,
                        action TEXT,
                        signal_price REAL,
                        simulated_fill_price REAL,
                        simulated_slippage_bps REAL,
                        quantity REAL,
                        stop_loss REAL,
                        take_profit REAL,
                        current_price REAL,
                        unrealized_pnl_pct REAL,
                        realized_pnl_pct REAL,
                        status TEXT,
                        created_at REAL,
                        closed_at REAL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize shadow trading DB: {e}")

    def open_shadow_trade(
        self,
        ticker: str,
        market_type: str,
        action: str,
        signal_price: float,
        current_tick_price: float,
        quantity: float,
        stop_loss: float,
        take_profit: float
    ) -> ShadowTrade:
        """
        Creates and persists a new shadow position using live market tick pricing.
        """
        fill = current_tick_price if current_tick_price > 0 else signal_price
        slip_pct = ((fill - signal_price) / signal_price) * 100.0 if signal_price > 0 else 0.0
        slip_bps = round(slip_pct * 100.0, 2)
        shadow_id = f"SHADOW-{int(time.time() * 1000)}-{ticker.replace('/', '_')}"

        trade = ShadowTrade(
            shadow_id=shadow_id,
            ticker=ticker,
            market_type=market_type.lower(),
            action=action.upper(),
            signal_price=round(signal_price, 4),
            simulated_fill_price=round(fill, 4),
            simulated_slippage_bps=slip_bps,
            quantity=round(quantity, 4),
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            current_price=round(fill, 4),
            unrealized_pnl_pct=0.0,
            realized_pnl_pct=0.0,
            status="OPEN",
            created_at=time.time()
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO shadow_trades (
                        shadow_id, ticker, market_type, action, signal_price,
                        simulated_fill_price, simulated_slippage_bps, quantity,
                        stop_loss, take_profit, current_price, unrealized_pnl_pct,
                        realized_pnl_pct, status, created_at, closed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.shadow_id, trade.ticker, trade.market_type, trade.action,
                    trade.signal_price, trade.simulated_fill_price, trade.simulated_slippage_bps,
                    trade.quantity, trade.stop_loss, trade.take_profit, trade.current_price,
                    trade.unrealized_pnl_pct, trade.realized_pnl_pct, trade.status,
                    trade.created_at, trade.closed_at
                ))
                conn.commit()
            logger.info(
                f"👻 [SHADOW TRADING] Opened {ticker} {action} @ ${fill:,.2f} "
                f"(Signal=${signal_price:,.2f}, Slip={slip_bps:+.1f} bps, SL=${stop_loss:,.2f}, TP=${take_profit:,.2f})"
            )
        except Exception as e:
            logger.error(f"Failed to open shadow trade for {ticker}: {e}")

        return trade

    def update_ticks(self, ticker_price_map: Dict[str, float]) -> List[ShadowTrade]:
        """
        Updates unrealized PnL and executes SL/TP trigger exits for open shadow positions.
        """
        updated_trades: List[ShadowTrade] = []
        open_trades = self.get_open_trades()

        for t in open_trades:
            if t.ticker not in ticker_price_map:
                continue

            live_p = ticker_price_map[t.ticker]
            t.current_price = live_p
            pnl_pct = ((live_p - t.simulated_fill_price) / t.simulated_fill_price) * 100.0 if t.simulated_fill_price > 0 else 0.0
            t.unrealized_pnl_pct = round(pnl_pct, 2)

            # Check SL trigger
            if t.action == "BUY" and t.stop_loss > 0 and live_p <= t.stop_loss:
                t.status = "CLOSED_SL"
                t.realized_pnl_pct = t.unrealized_pnl_pct
                t.closed_at = time.time()
                logger.info(f"👻 [SHADOW HIT SL] {t.ticker} hit Stop-Loss (${t.stop_loss:,.2f}): PnL={t.realized_pnl_pct:+.2f}%")

            # Check TP trigger
            elif t.action == "BUY" and t.take_profit > 0 and live_p >= t.take_profit:
                t.status = "CLOSED_TP"
                t.realized_pnl_pct = t.unrealized_pnl_pct
                t.closed_at = time.time()
                logger.info(f"👻 [SHADOW HIT TP] {t.ticker} hit Take-Profit (${t.take_profit:,.2f}): PnL={t.realized_pnl_pct:+.2f}%")

            self._update_trade(t)
            updated_trades.append(t)

        return updated_trades

    def _update_trade(self, t: ShadowTrade) -> None:
        """Persists updated shadow trade state."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE shadow_trades
                    SET current_price = ?, unrealized_pnl_pct = ?, realized_pnl_pct = ?,
                        status = ?, closed_at = ?
                    WHERE shadow_id = ?
                """, (t.current_price, t.unrealized_pnl_pct, t.realized_pnl_pct, t.status, t.closed_at, t.shadow_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update shadow trade {t.shadow_id}: {e}")

    def get_open_trades(self) -> List[ShadowTrade]:
        """Retrieves all currently active open shadow positions."""
        results: List[ShadowTrade] = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        shadow_id, ticker, market_type, action, signal_price,
                        simulated_fill_price, simulated_slippage_bps, quantity,
                        stop_loss, take_profit, current_price, unrealized_pnl_pct,
                        realized_pnl_pct, status, created_at, closed_at
                    FROM shadow_trades
                    WHERE status = 'OPEN'
                """)
                for r in cursor.fetchall():
                    results.append(ShadowTrade(
                        shadow_id=r[0],
                        ticker=r[1],
                        market_type=r[2],
                        action=r[3],
                        signal_price=r[4],
                        simulated_fill_price=r[5],
                        simulated_slippage_bps=r[6],
                        quantity=r[7],
                        stop_loss=r[8],
                        take_profit=r[9],
                        current_price=r[10],
                        unrealized_pnl_pct=r[11],
                        realized_pnl_pct=r[12],
                        status=r[13],
                        created_at=r[14],
                        closed_at=r[15]
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch open shadow trades: {e}")

        return results

    def get_performance_summary(self) -> Dict[str, Any]:
        """Calculates aggregate shadow trading performance metrics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        COUNT(*),
                        SUM(CASE WHEN realized_pnl_pct > 0 THEN 1 ELSE 0 END),
                        SUM(CASE WHEN realized_pnl_pct < 0 THEN 1 ELSE 0 END),
                        AVG(realized_pnl_pct),
                        AVG(simulated_slippage_bps)
                    FROM shadow_trades
                    WHERE status IN ('CLOSED_TP', 'CLOSED_SL', 'CLOSED_MANUAL')
                """)
                row = cursor.fetchone()
                total = row[0] or 0
                wins = row[1] or 0
                losses = row[2] or 0
                avg_pnl = row[3] or 0.0
                avg_slip = row[4] or 0.0
                win_rate = round((wins / total * 100.0), 1) if total > 0 else 0.0

                return {
                    "total_closed_trades": total,
                    "wins": wins,
                    "losses": losses,
                    "win_rate_pct": win_rate,
                    "avg_pnl_pct": round(avg_pnl, 2),
                    "avg_slippage_bps": round(avg_slip, 2)
                }
        except Exception as e:
            logger.error(f"Failed to fetch shadow performance summary: {e}")

        return {
            "total_closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "avg_pnl_pct": 0.0,
            "avg_slippage_bps": 0.0
        }
