"""
Confidence Calibration Tracker (KODA Institutional Architecture - Block 4)
Tracks AI LLM confidence scores against actual empirical win rates across brackets
(60-70%, 70-80%, 80-90%, 90%+), identifying overconfidence or underconfidence bias.
"""

import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceBracketReport:
    """Statistical calibration metrics for a single confidence bracket."""
    bracket_name: str
    min_confidence: int
    max_confidence: int
    expected_midpoint: float
    total_signals: int
    wins: int
    losses: int
    actual_win_rate_pct: float
    calibration_error: float  # (expected_midpoint - actual_win_rate_pct)
    status: str  # 'CALIBRATED', 'OVERCONFIDENT', 'UNDERCONFIDENT', 'INSUFFICIENT_DATA'


class ConfidenceTracker:
    """
    Measures calibration accuracy of AI trade confidence predictions.
    """

    DB_FILE = "trading_outcomes.db"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self.DB_FILE
        self._init_db()

    def _init_db(self) -> None:
        """Initializes confidence calibration table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS confidence_predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        signal_id INTEGER,
                        ticker TEXT,
                        confidence_score INTEGER,
                        model_name TEXT,
                        outcome TEXT,
                        is_win INTEGER,
                        timestamp REAL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize confidence tracker DB: {e}")

    def record_prediction(
        self,
        signal_id: int,
        ticker: str,
        confidence_score: int,
        model_name: str = "llama-3.3-70b-versatile"
    ) -> None:
        """Records an AI signal confidence prediction."""
        conf = max(0, min(100, int(confidence_score)))
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO confidence_predictions (
                        signal_id, ticker, confidence_score, model_name, outcome, is_win, timestamp
                    ) VALUES (?, ?, ?, ?, 'PENDING', NULL, ?)
                """, (signal_id, ticker, conf, model_name, time.time()))
                conn.commit()
            logger.info(f"🎯 [CONFIDENCE TRACKER] Logged prediction for {ticker} (#{signal_id}): Confidence={conf}% [{model_name}]")
        except Exception as e:
            logger.error(f"Failed to record confidence prediction for {ticker}: {e}")

    def record_outcome(self, signal_id: int, is_win: bool) -> None:
        """Updates the actual outcome for a previously recorded signal confidence prediction."""
        outcome_str = "WIN" if is_win else "LOSS"
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE confidence_predictions
                    SET outcome = ?, is_win = ?
                    WHERE signal_id = ?
                """, (outcome_str, 1 if is_win else 0, signal_id))
                conn.commit()
            logger.info(f"🎯 [CONFIDENCE TRACKER] Updated outcome for signal #{signal_id}: {outcome_str}")
        except Exception as e:
            logger.error(f"Failed to update confidence outcome for signal #{signal_id}: {e}")

    def get_calibration_report(self) -> Dict[str, Any]:
        """
        Calculates empirical win rates and calibration error across confidence brackets.
        """
        brackets = [
            ("60-69%", 60, 69, 65.0),
            ("70-79%", 70, 79, 75.0),
            ("80-89%", 80, 89, 85.0),
            ("90-100%", 90, 100, 95.0),
        ]

        bracket_reports: List[ConfidenceBracketReport] = []
        total_eval = 0

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for b_name, b_min, b_max, b_mid in brackets:
                    cursor.execute("""
                        SELECT 
                            COUNT(*),
                            SUM(CASE WHEN is_win = 1 THEN 1 ELSE 0 END),
                            SUM(CASE WHEN is_win = 0 THEN 1 ELSE 0 END)
                        FROM confidence_predictions
                        WHERE confidence_score >= ? AND confidence_score <= ? AND is_win IS NOT NULL
                    """, (b_min, b_max))
                    row = cursor.fetchone()
                    count = row[0] or 0
                    wins = row[1] or 0
                    losses = row[2] or 0
                    total_eval += count

                    if count > 0:
                        win_rate = round((wins / count) * 100.0, 1)
                        cal_err = round(b_mid - win_rate, 1)

                        if cal_err > 15.0:
                            status = "OVERCONFIDENT"
                        elif cal_err < -15.0:
                            status = "UNDERCONFIDENT"
                        else:
                            status = "CALIBRATED"
                    else:
                        win_rate = 0.0
                        cal_err = 0.0
                        status = "INSUFFICIENT_DATA"

                    bracket_reports.append(ConfidenceBracketReport(
                        bracket_name=b_name,
                        min_confidence=b_min,
                        max_confidence=b_max,
                        expected_midpoint=b_mid,
                        total_signals=count,
                        wins=wins,
                        losses=losses,
                        actual_win_rate_pct=win_rate,
                        calibration_error=cal_err,
                        status=status
                    ))
        except Exception as e:
            logger.error(f"Failed to generate calibration report: {e}")

        return {
            "total_evaluated": total_eval,
            "brackets": bracket_reports,
            "is_calibrated": all(b.status in ("CALIBRATED", "INSUFFICIENT_DATA") for b in bracket_reports)
        }
