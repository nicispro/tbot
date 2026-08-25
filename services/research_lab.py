"""
KODA Research Lab & Hypothesis Engine (KODA Institutional Architecture - Block 5)
Provides a structured scientific pipeline for strategy modifications and AI hypotheses:
Hypothesis -> Backtest -> Walk-Forward -> Shadow Verification -> Production Approval.
Enforces a strict safety barrier: No unvalidated hypothesis can enter production without passing all stages.
"""

import datetime
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class HypothesisStage(str, Enum):
    PROPOSED = "PROPOSED"
    BACKTEST_PASSED = "BACKTEST_PASSED"
    WALK_FORWARD_PASSED = "WALK_FORWARD_PASSED"
    SHADOW_VERIFIED = "SHADOW_VERIFIED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class ResearchHypothesis:
    """Represents a strategy hypothesis moving through the scientific validation pipeline."""
    hypothesis_id: str
    target_market: str = "all"  # 'stock', 'crypto', 'all'
    title: str = ""
    description: str = ""
    archetype: str = "CUSTOM"
    parameters: Dict[str, Any] = field(default_factory=dict)
    stage: HypothesisStage = HypothesisStage.PROPOSED
    backtest_sharpe: float = 0.0
    backtest_profit_factor: float = 0.0
    walk_forward_efficiency: float = 0.0  # Out-of-sample / In-sample ratio (>= 0.65 required)
    shadow_trades_count: int = 0
    shadow_wins_count: int = 0
    shadow_win_rate_pct: float = 0.0
    approval_status: str = "PENDING"
    rejection_reason: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.title:
            self.title = self.archetype if self.archetype != "CUSTOM" else self.hypothesis_id


class ResearchLabEngine:
    """
    Gatekeeper and evaluation engine for research hypotheses.
    Enforces minimum thresholds at each validation stage before granting production authorization.
    """

    DB_FILE = "trading_outcomes.db"

    # Validation criteria thresholds
    MIN_BACKTEST_SHARPE = 1.40
    MIN_BACKTEST_PROFIT_FACTOR = 1.35
    MIN_WALK_FORWARD_EFFICIENCY = 0.65
    MIN_SHADOW_TRADES = 5
    MIN_SHADOW_WIN_RATE = 55.0

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self.DB_FILE
        self._init_db()

    def _init_db(self) -> None:
        """Initializes research hypotheses table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS research_hypotheses (
                        hypothesis_id TEXT PRIMARY KEY,
                        title TEXT,
                        description TEXT,
                        target_market TEXT,
                        archetype TEXT,
                        parameters TEXT,
                        stage TEXT,
                        backtest_sharpe REAL,
                        backtest_profit_factor REAL,
                        walk_forward_efficiency REAL,
                        shadow_trades_count INTEGER,
                        shadow_wins_count INTEGER,
                        shadow_win_rate_pct REAL,
                        approval_status TEXT,
                        rejection_reason TEXT,
                        created_at REAL,
                        updated_at REAL
                    )
                """)
                # Auto-migrate existing tables if columns are missing
                cursor.execute("PRAGMA table_info(research_hypotheses)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                if "archetype" not in existing_cols:
                    cursor.execute("ALTER TABLE research_hypotheses ADD COLUMN archetype TEXT DEFAULT 'CUSTOM'")
                if "parameters" not in existing_cols:
                    cursor.execute("ALTER TABLE research_hypotheses ADD COLUMN parameters TEXT DEFAULT '{}'")
                if "shadow_wins_count" not in existing_cols:
                    cursor.execute("ALTER TABLE research_hypotheses ADD COLUMN shadow_wins_count INTEGER DEFAULT 0")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize research lab DB: {e}")

    def create_hypothesis(
        self,
        hypothesis_id: str,
        title: str = "",
        description: str = "",
        target_market: str = "all",
        archetype: str = "CUSTOM",
        parameters: Optional[Dict[str, Any]] = None
    ) -> ResearchHypothesis:
        """Registers a newly proposed strategy hypothesis."""
        hyp = ResearchHypothesis(
            hypothesis_id=hypothesis_id,
            title=title or archetype or hypothesis_id,
            description=description,
            target_market=target_market.lower(),
            archetype=archetype,
            parameters=parameters or {}
        )
        return self.register_hypothesis(hyp)

    def register_hypothesis(self, hypothesis: ResearchHypothesis) -> ResearchHypothesis:
        """Registers or persists an existing hypothesis object into the Research Lab DB."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO research_hypotheses (
                        hypothesis_id, title, description, target_market, archetype, parameters,
                        stage, backtest_sharpe, backtest_profit_factor, walk_forward_efficiency,
                        shadow_trades_count, shadow_wins_count, shadow_win_rate_pct,
                        approval_status, rejection_reason, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    hypothesis.hypothesis_id, hypothesis.title, hypothesis.description,
                    hypothesis.target_market, hypothesis.archetype, json.dumps(hypothesis.parameters),
                    hypothesis.stage.value, hypothesis.backtest_sharpe, hypothesis.backtest_profit_factor,
                    hypothesis.walk_forward_efficiency, hypothesis.shadow_trades_count,
                    hypothesis.shadow_wins_count, hypothesis.shadow_win_rate_pct,
                    hypothesis.approval_status, hypothesis.rejection_reason,
                    hypothesis.created_at, hypothesis.updated_at
                ))
                conn.commit()
            logger.info(f"🧪 [RESEARCH LAB] Registered hypothesis '{hypothesis.hypothesis_id}': {hypothesis.title or hypothesis.description}")
        except Exception as e:
            logger.error(f"Failed to register hypothesis {hypothesis.hypothesis_id}: {e}")

        return hypothesis

    def evaluate_backtest(
        self,
        hypothesis_id: str,
        sharpe_ratio: float,
        profit_factor: float,
        win_rate: Optional[float] = None,
        max_drawdown: Optional[float] = None
    ) -> Tuple[bool, ResearchHypothesis, str]:
        """Evaluates Stage 1 Backtest performance metrics against gatekeeper standards."""
        return self.advance_stage(
            hypothesis_id=hypothesis_id,
            backtest_sharpe=sharpe_ratio,
            backtest_profit_factor=profit_factor
        )

    def evaluate_walk_forward(
        self,
        hypothesis_id: str,
        walk_forward_efficiency: float
    ) -> Tuple[bool, ResearchHypothesis, str]:
        """Evaluates Stage 2 Walk-Forward Efficiency (OOS/IS) against overfitting thresholds."""
        return self.advance_stage(
            hypothesis_id=hypothesis_id,
            walk_forward_efficiency=walk_forward_efficiency
        )

    def record_shadow_trade(
        self,
        hypothesis_id: str,
        was_profitable: bool
    ) -> Tuple[bool, ResearchHypothesis, str]:
        """Records an execution result in Stage 3 Shadow Trading and evaluates approval status."""
        hyp = self.get_hypothesis(hypothesis_id)
        if not hyp:
            return False, ResearchHypothesis(hypothesis_id=hypothesis_id), "Hypothesis not found."

        hyp.shadow_trades_count += 1
        if was_profitable:
            hyp.shadow_wins_count += 1

        hyp.shadow_win_rate_pct = round((hyp.shadow_wins_count / hyp.shadow_trades_count) * 100.0, 1)
        self._update_db(hyp)

        # Check if enough trades accumulated to graduate to APPROVED
        return self.advance_stage(
            hypothesis_id=hypothesis_id,
            shadow_trades_count=hyp.shadow_trades_count,
            shadow_win_rate_pct=hyp.shadow_win_rate_pct
        )

    def advance_stage(
        self,
        hypothesis_id: str,
        backtest_sharpe: Optional[float] = None,
        backtest_profit_factor: Optional[float] = None,
        walk_forward_efficiency: Optional[float] = None,
        shadow_trades_count: Optional[int] = None,
        shadow_win_rate_pct: Optional[float] = None
    ) -> Tuple[bool, ResearchHypothesis, str]:
        """
        Validates performance metrics against stage criteria and advances hypothesis.
        """
        hyp = self.get_hypothesis(hypothesis_id)
        if not hyp:
            return False, ResearchHypothesis(hypothesis_id=hypothesis_id, title="", description="", target_market=""), "Hypothesis not found."

        msg = f"Stage remains {hyp.stage.value}."

        # Stage 1 -> 2: Backtest Gate
        if hyp.stage == HypothesisStage.PROPOSED:
            sharpe = backtest_sharpe if backtest_sharpe is not None else hyp.backtest_sharpe
            pf = backtest_profit_factor if backtest_profit_factor is not None else hyp.backtest_profit_factor
            hyp.backtest_sharpe = sharpe
            hyp.backtest_profit_factor = pf

            if sharpe >= self.MIN_BACKTEST_SHARPE and pf >= self.MIN_BACKTEST_PROFIT_FACTOR:
                hyp.stage = HypothesisStage.BACKTEST_PASSED
                msg = f"Passed Backtest (Sharpe: {sharpe:.2f} >= {self.MIN_BACKTEST_SHARPE}, PF: {pf:.2f} >= {self.MIN_BACKTEST_PROFIT_FACTOR})."
            else:
                hyp.stage = HypothesisStage.REJECTED
                hyp.rejection_reason = f"Backtest failed: Sharpe {sharpe:.2f} < {self.MIN_BACKTEST_SHARPE} or PF {pf:.2f} < {self.MIN_BACKTEST_PROFIT_FACTOR}."
                msg = hyp.rejection_reason

        # Stage 2 -> 3: Walk-Forward Gate
        elif hyp.stage == HypothesisStage.BACKTEST_PASSED:
            wfe = walk_forward_efficiency if walk_forward_efficiency is not None else hyp.walk_forward_efficiency
            hyp.walk_forward_efficiency = wfe

            if wfe >= self.MIN_WALK_FORWARD_EFFICIENCY:
                hyp.stage = HypothesisStage.WALK_FORWARD_PASSED
                msg = f"Passed Walk-Forward (WFE: {wfe:.2f} >= {self.MIN_WALK_FORWARD_EFFICIENCY})."
            else:
                hyp.stage = HypothesisStage.REJECTED
                hyp.rejection_reason = f"Overfitting detected: Walk-forward efficiency {wfe:.2f} < {self.MIN_WALK_FORWARD_EFFICIENCY}."
                msg = hyp.rejection_reason

        # Stage 3 -> 4 & 5: Shadow Verification & Approval Gate
        elif hyp.stage in (HypothesisStage.WALK_FORWARD_PASSED, HypothesisStage.SHADOW_VERIFIED, HypothesisStage.APPROVED):
            trades = shadow_trades_count if shadow_trades_count is not None else hyp.shadow_trades_count
            win_rate = shadow_win_rate_pct if shadow_win_rate_pct is not None else hyp.shadow_win_rate_pct
            hyp.shadow_trades_count = trades
            hyp.shadow_win_rate_pct = win_rate

            if trades >= self.MIN_SHADOW_TRADES and win_rate >= self.MIN_SHADOW_WIN_RATE:
                hyp.stage = HypothesisStage.APPROVED
                hyp.approval_status = "APPROVED_FOR_PRODUCTION"
                msg = f"Passed Shadow Trading ({trades} trades, {win_rate:.1f}% Win Rate). APPROVED FOR PRODUCTION."
            elif trades >= self.MIN_SHADOW_TRADES:
                hyp.stage = HypothesisStage.REJECTED
                hyp.rejection_reason = f"Shadow trading underperformed: Win Rate {win_rate:.1f}% < {self.MIN_SHADOW_WIN_RATE}%."
                msg = hyp.rejection_reason
            else:
                hyp.stage = HypothesisStage.SHADOW_VERIFIED
                msg = f"In Shadow Trading Sandbox ({trades}/{self.MIN_SHADOW_TRADES} trades completed)."

        hyp.updated_at = time.time()
        self._update_db(hyp)
        return (hyp.stage in (HypothesisStage.BACKTEST_PASSED, HypothesisStage.WALK_FORWARD_PASSED, HypothesisStage.SHADOW_VERIFIED, HypothesisStage.APPROVED)), hyp, msg

    def _update_db(self, hyp: ResearchHypothesis) -> None:
        """Updates hypothesis record in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE research_hypotheses
                    SET stage = ?, backtest_sharpe = ?, backtest_profit_factor = ?,
                        walk_forward_efficiency = ?, shadow_trades_count = ?,
                        shadow_wins_count = ?, shadow_win_rate_pct = ?,
                        approval_status = ?, rejection_reason = ?, updated_at = ?
                    WHERE hypothesis_id = ?
                """, (
                    hyp.stage.value, hyp.backtest_sharpe, hyp.backtest_profit_factor,
                    hyp.walk_forward_efficiency, hyp.shadow_trades_count,
                    hyp.shadow_wins_count, hyp.shadow_win_rate_pct,
                    hyp.approval_status, hyp.rejection_reason, hyp.updated_at,
                    hyp.hypothesis_id
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update hypothesis {hyp.hypothesis_id}: {e}")

    def get_hypothesis(self, hypothesis_id: str) -> Optional[ResearchHypothesis]:
        """Retrieves a single hypothesis by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        hypothesis_id, title, description, target_market, archetype, parameters,
                        stage, backtest_sharpe, backtest_profit_factor, walk_forward_efficiency,
                        shadow_trades_count, shadow_wins_count, shadow_win_rate_pct,
                        approval_status, rejection_reason, created_at, updated_at
                    FROM research_hypotheses
                    WHERE hypothesis_id = ?
                """, (hypothesis_id,))
                row = cursor.fetchone()
                if row:
                    params = {}
                    try:
                        params = json.loads(row[5]) if row[5] else {}
                    except Exception:
                        pass

                    return ResearchHypothesis(
                        hypothesis_id=row[0],
                        title=row[1] or row[0],
                        description=row[2] or "",
                        target_market=row[3] or "all",
                        archetype=row[4] or "CUSTOM",
                        parameters=params,
                        stage=HypothesisStage(row[6]),
                        backtest_sharpe=row[7],
                        backtest_profit_factor=row[8],
                        walk_forward_efficiency=row[9],
                        shadow_trades_count=row[10],
                        shadow_wins_count=row[11] if len(row) > 11 else 0,
                        shadow_win_rate_pct=row[12],
                        approval_status=row[13],
                        rejection_reason=row[14],
                        created_at=row[15],
                        updated_at=row[16]
                    )
        except Exception as e:
            logger.error(f"Failed to get hypothesis {hypothesis_id}: {e}")

        return None

    def list_all_hypotheses(self) -> List[ResearchHypothesis]:
        """Lists all registered hypotheses across all stages."""
        results: List[ResearchHypothesis] = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        hypothesis_id, title, description, target_market, archetype, parameters,
                        stage, backtest_sharpe, backtest_profit_factor, walk_forward_efficiency,
                        shadow_trades_count, shadow_wins_count, shadow_win_rate_pct,
                        approval_status, rejection_reason, created_at, updated_at
                    FROM research_hypotheses
                    ORDER BY updated_at DESC
                """)
                for row in cursor.fetchall():
                    params = {}
                    try:
                        params = json.loads(row[5]) if row[5] else {}
                    except Exception:
                        pass

                    results.append(ResearchHypothesis(
                        hypothesis_id=row[0],
                        title=row[1] or row[0],
                        description=row[2] or "",
                        target_market=row[3] or "all",
                        archetype=row[4] or "CUSTOM",
                        parameters=params,
                        stage=HypothesisStage(row[6]),
                        backtest_sharpe=row[7],
                        backtest_profit_factor=row[8],
                        walk_forward_efficiency=row[9],
                        shadow_trades_count=row[10],
                        shadow_wins_count=row[11],
                        shadow_win_rate_pct=row[12],
                        approval_status=row[13],
                        rejection_reason=row[14],
                        created_at=row[15],
                        updated_at=row[16]
                    ))
        except Exception as e:
            logger.error(f"Failed to list hypotheses: {e}")

        return results


# Alias for institutional naming
KODAResearchLab = ResearchLabEngine
