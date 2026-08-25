"""
Automated Signal Outcome Tracker & Machine Learning Feedback Module
Persists all generated trading hypotheses (BUY/SELL) into an embedded SQLite database,
verifies forward-testing outcomes over time, computes strategy accuracy (Win Rate %, PnL),
and provides historical feedback to the AI Analyzer and Obsidian Learning Journal.
"""

import datetime
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Tuple

from services.market_data import YFinanceClient, MarketQuote
from services.crypto_data import CryptoDataClient

logger = logging.getLogger(__name__)

DB_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "signals.db")


@dataclass
class SignalRecord:
    """Represents a recorded trading signal hypothesis."""
    id: Optional[int]
    timestamp: datetime.datetime
    ticker: str
    market_type: str  # 'stock' or 'crypto'
    signal_type: str  # 'BUY' or 'SELL'
    price_at_signal: float
    indicators: Dict[str, Any]
    status: str = "pending"  # 'pending' or 'evaluated'
    evaluated_at: Optional[datetime.datetime] = None
    exit_price: Optional[float] = None
    pnl_percent: Optional[float] = None
    outcome: Optional[str] = None  # 'WIN', 'LOSS', 'NEUTRAL'
    notes: Optional[str] = None


class SignalTracker:
    """
    SQLite-backed signal hypothesis logger and forward-testing performance evaluator.
    """

    def __init__(self, db_path: str = DB_FILE_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes the signals table schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    price_at_signal REAL NOT NULL,
                    indicators TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    evaluated_at TEXT,
                    exit_price REAL,
                    pnl_percent REAL,
                    outcome TEXT,
                    notes TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp);")
            conn.commit()

    def record_signal(
        self,
        ticker: str,
        market_type: str,
        signal_type: str,
        price_at_signal: float,
        indicators: Dict[str, Any],
        notes: str = "",
        timestamp: Optional[datetime.datetime] = None
    ) -> int:
        """
        Saves a newly generated trade hypothesis signal into the database.
        """
        ts = timestamp or datetime.datetime.now(datetime.timezone.utc)
        ts_str = ts.isoformat()
        indicators_json = json.dumps(indicators)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signals (
                    timestamp, ticker, market_type, signal_type,
                    price_at_signal, indicators, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (
                ts_str,
                ticker.strip().upper(),
                market_type.lower(),
                signal_type.upper(),
                price_at_signal,
                indicators_json,
                notes
            ))
            conn.commit()
            signal_id = cursor.lastrowid
            logger.info(f"Recorded signal #{signal_id} for {ticker} ({signal_type} @ ${price_at_signal:,.2f})")
            return signal_id

    def get_pending_signals(
        self,
        older_than_hours: float = 24.0,
        market_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves pending signals that are at least `older_than_hours` old.
        """
        cutoff_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=older_than_hours)
        cutoff_iso = cutoff_dt.isoformat()

        query = "SELECT * FROM signals WHERE status = 'pending' AND timestamp <= ?"
        params: List[Any] = [cutoff_iso]

        if market_type:
            query += " AND market_type = ?"
            params.append(market_type.lower())

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def evaluate_past_signals(
        self,
        market_client: YFinanceClient,
        crypto_client: CryptoDataClient,
        stock_min_age_hours: float = 24.0,
        crypto_min_age_hours: float = 4.0
    ) -> List[Dict[str, Any]]:
        """
        Queries mature pending signals, fetches current market price, and classifies outcome (WIN/LOSS).
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        evaluated_results: List[Dict[str, Any]] = []

        # 1. Fetch pending stocks older than threshold
        pending_stocks = self.get_pending_signals(older_than_hours=stock_min_age_hours, market_type="stock")
        # 2. Fetch pending crypto older than threshold
        pending_crypto = self.get_pending_signals(older_than_hours=crypto_min_age_hours, market_type="crypto")

        all_pending = pending_stocks + pending_crypto
        if not all_pending:
            logger.info("No mature pending signals to evaluate at this time.")
            return []

        logger.info(f"Forward-testing {len(all_pending)} mature signal hypothesis outcomes...")

        for sig in all_pending:
            sig_id = sig["id"]
            ticker = sig["ticker"]
            market_type = sig["market_type"]
            signal_type = sig["signal_type"].upper()
            entry_price = float(sig["price_at_signal"])

            try:
                # Fetch current market price
                if market_type == "crypto":
                    quote: MarketQuote = crypto_client.get_quote(ticker)
                else:
                    quote = market_client.get_quote(ticker)

                current_price = quote.price
                if current_price <= 0.0:
                    continue

                # Calculate PnL percentage based on signal direction
                if signal_type == "BUY":
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
                elif signal_type == "SELL":
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100.0
                else:
                    pnl_pct = 0.0

                # Classify Outcome (Win threshold > +0.3%, Loss < -0.3%)
                if pnl_pct > 0.3:
                    outcome = "WIN"
                elif pnl_pct < -0.3:
                    outcome = "LOSS"
                else:
                    outcome = "NEUTRAL"

                # Update in SQLite DB
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE signals
                        SET status = 'evaluated',
                            evaluated_at = ?,
                            exit_price = ?,
                            pnl_percent = ?,
                            outcome = ?
                        WHERE id = ?
                    """, (
                        now.isoformat(),
                        round(current_price, 4),
                        round(pnl_pct, 2),
                        outcome,
                        sig_id
                    ))
                    conn.commit()

                eval_record = {
                    "id": sig_id,
                    "ticker": ticker,
                    "market_type": market_type,
                    "signal_type": signal_type,
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "pnl_percent": round(pnl_pct, 2),
                    "outcome": outcome,
                    "evaluated_at": now.isoformat(),
                    "signal_time": sig["timestamp"]
                }
                evaluated_results.append(eval_record)
                logger.info(
                    f"Signal #{sig_id} evaluated: {ticker} ({signal_type}) -> "
                    f"Entry: ${entry_price:,.2f} | Exit: ${current_price:,.2f} | "
                    f"PnL: {pnl_pct:+.2f}% ({outcome})"
                )

            except Exception as e:
                logger.warning(f"Could not forward-test signal #{sig_id} for {ticker}: {e}")

        return evaluated_results

    def get_accuracy_stats(self) -> Dict[str, Any]:
        """
        Computes overall strategy win rate %, average PnL %, and performance metrics.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM signals")
            total_signals = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as evaluated FROM signals WHERE status = 'evaluated'")
            evaluated_count = cursor.fetchone()["evaluated"]

            cursor.execute("SELECT COUNT(*) as wins FROM signals WHERE outcome = 'WIN'")
            wins = cursor.fetchone()["wins"]

            cursor.execute("SELECT COUNT(*) as losses FROM signals WHERE outcome = 'LOSS'")
            losses = cursor.fetchone()["losses"]

            cursor.execute("SELECT COUNT(*) as neutrals FROM signals WHERE outcome = 'NEUTRAL'")
            neutrals = cursor.fetchone()["neutrals"]

            cursor.execute("SELECT AVG(pnl_percent) as avg_pnl FROM signals WHERE status = 'evaluated'")
            avg_pnl_row = cursor.fetchone()["avg_pnl"]
            avg_pnl = float(avg_pnl_row) if avg_pnl_row is not None else 0.0

            cursor.execute("SELECT AVG(pnl_percent) as avg_win FROM signals WHERE outcome = 'WIN'")
            avg_win_row = cursor.fetchone()["avg_win"]
            avg_win = float(avg_win_row) if avg_win_row is not None else 0.0

            cursor.execute("SELECT AVG(pnl_percent) as avg_loss FROM signals WHERE outcome = 'LOSS'")
            avg_loss_row = cursor.fetchone()["avg_loss"]
            avg_loss = float(avg_loss_row) if avg_loss_row is not None else 0.0

            decisive_total = wins + losses
            win_rate = (wins / decisive_total * 100.0) if decisive_total > 0 else 0.0

            return {
                "total_signals": total_signals,
                "evaluated_count": evaluated_count,
                "pending_count": total_signals - evaluated_count,
                "wins": wins,
                "losses": losses,
                "neutrals": neutrals,
                "win_rate_percent": round(win_rate, 1),
                "avg_pnl_percent": round(avg_pnl, 2),
                "avg_win_percent": round(avg_win, 2),
                "avg_loss_percent": round(avg_loss, 2)
            }

    def get_evaluated_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves recent forward-tested evaluated signal records.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM signals WHERE status = 'evaluated' ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                d = dict(row)
                if d.get("indicators"):
                    try:
                        d["indicators"] = json.loads(d["indicators"])
                    except Exception:
                        pass
                results.append(d)
            return results
