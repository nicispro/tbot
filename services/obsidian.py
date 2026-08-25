"""
Obsidian Integration Service
Communicates with Obsidian Local REST API to generate and append daily Markdown trade journals,
market scan cycle evaluations, technical indicators, and portfolio logs formatted for Dataview.
"""

import datetime
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import requests
import urllib3

from services.trading212 import AccountCash

logger = logging.getLogger(__name__)


@dataclass
class TradeLogRecord:
    """Represents a trade execution record to be logged in Obsidian."""
    timestamp: datetime.datetime
    ticker: str
    action: str  # BUY or SELL
    price: float
    quantity: float
    order_value: float
    strategy_reason: str
    execution_success: bool
    order_id: Optional[str] = None
    broker_status: str = "PENDING"
    environment: str = "demo"
    error_message: Optional[str] = None
    extra_meta: Optional[Dict[str, Any]] = None


class ObsidianClient:
    """
    Client for interacting with Obsidian Local REST API plugin.
    Appends or creates Markdown daily log files in the specified vault folder.
    """

    def __init__(
        self,
        api_key: str,
        host: str = "127.0.0.1",
        port: int = 27124,
        use_https: bool = True,
        verify_ssl: bool = False,
        vault_folder: str = "Trading-Logs",
        timeout: int = 10
    ):
        self.api_key = api_key.strip()
        self.host = host.strip()
        self.port = port
        self.use_https = use_https
        self.verify_ssl = verify_ssl
        self.vault_folder = vault_folder.strip("/\\")
        self.timeout = timeout

        protocol = "https" if self.use_https else "http"
        self.base_url = f"{protocol}://{self.host}:{self.port}"

        if not self.verify_ssl:
            # Suppress self-signed certificate warnings for local Obsidian HTTPS
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self._session = requests.Session()
        self._session.verify = self.verify_ssl
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/vnd.olra.v1+json",
        })

    def _get_daily_log_filename(self, date_obj: datetime.date) -> str:
        """Returns the Markdown filename for a given date."""
        return f"Trades-Log-{date_obj.strftime('%Y-%m-%d')}.md"

    def _get_vault_file_path(self, filename: str) -> str:
        """Returns the relative vault path for the note."""
        if self.vault_folder:
            return f"{self.vault_folder}/{filename}"
        return filename

    def test_connection(self) -> Dict[str, Any]:
        """
        Tests connectivity and authentication with Obsidian Local REST API.
        """
        if not self.api_key or self.api_key in ("your_obsidian_local_rest_api_key_here", ""):
            raise ValueError("Obsidian REST API Key is not configured.")

        url = f"{self.base_url}/"
        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_file_content(self, vault_path: str) -> Optional[str]:
        """
        Retrieves existing note content from Obsidian vault if it exists.
        """
        url = f"{self.base_url}/vault/{vault_path}"
        headers = {"Accept": "text/markdown"}
        try:
            response = self._session.get(url, headers=headers, timeout=self.timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    def write_file(self, vault_path: str, content: str) -> bool:
        """
        Creates or replaces a file in the Obsidian vault.
        """
        url = f"{self.base_url}/vault/{vault_path}"
        headers = {"Content-Type": "text/markdown"}
        response = self._session.put(url, data=content.encode("utf-8"), headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return True

    def append_to_file(self, vault_path: str, content_to_append: str) -> bool:
        """
        Appends Markdown content to an existing file, or creates it if not found.
        """
        url = f"{self.base_url}/vault/{vault_path}"
        headers = {"Content-Type": "text/markdown"}
        try:
            response = self._session.post(url, data=content_to_append.encode("utf-8"), headers=headers, timeout=self.timeout)
            if response.ok:
                return True
        except Exception:
            logger.debug(f"Direct POST append not supported or failed on {vault_path}, falling back to GET + PUT.")

        # Fallback: Read current content, append, and PUT
        existing = self.get_file_content(vault_path) or ""
        new_content = existing + ("\n\n" if existing else "") + content_to_append.strip()
        return self.write_file(vault_path, new_content)

    def _generate_initial_daily_note(self, date_obj: datetime.date, market_target: str = "stocks") -> str:
        """Generates starter template for a new daily trade log note."""
        date_str = date_obj.strftime("%Y-%m-%d")
        return f"""---
tags:
  - trading-bot
  - daily-trade-log
  - stocks
  - crypto
date: {date_str}
market_target: {market_target}
type: trade-journal
status: active
---

# 📈 Daily Trade & Market Scan Log: {date_str}

> [!NOTE] Bot Status
> This log is automatically updated by the automated Trading Bot with real-time indicators and Groq AI analysis.

## 📊 Summary Table
| Time (UTC) | Ticker | Action | Price | Quantity | Total Value | Status | Order ID |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |

## 📝 Trade Executions & Details
"""

    def _format_trade_entry_markdown(self, record: TradeLogRecord) -> str:
        """Formats a single trade execution into an Obsidian Markdown entry with Callouts."""
        time_str = record.timestamp.strftime("%H:%M:%S")
        date_str = record.timestamp.strftime("%Y-%m-%d")
        action_icon = "🟢" if record.action.upper() == "BUY" else "🔴"
        status_badge = "✅ SUCCESS" if record.execution_success else "❌ FAILED"
        callout_type = "success" if record.execution_success else "danger"

        # Table row to insert
        table_row = (
            f"| {time_str} | **{record.ticker}** | {action_icon} {record.action.upper()} | "
            f"${record.price:,.2f} | {record.quantity:.4f} | ${record.order_value:,.2f} | "
            f"`{record.broker_status}` | `{record.order_id or 'N/A'}` |"
        )

        entry_markdown = f"""
> [!{callout_type}] Trade Entry: {action_icon} {record.action.upper()} `{record.ticker}` @ ${record.price:,.2f}
> - **Timestamp:** `{date_str} {time_str} UTC`
> - **Environment:** `{record.environment.upper()}`
> - **Action:** `{record.action.upper()}`
> - **Price:** `${record.price:,.2f}`
> - **Quantity:** `{record.quantity:.4f}` shares
> - **Estimated Value:** `${record.order_value:,.2f}`
> - **Execution Result:** {status_badge} (`{record.broker_status}`)
> - **Order ID:** `{record.order_id or 'N/A'}`
> - **Strategy Reason:** {record.strategy_reason}
"""
        if record.extra_meta and "ai_sentiment" in record.extra_meta:
            ai_sent = record.extra_meta.get("ai_sentiment", "NEUTRAL")
            ai_conf = record.extra_meta.get("ai_confidence", "N/A")
            ai_sum = record.extra_meta.get("ai_summary", "")
            entry_markdown += f"> - 🤖 **AI Analysis:** `{ai_sent}` ({ai_conf}% confidence) - _{ai_sum}_\n"

        if record.error_message:
            entry_markdown += f"> - ⚠️ **Error Info:** `{record.error_message}`\n"

        return table_row, entry_markdown

    def log_trade(self, record: TradeLogRecord) -> str:
        """
        Logs a trade record to Obsidian in the daily note `Trades-Log-YYYY-MM-DD.md`.
        Ensures the table and detailed callout blocks are maintained seamlessly.
        """
        date_obj = record.timestamp.date()
        filename = self._get_daily_log_filename(date_obj)
        vault_path = self._get_vault_file_path(filename)

        logger.info(f"Logging trade {record.action} {record.ticker} into Obsidian note: {vault_path}")

        current_content = self.get_file_content(vault_path)
        table_row, callout_entry = self._format_trade_entry_markdown(record)

        if not current_content:
            initial_note = self._generate_initial_daily_note(date_obj)
            split_target = "## 📊 Summary Table\n| Time (UTC) | Ticker | Action | Price | Quantity | Total Value | Status | Order ID |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
            if split_target in initial_note:
                updated_content = initial_note.replace(
                    split_target,
                    f"{split_target}\n{table_row}"
                )
                updated_content += f"\n{callout_entry}"
            else:
                updated_content = f"{initial_note}\n{table_row}\n\n{callout_entry}"

            self.write_file(vault_path, updated_content)
        else:
            lines = current_content.splitlines()
            table_inserted = False
            new_lines = []

            for i, line in enumerate(lines):
                new_lines.append(line)
                if "| Time (UTC) | Ticker |" in line or "| :--- | :--- |" in line:
                    if i + 1 < len(lines) and not lines[i + 1].startswith("| :---"):
                        new_lines.append(table_row)
                        table_inserted = True

            if not table_inserted:
                new_lines.append(table_row)

            new_lines.append(callout_entry)
            self.write_file(vault_path, "\n".join(new_lines))

        return vault_path

    def log_market_scan_cycle(
        self,
        timestamp: datetime.datetime,
        market_target: str,
        cash: Optional[AccountCash] = None,
        stock_cash: Optional[AccountCash] = None,
        crypto_cash: Optional[AccountCash] = None,
        crypto_exchange_name: str = "binance",
        open_positions_count: int = 0,
        evaluated_signals: Optional[List[Dict[str, Any]]] = None,
        dry_run: bool = False,
        scan_mode: bool = False,
        top_radar_opportunities: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Logs a structured market scan cycle summary to the daily note in Obsidian.
        Includes timestamp, market target (stocks/crypto/all), separated stock and crypto balances,
        technical indicators evaluated (e.g. SMA 10 vs SMA 50, Dip %), radar opportunity rankings, and triggered signals.
        """
        evaluated_signals = evaluated_signals or []
        effective_stock_cash = stock_cash or cash

        date_obj = timestamp.date()
        filename = self._get_daily_log_filename(date_obj)
        vault_path = self._get_vault_file_path(filename)

        time_str = timestamp.strftime("%H:%M:%S")
        date_str = timestamp.strftime("%Y-%m-%d")
        mode_badge = "DRY-RUN SIMULATION" if dry_run else "LIVE TRADING"

        current_content = self.get_file_content(vault_path)
        if not current_content:
            current_content = self._generate_initial_daily_note(date_obj, market_target=market_target)

        # Build scan cycle Markdown block
        cycle_md = f"""
### 🔍 Market Evaluation Cycle: `{time_str} UTC` ({market_target.upper()} | {mode_badge})
> [!info] Cycle & Account Status
> - **Timestamp:** `{date_str} {time_str} UTC`
> - **Target Market:** `{market_target}` ({"Dynamic Scanner" if scan_mode else "Watchlist"})
> - **Instruments Evaluated:** `{len(evaluated_signals)}` | **Open Stock Positions:** `{open_positions_count}`
"""
        if market_target in ("stocks", "all") and effective_stock_cash:
            pnl_sign = "+" if effective_stock_cash.ppl >= 0 else ""
            cycle_md += f"> - **Stocks Account (Trading 212):** Free: `${effective_stock_cash.free:,.2f}` | Invested: `${effective_stock_cash.invested:,.2f}` | Total: `${effective_stock_cash.total:,.2f}` | PnL: `{pnl_sign}${effective_stock_cash.ppl:,.2f}`\n"

        if market_target in ("crypto", "all"):
            if crypto_cash:
                cycle_md += f"> - **Crypto Account ({crypto_exchange_name.upper()}):** Free: `{crypto_cash.free:,.2f} USDT` | Total: `{crypto_cash.total:,.2f} USDT`\n"
            else:
                cycle_md += "> - **Crypto Account:** *Simulation Mode without wallet balance (public data scan)*\n"

        if top_radar_opportunities:
            cycle_md += """
#### 📡 KODA Market Radar: Top Ranked Opportunities
| Grade | Ticker | Market | Price | Composite Score | Key Confluence Events |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
            for opp in top_radar_opportunities[:8]:
                grd = opp.get("grade", "B")
                t = opp.get("ticker", "")
                m = str(opp.get("market_type", "")).upper()
                p = opp.get("price", 0.0)
                score = opp.get("composite_score", 0.0)
                evts = opp.get("key_events", [])
                evts_str = "; ".join(evts[:2]) if evts else "Solid technical alignment"
                p_str = f"${p:,.2f}" if p >= 1.0 else f"${p:.4f}"
                cycle_md += f"| **`[{grd}]`** | **{t}** | `{m}` | {p_str} | **`{score:.1f}`/100** | {evts_str} |\n"

        if evaluated_signals:
            cycle_md += """
#### 📈 Evaluated Indicators & Decisions
| Ticker | Price | Short SMA | Long SMA | Dip % | Signal | Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
            # Include top 25 evaluated signals in the table to prevent giant notes
            for item in evaluated_signals[:25]:
                ticker = item.get("ticker", "")
                price = item.get("price", 0.0)
                short_sma = item.get("short_sma", 0.0)
                long_sma = item.get("long_sma", 0.0)
                dip_pct = item.get("dip_percentage", 0.0)
                action = str(item.get("action", "HOLD")).upper()
                reason = str(item.get("reason", "")).replace("|", "/")
                short_reason = (reason[:45] + "...") if len(reason) > 45 else reason

                action_icon = "🟢 BUY" if action == "BUY" else ("🔴 SELL" if action == "SELL" else "⏸ HOLD")
                short_sma_str = f"${short_sma:,.2f}" if short_sma > 0 else "N/A"
                long_sma_str = f"${long_sma:,.2f}" if long_sma > 0 else "N/A"
                price_str = f"${price:,.2f}" if price >= 1.0 else f"${price:.4f}"

                cycle_md += f"| **{ticker}** | {price_str} | {short_sma_str} | {long_sma_str} | {dip_pct:.2f}% | {action_icon} | {short_reason} |\n"

            if len(evaluated_signals) > 25:
                cycle_md += f"\n*...and {len(evaluated_signals) - 25} more instruments evaluated in this scan cycle.*\n"

        # Append to existing daily note
        updated_content = current_content.strip() + "\n\n" + cycle_md.strip() + "\n"
        self.write_file(vault_path, updated_content)
        logger.info(f"Appended market scan cycle report to Obsidian note: {vault_path}")

        return vault_path

    def log_learning_journal(
        self,
        evaluated_outcomes: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> str:
        """
        Logs forward-tested trade signal outcomes into `Learning-Journal.md` in Obsidian,
        updating frontmatter accuracy metrics and appending verified outcome tables for Dataview.
        """
        filename = "Learning-Journal.md"
        vault_path = self._get_vault_file_path(filename)
        now = datetime.datetime.now(datetime.timezone.utc)
        now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        win_rate = stats.get("win_rate_percent", 0.0)
        total_eval = stats.get("evaluated_count", 0)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        neutrals = stats.get("neutrals", 0)
        avg_pnl = stats.get("avg_pnl_percent", 0.0)
        avg_win = stats.get("avg_win_percent", 0.0)
        avg_loss = stats.get("avg_loss_percent", 0.0)

        existing_content = self.get_file_content(vault_path)

        header_block = f"""---
tags:
  - trading-bot
  - learning-log
  - ai-memory
  - strategy-review
type: machine-learning-feedback
win_rate: {win_rate}%
total_signals_evaluated: {total_eval}
wins: {wins}
losses: {losses}
last_updated: "{now_str}"
---

# 🧠 Automated Strategy Learning & Outcome Journal

> [!abstract] Strategy Accuracy Metrics
> - **Win Rate:** `{win_rate}%` ({wins} Wins / {losses} Losses / {neutrals} Neutral)
> - **Total Evaluated Signals:** `{total_eval}`
> - **Average Outcome PnL:** `{avg_pnl:+.2f}%` (Avg Win: `{avg_win:+.2f}%` | Avg Loss: `{avg_loss:+.2f}%`)
> - **Last Evaluation:** `{now_str}`

## 📊 Verified Signal Outcomes Log
| ID | Signal Time (UTC) | Ticker | Market | Signal | Entry Price | Exit Price | PnL % | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""

        rows_md = ""
        for out in evaluated_outcomes:
            sig_id = out.get("id", "N/A")
            sig_time = str(out.get("signal_time", ""))[:19].replace("T", " ")
            ticker = out.get("ticker", "")
            mkt = str(out.get("market_type", "")).upper()
            sig_type = str(out.get("signal_type", "")).upper()
            entry_p = out.get("entry_price", 0.0)
            exit_p = out.get("exit_price", 0.0)
            pnl_pct = out.get("pnl_percent", 0.0)
            outcome = out.get("outcome", "NEUTRAL")

            outcome_tag = f"`{outcome}`"
            if outcome == "WIN":
                outcome_tag = f"🟢 **#win** (`+{pnl_pct:.2f}%`)"
            elif outcome == "LOSS":
                outcome_tag = f"🔴 **#loss** (`{pnl_pct:.2f}%`)"

            entry_p_str = f"${entry_p:,.2f}" if entry_p >= 1.0 else f"${entry_p:.4f}"
            exit_p_str = f"${exit_p:,.2f}" if exit_p >= 1.0 else f"${exit_p:.4f}"

            rows_md += f"| #{sig_id} | {sig_time} | **{ticker}** | `{mkt}` | `{sig_type}` | {entry_p_str} | {exit_p_str} | {pnl_pct:+.2f}% | {outcome_tag} |\n"

        if not existing_content:
            new_content = header_block + rows_md
        else:
            if "## 📊 Verified Signal Outcomes Log" in existing_content:
                parts = existing_content.split("## 📊 Verified Signal Outcomes Log")
                table_header = "\n| ID | Signal Time (UTC) | Ticker | Market | Signal | Entry Price | Exit Price | PnL % | Outcome |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
                existing_table_body = parts[1].replace(table_header, "").strip()
                new_content = header_block + (existing_table_body + "\n" if existing_table_body else "") + rows_md
            else:
                new_content = header_block + rows_md

        self.write_file(vault_path, new_content.strip() + "\n")
        logger.info(f"Updated Obsidian Learning Journal at: {vault_path}")
        return vault_path

    def log_trade_autopsies(
        self,
        autopsies: List[Any],
        stats: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Appends detailed trade post-mortem autopsy reports into `Learning-Journal.md` in Obsidian
        with Dataview tags #learning-log, #trade-autopsy, #win, #loss, and actionable retrospective lessons.
        """
        filename = "Learning-Journal.md"
        vault_path = self._get_vault_file_path(filename)
        current_content = self.get_file_content(vault_path) or "# 🧠 Automated Strategy Learning & Outcome Journal\n"

        autopsies_md = "\n## 🔬 Trade Post-Mortem Autopsies & Actionable Lessons\n"
        for rep in autopsies:
            sig_id = getattr(rep, "signal_id", "N/A")
            ticker = getattr(rep, "ticker", "")
            outcome = getattr(rep, "outcome", "NEUTRAL")
            pnl_pct = getattr(rep, "pnl_percent", 0.0)
            sig_type = getattr(rep, "signal_type", "BUY")
            entry_p = getattr(rep, "entry_price", 0.0)
            exit_p = getattr(rep, "exit_price", 0.0)
            root_cause = getattr(rep, "root_cause", "UNKNOWN")
            driver = getattr(rep, "primary_driver", "")
            lesson = getattr(rep, "actionable_lesson", "")
            rule = getattr(rep, "rule_recommendation", "")
            time_str = getattr(rep, "evaluated_at", "")[:19].replace("T", " ")

            outcome_badge = "🟢 WIN" if outcome == "WIN" else ("🔴 LOSS" if outcome == "LOSS" else "⚖️ NEUTRAL")
            entry_p_str = f"${entry_p:,.2f}" if entry_p >= 1.0 else f"${entry_p:.4f}"
            exit_p_str = f"${exit_p:,.2f}" if exit_p >= 1.0 else f"${exit_p:.4f}"

            autopsies_md += f"""
### 🔬 Autopsy #{sig_id}: {ticker} ({outcome_badge} `{pnl_pct:+.2f}%`)
> [!quote] Retrospective Diagnosis `{time_str} UTC`
> - **Signal:** `{sig_type}` @ {entry_p_str} ➔ {exit_p_str} (`{pnl_pct:+.2f}%`)
> - **Root Cause:** `{root_cause}`
> - **Driver:** *{driver}*
> - **💡 Actionable Lesson:** **{lesson}**
> - **🛡 Rule Recommendation:** `{rule}`
"""

        updated_content = current_content.strip() + "\n" + autopsies_md.strip() + "\n"
        self.write_file(vault_path, updated_content)
        logger.info(f"Appended {len(autopsies)} trade autopsies to Obsidian note: {vault_path}")
        return vault_path

    def log_morning_brief(
        self,
        top_radar_setups: Optional[List[Dict[str, Any]]] = None,
        macro_sentiment: str = "NEUTRAL / MIXED",
        stock_cash: Optional[AccountCash] = None,
        crypto_cash: Optional[AccountCash] = None,
        focus_notes: str = "Focus on high-conviction pullbacks."
    ) -> str:
        """
        Logs the Morning Intelligence Brief into today's Obsidian daily note.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        filename = f"{date_str}.md"
        vault_path = self._get_vault_file_path(filename)
        current_content = self.get_file_content(vault_path) or f"# 📈 Trading Journal - {date_str}\n"

        brief_md = f"""
## 🌅 KODA Morning Intelligence Brief ({now.strftime('%H:%M UTC')})
> [!summary] Macro Regime & Tactical Focus
> - **Macro Sentiment:** `{macro_sentiment}`
> - **Tactical Focus:** {focus_notes}

### 💼 Portfolio Capital Allocation
"""
        if stock_cash:
            brief_md += f"- **Stocks (T212):** Free: `${stock_cash.free:,.2f}` | Total: `${stock_cash.total:,.2f}` | PnL: `${stock_cash.ppl:+,.2f}`\n"
        if crypto_cash:
            brief_md += f"- **Crypto:** Free: `{crypto_cash.free:,.2f} USDT` | Total: `{crypto_cash.total:,.2f} USDT`\n"

        if top_radar_setups:
            brief_md += "\n### 📡 Top Radar Opportunities\n| Grade | Ticker | Market | Price | Score | Key Confluence |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            for op in top_radar_setups[:5]:
                g = op.get("grade", "B")
                t = op.get("ticker", "")
                m = op.get("market_type", "").upper()
                p = op.get("price", 0.0)
                sc = op.get("composite_score", 0.0)
                evts = "; ".join(op.get("key_events", [])[:2]) if op.get("key_events") else "Trend alignment"
                p_str = f"${p:,.2f}" if p >= 1.0 else f"${p:.4f}"
                brief_md += f"| `{g}` | **{t}** | `{m}` | {p_str} | {sc:.0f}/100 | {evts} |\n"

        updated = current_content.strip() + "\n\n" + brief_md.strip() + "\n"
        self.write_file(vault_path, updated)
        logger.info(f"Appended Morning Brief to Obsidian daily note: {vault_path}")
        return vault_path

    def log_evening_brief(
        self,
        daily_stats: Optional[Dict[str, Any]] = None,
        stock_cash: Optional[AccountCash] = None,
        crypto_cash: Optional[AccountCash] = None,
        autopsy_lessons: Optional[List[str]] = None,
        open_positions: Optional[List[str]] = None
    ) -> str:
        """
        Logs the End-of-Day Evening Brief into today's Obsidian daily note.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        filename = f"{date_str}.md"
        vault_path = self._get_vault_file_path(filename)
        current_content = self.get_file_content(vault_path) or f"# 📈 Trading Journal - {date_str}\n"

        stats = daily_stats or {}
        win_rate = stats.get("win_rate_percent", 0.0)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        total_eval = stats.get("evaluated_count", 0)
        avg_pnl = stats.get("avg_pnl_percent", 0.0)

        brief_md = f"""
## 🌆 KODA End-of-Day Intelligence Brief ({now.strftime('%H:%M UTC')})
> [!abstract] Daily Performance Recap
> - **Win Rate:** `{win_rate}%` ({wins}W / {losses}L across {total_eval} signals)
> - **Average Outcome PnL:** `{avg_pnl:+.2f}%`

### 💼 Closing Portfolio State
"""
        if stock_cash:
            brief_md += f"- **Stocks (T212):** Total: `${stock_cash.total:,.2f}` | Free: `${stock_cash.free:,.2f}` | PnL: `${stock_cash.ppl:+,.2f}`\n"
        if crypto_cash:
            brief_md += f"- **Crypto:** Total: `{crypto_cash.total:,.2f} USDT` | Free: `{crypto_cash.free:,.2f} USDT`\n"

        if open_positions:
            brief_md += f"\n- **Overnight Open Exposure ({len(open_positions)}):** `{', '.join(open_positions)}`\n"
        else:
            brief_md += "\n- **Overnight Open Exposure:** *Zero open exposure (100% liquid cash)*\n"

        if autopsy_lessons:
            brief_md += "\n### 🔬 Key Trade Lessons Learned\n"
            for les in autopsy_lessons[:3]:
                brief_md += f"- 💡 *{les}*\n"

        updated = current_content.strip() + "\n\n" + brief_md.strip() + "\n"
        self.write_file(vault_path, updated)
        logger.info(f"Appended Evening Brief to Obsidian daily note: {vault_path}")
        return vault_path

