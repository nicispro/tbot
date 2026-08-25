"""
Kill Switch & System Health Guard (KODA OS Phase 1)
Centralized circuit breaker managing SystemState (NORMAL, SAFE_MODE, HALTED).
Automatically triggers SAFE MODE on:
- >= 3 consecutive API errors
- Maximum portfolio drawdown breach
- Corrupted / anomalous market data detection
- Manual CLI / Telegram triggers (/kill, /resume)
"""

import json
import logging
import os
import datetime
from enum import Enum
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

STATE_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".kill_switch_state.json"
)


class SystemState(str, Enum):
    NORMAL = "NORMAL"
    SAFE_MODE = "SAFE_MODE"  # Only allows managing/closing existing positions, blocks new buys
    HALTED = "HALTED"        # Full system trading freeze


class KillSwitch:
    """
    Singleton system health guard and emergency circuit breaker.
    """
    _instance: Optional["KillSwitch"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(KillSwitch, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        max_consecutive_api_errors: int = 3,
        max_daily_drawdown_percent: float = 5.0,
        max_total_drawdown_percent: float = 10.0,
        state_file: str = STATE_FILE_PATH
    ):
        if getattr(self, "_initialized", False):
            return

        self.max_consecutive_api_errors = max_consecutive_api_errors
        self.max_daily_drawdown_percent = max_daily_drawdown_percent
        self.max_total_drawdown_percent = max_total_drawdown_percent
        self.state_file = state_file

        self.state = SystemState.NORMAL
        self.consecutive_api_errors = 0
        self.last_error_message = ""
        self.trigger_reason = ""
        self.triggered_at: Optional[datetime.datetime] = None
        self.peak_equity = 0.0
        self.day_start_equity = 0.0
        self.current_day = datetime.date.today()

        self._load_state()
        self._initialized = True

    def _save_state(self) -> None:
        """Persists current kill switch state to local disk."""
        try:
            data = {
                "state": self.state.value,
                "consecutive_api_errors": self.consecutive_api_errors,
                "trigger_reason": self.trigger_reason,
                "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
                "peak_equity": self.peak_equity,
                "day_start_equity": self.day_start_equity,
                "current_day": self.current_day.isoformat()
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist kill switch state: {e}")

    def _load_state(self) -> None:
        """Restores persisted kill switch state if present."""
        if not os.path.exists(self.state_file) or os.path.getsize(self.state_file) == 0:
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.state = SystemState(data.get("state", SystemState.NORMAL.value))
                self.consecutive_api_errors = int(data.get("consecutive_api_errors", 0))
                self.trigger_reason = data.get("trigger_reason", "")
                ts_str = data.get("triggered_at")
                self.triggered_at = datetime.datetime.fromisoformat(ts_str) if ts_str else None
                self.peak_equity = float(data.get("peak_equity", 0.0))
                self.day_start_equity = float(data.get("day_start_equity", 0.0))
        except Exception as e:
            logger.warning(f"Could not load kill switch state file: {e}")

    def record_api_success(self) -> None:
        """Resets the consecutive API error counter upon successful network/broker interaction."""
        if self.consecutive_api_errors > 0:
            logger.info(f"API connection healthy. Resetting error counter (was {self.consecutive_api_errors}).")
            self.consecutive_api_errors = 0
            self._save_state()

    def record_api_error(self, error_message: str) -> None:
        """
        Increments consecutive API error count and trips circuit breaker if threshold is reached.
        """
        self.consecutive_api_errors += 1
        self.last_error_message = error_message
        logger.warning(
            f"API Error recorded ({self.consecutive_api_errors}/{self.max_consecutive_api_errors}): {error_message}"
        )

        if self.consecutive_api_errors >= self.max_consecutive_api_errors and self.state == SystemState.NORMAL:
            self.engage_safe_mode(
                reason=f"Exceeded {self.max_consecutive_api_errors} consecutive API failures: {error_message}"
            )

    def record_anomaly(self, anomaly_description: str) -> None:
        """
        Trips SAFE MODE immediately upon detecting data corruption or anomalous price behavior.
        """
        logger.error(f"Market Data Anomaly detected: {anomaly_description}")
        if self.state == SystemState.NORMAL:
            self.engage_safe_mode(reason=f"Data Anomaly: {anomaly_description}")

    def update_portfolio_equity(self, current_total_equity: float) -> None:
        """
        Tracks peak equity and daily drawdown. Trips circuit breaker if thresholds are breached.
        """
        if current_total_equity <= 0.0:
            return

        today = datetime.date.today()
        if today != self.current_day:
            self.current_day = today
            self.day_start_equity = current_total_equity

        if self.day_start_equity <= 0.0:
            self.day_start_equity = current_total_equity

        if current_total_equity > self.peak_equity:
            self.peak_equity = current_total_equity

        # Check daily drawdown
        if self.day_start_equity > 0.0:
            daily_dd = ((self.day_start_equity - current_total_equity) / self.day_start_equity) * 100.0
            if daily_dd >= self.max_daily_drawdown_percent and self.state == SystemState.NORMAL:
                self.engage_safe_mode(
                    reason=f"Daily drawdown breach: {daily_dd:.2f}% (Limit: {self.max_daily_drawdown_percent}%)"
                )

        # Check total peak drawdown
        if self.peak_equity > 0.0:
            total_dd = ((self.peak_equity - current_total_equity) / self.peak_equity) * 100.0
            if total_dd >= self.max_total_drawdown_percent and self.state != SystemState.HALTED:
                self.trigger_kill(
                    reason=f"Total drawdown breach: {total_dd:.2f}% (Limit: {self.max_total_drawdown_percent}%)"
                )

        self._save_state()

    def engage_safe_mode(self, reason: str) -> None:
        """Transitions system to SAFE_MODE (blocks new purchases, allows sell/risk-reduction)."""
        self.state = SystemState.SAFE_MODE
        self.trigger_reason = reason
        self.triggered_at = datetime.datetime.now(datetime.timezone.utc)
        logger.critical(f"🚨 [KILL SWITCH] SAFE MODE ENGAGED: {reason}")
        self._save_state()

    def trigger_kill(self, reason: str) -> None:
        """Transitions system to HALTED (complete trading stop)."""
        self.state = SystemState.HALTED
        self.trigger_reason = reason
        self.triggered_at = datetime.datetime.now(datetime.timezone.utc)
        logger.critical(f"🛑 [KILL SWITCH] SYSTEM HALTED: {reason}")
        self._save_state()

    def reset(self) -> None:
        """Manually resets circuit breaker back to NORMAL state."""
        self.state = SystemState.NORMAL
        self.consecutive_api_errors = 0
        self.trigger_reason = ""
        self.triggered_at = None
        logger.info("✅ [KILL SWITCH] System successfully reset to NORMAL state.")
        self._save_state()

    def can_execute_orders(self, action: str = "BUY") -> Tuple[bool, str]:
        """
        Determines whether order execution is permitted under current health state.
        Returns (is_allowed, reason).
        """
        if self.state == SystemState.HALTED:
            return False, f"System is HALTED: {self.trigger_reason}"

        if self.state == SystemState.SAFE_MODE:
            if action.upper() == "BUY":
                return False, f"System in SAFE MODE (New buys blocked): {self.trigger_reason}"
            # SELL / Risk reduction is permitted in SAFE_MODE
            return True, "SAFE MODE active - Position liquidation/reduction permitted."

        return True, "System NORMAL - Execution permitted."

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive diagnostic health dictionary."""
        return {
            "state": self.state.value,
            "consecutive_api_errors": self.consecutive_api_errors,
            "trigger_reason": self.trigger_reason,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "peak_equity": self.peak_equity,
            "day_start_equity": self.day_start_equity
        }
