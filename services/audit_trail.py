"""
Decision Audit Trail Engine (KODA Institutional Architecture - Block 3)
Provides verifiable, end-to-end trace logging for every trade candidate:
[Asset -> Regime -> Quant Score -> Macro Context -> Groq Decision -> Risk Approval -> Exposure Approval -> Execution Result].
Persists decision trees to local database for post-trade compliance and diagnostics.
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class DecisionAuditRecord:
    """End-to-end decision lifecycle trace for a candidate trade."""
    ticker: str
    market_type: str
    regime: str
    quant_score: float
    macro_sentiment: str
    ai_sentiment: str
    ai_confidence: int
    risk_approved: bool
    exposure_approved: bool
    execution_status: str  # 'EXECUTED', 'VETOED_RISK', 'VETOED_EXPOSURE', 'VETOED_AI', 'SIMULATED'
    rejection_reason: Optional[str] = None
    trace_details: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    timestamp: float = field(default_factory=time.time)


class DecisionAuditTrail:
    """
    Manages institutional decision trace recording and historical audit retrieval.
    """

    DB_FILE = "trading_outcomes.db"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self.DB_FILE
        self._init_db()

    def _init_db(self) -> None:
        """Initializes decision audit trail table in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS decision_audit_trail (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticker TEXT,
                        market_type TEXT,
                        regime TEXT,
                        quant_score REAL,
                        macro_sentiment TEXT,
                        ai_sentiment TEXT,
                        ai_confidence INTEGER,
                        risk_approved INTEGER,
                        exposure_approved INTEGER,
                        execution_status TEXT,
                        rejection_reason TEXT,
                        trace_details_json TEXT,
                        timestamp REAL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize decision audit trail DB: {e}")

    def log_decision_chain(
        self,
        ticker: str,
        market_type: str,
        regime: str,
        quant_score: float,
        macro_sentiment: str,
        ai_sentiment: str,
        ai_confidence: int,
        risk_approved: bool,
        exposure_approved: bool,
        execution_status: str,
        rejection_reason: Optional[str] = None,
        trace_details: Optional[Dict[str, Any]] = None
    ) -> DecisionAuditRecord:
        """
        Records a complete multi-stage decision trace to database.
        """
        ts = time.time()
        details = trace_details or {}
        details_json = json.dumps(details, default=str)

        rec = DecisionAuditRecord(
            ticker=ticker,
            market_type=market_type.lower(),
            regime=regime,
            quant_score=round(quant_score, 1),
            macro_sentiment=macro_sentiment,
            ai_sentiment=ai_sentiment,
            ai_confidence=ai_confidence,
            risk_approved=risk_approved,
            exposure_approved=exposure_approved,
            execution_status=execution_status,
            rejection_reason=rejection_reason,
            trace_details=details,
            timestamp=ts
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO decision_audit_trail (
                        ticker, market_type, regime, quant_score, macro_sentiment,
                        ai_sentiment, ai_confidence, risk_approved, exposure_approved,
                        execution_status, rejection_reason, trace_details_json, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rec.ticker, rec.market_type, rec.regime, rec.quant_score,
                    rec.macro_sentiment, rec.ai_sentiment, rec.ai_confidence,
                    1 if rec.risk_approved else 0, 1 if rec.exposure_approved else 0,
                    rec.execution_status, rec.rejection_reason, details_json, rec.timestamp
                ))
                rec.id = cursor.lastrowid
                conn.commit()
            logger.info(
                f"📋 [AUDIT TRAIL] Logged decision for {ticker}: Status={execution_status} | "
                f"Regime={regime} | Quant={quant_score:.0f} | AI={ai_sentiment}({ai_confidence}%)"
            )
        except Exception as e:
            logger.error(f"Failed to record decision audit for {ticker}: {e}")

        return rec

    def get_recent_traces(self, limit: int = 15) -> List[DecisionAuditRecord]:
        """Retrieves recent decision audit records from database."""
        records: List[DecisionAuditRecord] = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        id, ticker, market_type, regime, quant_score,
                        macro_sentiment, ai_sentiment, ai_confidence,
                        risk_approved, exposure_approved, execution_status,
                        rejection_reason, trace_details_json, timestamp
                    FROM decision_audit_trail
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                for r in rows:
                    details = {}
                    if r[12]:
                        try:
                            details = json.loads(r[12])
                        except Exception:
                            pass
                    records.append(DecisionAuditRecord(
                        id=r[0],
                        ticker=r[1],
                        market_type=r[2],
                        regime=r[3],
                        quant_score=r[4],
                        macro_sentiment=r[5],
                        ai_sentiment=r[6],
                        ai_confidence=r[7],
                        risk_approved=bool(r[8]),
                        exposure_approved=bool(r[9]),
                        execution_status=r[10],
                        rejection_reason=r[11],
                        trace_details=details,
                        timestamp=r[13]
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch decision audit traces: {e}")

        return records
