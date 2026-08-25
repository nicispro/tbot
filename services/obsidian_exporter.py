"""
Obsidian Direct Vault Exporter (KODA Institutional Architecture)
Provides headless, filesystem-based Obsidian note generation with Dataview-compatible
YAML frontmatter, Dataview tags, and callouts for Trades, Autopsies, Daily Briefs, and Research Lab.
Works standalone on VPS servers (/opt/koda_bot/obsidian_vault) or local workstations.
"""

import os
import subprocess
import datetime
import logging
from typing import Optional, Dict, Any, List
from dataclasses import asdict

from services.obsidian import TradeLogRecord
from services.ai_analyzer import AIAnalysisResult
from services.execution_quality import ExecutionMetrics

logger = logging.getLogger(__name__)


class ObsidianVaultExporter:
    """
    Directly generates structured Markdown notes with YAML frontmatter
    in an Obsidian Vault directory structure and automatically synchronizes with Git.
    """

    DEFAULT_VAULT_PATH = "/opt/koda_bot/obsidian_vault" if os.path.exists("/opt/koda_bot/obsidian_vault") or os.path.exists("/opt/koda_bot") else "./obsidian_vault"

    def __init__(self, vault_path: Optional[str] = None, auto_git_sync: bool = True):
        # 1. Resolve path prioritizing explicit param, env vars, or default Linux VPS path /opt/koda_bot/obsidian_vault
        raw_path = (
            vault_path
            or os.getenv("OBSIDIAN_VAULT_PATH")
            or os.getenv("OBSIDIAN_VAULT_FOLDER")
            or self.DEFAULT_VAULT_PATH
        )
        # Normalize legacy default folder name if on VPS
        if raw_path in ("Trading-Logs", "/opt/koda_bot/Trading-Logs", "obsidian_vault", "./obsidian_vault") and (os.path.exists("/opt/koda_bot/obsidian_vault") or os.path.exists("/opt/koda_bot")):
            raw_path = "/opt/koda_bot/obsidian_vault"

        self.vault_path = os.path.abspath(raw_path)
        self.auto_git_sync = auto_git_sync
        self._ensure_folders()

    def _ensure_folders(self) -> None:
        """Ensures standard vault subdirectories exist."""
        for folder_name in ("Trades", "Briefs", "Autopsies", "Research"):
            folder_dir = os.path.join(self.vault_path, folder_name)
            os.makedirs(folder_dir, exist_ok=True)

    def get_vault_status(self) -> Dict[str, Any]:
        """
        Queries the current health, file counts, and Git remote synchronization status
        of the Obsidian vault at /opt/koda_bot/obsidian_vault or local path.
        """
        exists = os.path.exists(self.vault_path)
        counts = {"trades": 0, "autopsies": 0, "briefs": 0, "research": 0}
        total_notes = 0

        if exists:
            for cat in ("Trades", "Autopsies", "Briefs", "Research"):
                cat_dir = os.path.join(self.vault_path, cat)
                if os.path.exists(cat_dir):
                    try:
                        c = len([f for f in os.listdir(cat_dir) if f.endswith(".md")])
                        counts[cat.lower()] = c
                        total_notes += c
                    except Exception:
                        pass

        # Check Git repository status
        git_initialized = False
        git_remote = "Nav piesaistīts"
        git_branch = "N/A"

        try:
            check_git = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=3
            )
            if check_git.returncode == 0:
                git_initialized = True
                remote_proc = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=self.vault_path,
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if remote_proc.returncode == 0 and remote_proc.stdout.strip():
                    git_remote = remote_proc.stdout.strip()

                branch_proc = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=self.vault_path,
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if branch_proc.returncode == 0 and branch_proc.stdout.strip():
                    git_branch = branch_proc.stdout.strip()
        except Exception as e:
            logger.debug(f"Git status query notice: {e}")

        return {
            "vault_path": self.vault_path,
            "exists": exists,
            "total_notes": total_notes,
            "counts": counts,
            "git_initialized": git_initialized,
            "git_remote": git_remote,
            "git_branch": git_branch,
            "auto_git_sync": self.auto_git_sync,
        }

    def get_status_summary(self) -> str:
        """Returns human-readable text status for AI prompt and user diagnostics."""
        st = self.get_vault_status()
        git_state = "Aktīvs un sinhronizēts" if (st["git_initialized"] and ("http" in st["git_remote"] or "git@" in st["git_remote"] or "github.com" in st["git_remote"])) else ("Inicializēts lokāli" if st["git_initialized"] else "Nav inicializēts")
        remote_info = st["git_remote"] if st["git_initialized"] else "Nav"
        return (
            f"Obsidian Vault: {st['vault_path']} | Statuss: Aktīvs | Kopā piezīmes: {st['total_notes']} "
            f"(Darījumi: {st['counts']['trades']}, Autopsijas: {st['counts']['autopsies']}, "
            f"Briefs: {st['counts']['briefs']}, Research: {st['counts']['research']}) | "
            f"Git: {git_state} (Remote: {remote_info}, Branch: {st['git_branch']}, Auto-sync: {st['auto_git_sync']})"
        )

    def _git_sync(self, commit_message: str = "Auto-sync: update trade notes and autopsies") -> bool:
        """
        Lightweight Git automation to stage, commit, and push updated vault Markdown notes.
        Non-interactive execution with 45s timeout limit. Gracefully catches edge cases
        (no changes, missing git repo, network/auth errors) without blocking trading operations.
        """
        if not self.auto_git_sync:
            return False

        # Disable interactive terminal prompts to prevent hanging on auth requests
        git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": ""}

        try:
            # 1. Check if git repo exists in vault path
            git_dir = os.path.join(self.vault_path, ".git")
            if not os.path.exists(git_dir):
                check_git = subprocess.run(
                    ["git", "rev-parse", "--is-inside-work-tree"],
                    cwd=self.vault_path,
                    env=git_env,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if check_git.returncode != 0:
                    logger.debug(f"Obsidian vault at '{self.vault_path}' is not a Git repository. Skipping auto-sync.")
                    return False

            # 2. Stage all changed/new markdown files
            add_proc = subprocess.run(
                ["git", "add", "."],
                cwd=self.vault_path,
                env=git_env,
                capture_output=True,
                text=True,
                timeout=15
            )
            if add_proc.returncode != 0:
                logger.warning(f"Git add failed in obsidian vault: {add_proc.stderr}")
                return False

            # 3. Check if there are changes to commit
            status_proc = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.vault_path,
                env=git_env,
                capture_output=True,
                text=True,
                timeout=5
            )
            if not status_proc.stdout.strip():
                logger.debug("No changes to commit in Obsidian vault Git repo.")
                return True

            # 4. Commit changes
            commit_proc = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.vault_path,
                env=git_env,
                capture_output=True,
                text=True,
                timeout=15
            )
            if commit_proc.returncode != 0:
                logger.warning(f"Git commit failed in obsidian vault: {commit_proc.stderr}")
                return False

            # 5. Detect branch and push to origin (with 45-second network timeout)
            branch_proc = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.vault_path,
                env=git_env,
                capture_output=True,
                text=True,
                timeout=5
            )
            branch = branch_proc.stdout.strip() or "main"

            push_proc = subprocess.run(
                ["git", "push", "origin", branch],
                cwd=self.vault_path,
                env=git_env,
                capture_output=True,
                text=True,
                timeout=45
            )
            if push_proc.returncode == 0:
                logger.info(f"Obsidian vault synced to Git remote origin/{branch}.")
                return True
            else:
                err_msg = push_proc.stderr.strip()[:150]
                logger.warning(f"Git push notice (remote/auth): {err_msg}")
                return False

        except subprocess.TimeoutExpired:
            logger.warning("Git auto-sync timed out after 45 seconds. Continuing trading bot operations.")
            return False
        except Exception as e:
            logger.warning(f"Obsidian Git auto-sync notice ({e}). Continuing trading bot operations.")
            return False

    def export_trade(
        self,
        record: TradeLogRecord,
        ai_analysis: Optional[AIAnalysisResult] = None,
        metrics: Optional[ExecutionMetrics] = None,
        risk_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Exports a detailed, Dataview-compatible Trade Note into the Trades/ folder.
        """
        date_str = record.timestamp.strftime("%Y-%m-%d")
        time_str = record.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        clean_ticker = record.ticker.replace("/", "_").replace(":", "_")
        action = record.action.upper()
        clean_name = clean_ticker.split("_")[0].lower()

        filename = f"{date_str}_{clean_ticker}_{action}.md"
        filepath = os.path.join(self.vault_path, "Trades", filename)

        status_str = "SUCCESS" if record.execution_success else "FAILED"
        ai_sentiment = ai_analysis.sentiment if ai_analysis else "N/A"
        ai_conf = ai_analysis.confidence_score if ai_analysis else 0
        ai_summary = ai_analysis.summary if ai_analysis else "No AI thesis provided."
        ai_catalysts = ai_analysis.catalysts if ai_analysis else "None"

        slippage_bps = metrics.slippage_bps if metrics else 0.0
        fee_usd = metrics.fee_usd if metrics else 0.0
        latency_ms = metrics.execution_latency_ms if metrics else 0.0

        content = f"""---
type: trade
date: {date_str}
timestamp: "{time_str}"
ticker: "{record.ticker}"
action: "{action}"
price: {record.price:.4f}
quantity: {record.quantity:.4f}
order_value: {record.order_value:.2f}
status: "{status_str}"
environment: "{record.environment}"
order_id: "{record.order_id or 'N/A'}"
slippage_bps: {slippage_bps:.1f}
fee_usd: {fee_usd:.2f}
ai_sentiment: "{ai_sentiment}"
ai_confidence: {ai_conf}
tags:
  - trade
  - {action.lower()}
  - {clean_name}
  - {status_str.lower()}
---

# ⚡ Trade Execution: `{record.ticker}` ({action})

> [!summary] **Order Execution Summary**
> - **Date & Time:** `{time_str}`
> - **Ticker:** `{record.ticker}`
> - **Action:** `{action}` @ `${record.price:,.2f}`
> - **Quantity:** `{record.quantity:.4f}` shares/units
> - **Total Value:** `${record.order_value:,.2f}`
> - **Status:** `{status_str}` (`{record.broker_status}`)
> - **Environment:** `{record.environment.upper()}`

---

## 🎯 Strategy & Technical Context
{record.strategy_reason}

---

## 🤖 Groq AI Analysis & Reasoning
> [!info] **AI Thesis ({ai_sentiment} - {ai_conf}% Confidence)**
> {ai_summary}
> 
> **Key Catalysts:** *{ai_catalysts}*

---

## ⚡ Execution Quality & Broker Latency
- **Expected Fill Price:** `${(metrics.expected_price if metrics else record.price):,.2f}`
- **Actual Fill Price:** `${record.price:,.2f}`
- **Execution Slippage:** `{slippage_bps:+.1f} bps`
- **Exchange/Broker Fee:** `${fee_usd:,.2f}`
- **Execution Latency:** `{latency_ms:.1f} ms`
"""
        if record.error_message:
            content += f"""
---

## ⚠️ Execution Errors
> [!danger] **Error Details**
> `{record.error_message}`
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")

        logger.info(f"Obsidian trade note exported: '{filepath}'")
        self._git_sync(commit_message=f"Auto-sync: log trade {record.ticker} ({action})")
        return filepath

    def export_autopsy(self, report: Any) -> str:
        """
        Exports a Trade Autopsy 2.0 retrospective note with Annie Duke 4-quadrant evaluation
        and counterfactual what-if analysis into the Autopsies/ folder.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        ticker = getattr(report, "ticker", "UNKNOWN")
        clean_ticker = ticker.replace("/", "_").replace(":", "_")
        clean_name = clean_ticker.split("_")[0].lower()
        quadrant = getattr(report, "decision_outcome_quadrant", "GOOD_DECISION_WIN")
        process_score = getattr(report, "process_quality_score", 75.0)
        pnl_pct = getattr(report, "pnl_percent", 0.0)
        outcome = getattr(report, "outcome", "WIN")
        lesson = getattr(report, "actionable_lesson", "Follow disciplined risk framework.")
        wider_sl = getattr(report, "counterfactual_wider_sl_result", "N/A")
        delayed_entry = getattr(report, "counterfactual_delayed_entry_result", "N/A")

        filename = f"{date_str}_{clean_ticker}_Autopsy.md"
        filepath = os.path.join(self.vault_path, "Autopsies", filename)

        content = f"""---
type: autopsy
date: {date_str}
timestamp: "{time_str}"
ticker: "{ticker}"
outcome: "{outcome}"
quadrant: "{quadrant}"
process_quality_score: {process_score:.1f}
pnl_percent: {pnl_pct:.2f}
tags:
  - autopsy
  - {outcome.lower()}
  - {clean_name}
  - {quadrant.lower()}
---

# 🔬 Trade Autopsy 2.0: `{ticker}`

> [!abstract] **Decision Quality vs Outcome Matrix (Annie Duke)**
> - **Ticker:** `{ticker}`
> - **Realized Outcome:** `{outcome}` (`{pnl_pct:+.2f}%`)
> - **Process Quality Score:** `{process_score:.0f}/100`
> - **Quadrant Classification:** `{quadrant}`

---

## 💡 Actionable Retrospective Lesson
> [!tip] **Key Rule Learned**
> *"{lesson}"*

---

## 🔮 Counterfactual What-If Simulation
- **Alternative 1 (Wider Stop Loss +0.5 ATR):**
  *{wider_sl}*
- **Alternative 2 (Delayed Entry for Confirmation):**
  *{delayed_entry}*
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")

        logger.info(f"Obsidian autopsy note exported: '{filepath}'")
        self._git_sync(commit_message=f"Auto-sync: log autopsy {ticker}")
        return filepath

    def export_daily_brief(
        self,
        brief_type: str,
        date_str: Optional[str] = None,
        macro_sentiment: str = "NEUTRAL",
        stock_cash: Optional[Any] = None,
        crypto_cash: Optional[Any] = None,
        top_radar_setups: Optional[List[Dict[str, Any]]] = None,
        lessons: Optional[List[str]] = None,
        stats: Optional[Dict[str, Any]] = None,
        notes: str = ""
    ) -> str:
        """
        Exports Morning or End-of-Day Intelligence Briefs into the Briefs/ folder.
        """
        d_str = date_str or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        b_type = brief_type.capitalize()
        filename = f"{d_str}_{b_type}_Brief.md"
        filepath = os.path.join(self.vault_path, "Briefs", filename)

        stock_total = stock_cash.total if stock_cash else 0.0
        stock_free = stock_cash.free if stock_cash else 0.0
        crypto_total = crypto_cash.total if crypto_cash else 0.0
        crypto_free = crypto_cash.free if crypto_cash else 0.0

        content = f"""---
type: brief
brief_type: "{brief_type.lower()}"
date: {d_str}
macro_sentiment: "{macro_sentiment}"
stock_total_value: {stock_total:.2f}
crypto_total_value: {crypto_total:.2f}
tags:
  - brief
  - {brief_type.lower()}
---

# 🌅 KODA {b_type} Intelligence Brief (`{d_str}`)

> [!info] **Macro Market Environment**
> - **Macro Regime:** `{macro_sentiment}`
> - **Stocks Portfolio Total:** `${stock_total:,.2f}` (Free: `${stock_free:,.2f}`)
> - **Crypto Portfolio Total:** `{crypto_total:,.2f} USDT` (Free: `{crypto_free:,.2f} USDT`)

---

## 📡 Top Radar Opportunities & Tactical Focus
"""
        if top_radar_setups:
            for s in top_radar_setups:
                t = s.get("ticker", "")
                sc = s.get("composite_score", 0.0)
                g = s.get("grade", "B")
                p = s.get("price", 0.0)
                evts = "; ".join(s.get("key_events", [])[:2]) if s.get("key_events") else "Trend Alignment"
                content += f"- **[{g}] `{t}`** @ `${p:,.2f}` | Score: `{sc:.0f}/100` | *{evts}*\n"
        else:
            content += "- *No top watchlist setups triggered this cycle.*\n"

        if lessons:
            content += "\n---\n\n## 💡 Key Lessons & Retrospective Insights\n"
            for les in lessons[:3]:
                content += f"- *{les}*\n"

        if notes:
            content += f"\n---\n\n## 🎯 Tactical Gameplan\n*{notes}*\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")

        logger.info(f"Obsidian brief exported: '{filepath}'")
        self._git_sync(commit_message=f"Auto-sync: log {brief_type} brief {d_str}")
        return filepath

    def export_hypothesis(self, hypothesis: Any) -> str:
        """
        Exports a KODA Research Lab hypothesis note into the Research/ folder.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        hyp_id = getattr(hypothesis, "hypothesis_id", "HYP-UNKNOWN")
        name = getattr(hypothesis, "name", "Hypothesis")
        stage = getattr(hypothesis, "stage", None)
        stage_str = stage.value if hasattr(stage, "value") else str(stage)
        sharpe = getattr(hypothesis, "backtest_sharpe", 0.0)
        win_rate = getattr(hypothesis, "backtest_win_rate_pct", 0.0)
        shadow_wr = getattr(hypothesis, "shadow_win_rate_pct", 0.0)
        desc = getattr(hypothesis, "description", "")

        filename = f"{hyp_id}_{name.replace(' ', '_')}.md"
        filepath = os.path.join(self.vault_path, "Research", filename)

        content = f"""---
type: research_hypothesis
hypothesis_id: "{hyp_id}"
name: "{name}"
date: {date_str}
stage: "{stage_str}"
sharpe_ratio: {sharpe:.2f}
backtest_win_rate: {win_rate:.1f}
shadow_win_rate: {shadow_wr:.1f}
tags:
  - research
  - hypothesis
  - {stage_str.lower()}
---

# 🧪 Research Hypothesis: `{hyp_id}` ({name})

> [!abstract] **Validation Pipeline State**
> - **ID:** `{hyp_id}`
> - **Current Gatekeeper Stage:** `{stage_str}`
> - **Backtest Sharpe Ratio:** `{sharpe:.2f}`
> - **Backtest Win Rate:** `{win_rate:.1f}%`
> - **Live Shadow Win Rate:** `{shadow_wr:.1f}%`

---

## 📋 Concept & Theory
{desc}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")

        logger.info(f"Obsidian research hypothesis exported: '{filepath}'")
        self._git_sync(commit_message=f"Auto-sync: update research hypothesis {hyp_id}")
        return filepath
