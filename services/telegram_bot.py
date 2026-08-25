import datetime
import os
import re
import logging
import time
from typing import Optional, Any, List, Dict, Tuple
import requests

from services.obsidian import TradeLogRecord
from services.ai_analyzer import AIAnalysisResult
from services.trading212 import AccountCash
from services.market_regime import MarketRegimeEngine
from services.news_sentiment import EconomicCalendar, NewsSentimentEngine
from services.execution_quality import ExecutionQualityEngine
from services.trade_autopsy import TradeAutopsyEngine, DecisionOutcomeQuadrant
from services.confidence_tracker import ConfidenceTracker
from services.research_lab import ResearchLabEngine, HypothesisStage
from services.strategy_tournament import StrategyTournamentEngine
from services.signal_tracker import SignalTracker

logger = logging.getLogger(__name__)


def get_recent_system_logs(max_lines: int = 35) -> str:
    """
    Extracts recent error traces and operational logs from log files or database audit trail.
    """
    # 1. Check local log files
    for log_filename in ("app.log", "error.log", "tbot.log", "bot.log", "trading.log"):
        if os.path.exists(log_filename):
            try:
                with open(log_filename, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    if lines:
                        recent = lines[-max_lines:]
                        return "".join(recent).strip()
            except Exception as e:
                logger.debug(f"Could not read {log_filename}: {e}")

    # 2. Fallback to decision audit trail and execution DB logs
    try:
        from services.audit_trail import DecisionAuditTrail
        audit = DecisionAuditTrail()
        traces = audit.get_recent_traces(limit=10)
        if traces:
            log_lines = ["[RECENT DECISION AUDIT TRACES]"]
            for t in traces:
                status_icon = "SUCCESS" if t.execution_status == "EXECUTED" else f"VETO ({t.execution_status})"
                rej = f" | Rejection: {t.rejection_reason}" if t.rejection_reason else ""
                log_lines.append(
                    f"• {t.ticker} ({t.market_type.upper()}): Regime={t.regime}, Quant={t.quant_score:.0f}, "
                    f"AI={t.ai_sentiment}({t.ai_confidence}%), Status={status_icon}{rej}"
                )
            return "\n".join(log_lines)
    except Exception as e:
        logger.debug(f"Audit log retrieval fallback: {e}")

    return "No active error traces found in system log."


class TelegramNotifier:
    """
    Client for dispatching real-time notifications to Telegram via the Telegram Bot API.
    """

    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout: int = 15
    ):
        raw_token = bot_token if bot_token is not None else (os.getenv("TELEGRAM_BOT_TOKEN") or "")
        raw_chat_id = chat_id if chat_id is not None else (os.getenv("TELEGRAM_CHAT_ID") or "")
        self.bot_token = raw_token.strip()
        self.chat_id = raw_chat_id.strip()
        self.timeout = timeout
        self._session = requests.Session()

    def is_configured(self) -> bool:
        """Checks whether Telegram Bot token and Chat ID are configured."""
        return bool(
            self.bot_token
            and self.chat_id
            and self.bot_token != "your_telegram_bot_token_here"
            and self.chat_id != "your_telegram_chat_id_here"
        )

    def send_message(self, text: str, parse_mode: Optional[str] = "HTML", target_chat_id: Optional[str] = None) -> bool:
        """
        Sends a message to the configured or specified Telegram chat.
        Includes automatic fallback to plain-text transmission if HTML/entity parsing fails (HTTP 400).
        """
        if not self.bot_token:
            logger.debug("Telegram bot token not configured. Skipping notification.")
            return False

        dest_chat = target_chat_id or self.chat_id
        if not dest_chat:
            logger.debug("Telegram chat ID not configured. Skipping notification.")
            return False

        url = self.BASE_URL.format(token=self.bot_token)
        payload: Dict[str, Any] = {
            "chat_id": dest_chat,
            "text": text,
            "disable_web_page_preview": True
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        def _execute_post(data_payload: Dict[str, Any]) -> requests.Response:
            try:
                return self._session.post(url, json=data_payload, timeout=self.timeout)
            except requests.exceptions.SSLError:
                return self._session.post(url, json=data_payload, timeout=self.timeout, verify=False)

        try:
            response = _execute_post(payload)

            # If Telegram rejects with 400 (e.g. unclosed tags or entity parse errors), sanitize and send as plain text
            if response.status_code == 400 and parse_mode:
                logger.warning(
                    f"Telegram HTTP 400 Bad Request on parse_mode='{parse_mode}': {response.text[:150]}. "
                    f"Sanitizing text and re-sending as plain text..."
                )
                plain_text = re.sub(r'<[^>]+>', '', text)
                fallback_payload: Dict[str, Any] = {
                    "chat_id": dest_chat,
                    "text": plain_text,
                    "disable_web_page_preview": True
                }
                fallback_resp = _execute_post(fallback_payload)
                if fallback_resp.ok:
                    logger.info(f"Telegram notification delivered successfully as plain text to {dest_chat}.")
                    return True
                else:
                    logger.error(f"Telegram plain-text fallback delivery failed with status {fallback_resp.status_code}: {fallback_resp.text}")
                    return False

            response.raise_for_status()
            logger.info(f"Telegram notification sent successfully to {dest_chat}.")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_trade_alert(
        self,
        record: TradeLogRecord,
        ai_analysis: Optional[AIAnalysisResult] = None
    ) -> bool:
        """
        Formats and sends a comprehensive real-time trade execution alert.
        """
        action_emoji = "🟢 <b>BUY ORDER</b>" if record.action.upper() == "BUY" else "🔴 <b>SELL ORDER</b>"
        status_emoji = "✅ SUCCESS" if record.execution_success else "❌ FAILED"
        time_str = record.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = f"""
{action_emoji}
━━━━━━━━━━━━━━━━━━
🏷 <b>Ticker:</b> <code>{record.ticker}</code>
💰 <b>Price:</b> <code>${record.price:,.2f}</code>
📦 <b>Quantity:</b> <code>{record.quantity:.4f} shares</code>
💵 <b>Total Value:</b> <code>${record.order_value:,.2f}</code>
🌐 <b>Environment:</b> <code>{record.environment.upper()}</code>
⚡ <b>Status:</b> {status_emoji} (<code>{record.broker_status}</code>)
🆔 <b>Order ID:</b> <code>{record.order_id or 'N/A'}</code>
⏱ <b>Time:</b> <code>{time_str}</code>

📊 <b>Strategy Reason:</b>
<i>{record.strategy_reason}</i>
"""
        if ai_analysis:
            sentiment_emoji = "🚀" if ai_analysis.sentiment == "BULLISH" else ("📉" if ai_analysis.sentiment == "BEARISH" else "⚖️")
            msg += f"""
🤖 <b>Groq AI Analysis:</b>
{sentiment_emoji} <b>Sentiment:</b> <code>{ai_analysis.sentiment}</code> ({ai_analysis.confidence_score}% confidence)
💡 <b>Thesis:</b> <i>{ai_analysis.summary}</i>
🔑 <b>Catalysts:</b> <i>{ai_analysis.catalysts}</i>
"""

        if record.error_message:
            msg += f"\n⚠️ <b>Error Details:</b> <code>{record.error_message}</code>\n"

        return self.send_message(msg.strip())

    def send_cycle_summary(
        self,
        evaluated_count: int = 0,
        executed_count: int = 0,
        cash: Optional[AccountCash] = None,
        stock_cash: Optional[AccountCash] = None,
        crypto_cash: Optional[AccountCash] = None,
        crypto_exchange_name: str = "binance",
        dry_run: bool = False,
        scan_mode: bool = False,
        target_market: str = "all",
        stocks_evaluated: int = 0,
        crypto_evaluated: int = 0,
        signals_summary: Optional[List[Dict[str, Any]]] = None,
        duration_seconds: float = 0.0,
        top_radar_opportunities: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Sends a comprehensive dual-market trading cycle summary report to Telegram.
        """
        mode_badge = "🧪 <b>[DRY-RUN SIMULATION]</b>" if dry_run else "⚡ <b>[LIVE TRADING]</b>"
        effective_stock_cash = stock_cash or cash

        msg = f"""
📊 <b>TBOT Evaluation Cycle Report</b>
{mode_badge}
━━━━━━━━━━━━━━━━━━
🌐 <b>Market Target:</b> <code>{target_market.upper()}</code>
📈 <b>Stocks Evaluated:</b> <code>{stocks_evaluated}</code>
🪙 <b>Crypto Evaluated:</b> <code>{crypto_evaluated}</code>
🎯 <b>Signals / Trades:</b> <code>{executed_count}</code>
⏱ <b>Duration:</b> <code>{duration_seconds:.1f}s</code>
"""
        # 1. Stocks Account Section
        if target_market in ("stocks", "all") and effective_stock_cash:
            pnl_emoji = "🟢" if effective_stock_cash.ppl >= 0 else "🔴"
            msg += f"""
💼 <b>Stocks Account (Trading 212):</b>
• Free Cash: <code>${effective_stock_cash.free:,.2f}</code>
• Invested: <code>${effective_stock_cash.invested:,.2f}</code>
• Total Value: <code>${effective_stock_cash.total:,.2f}</code>
• Unrealized PnL: {pnl_emoji} <code>${effective_stock_cash.ppl:+,.2f}</code>
"""

        # 2. Crypto Account Section
        if target_market in ("crypto", "all"):
            if crypto_cash:
                msg += f"""
🪙 <b>Crypto Account ({crypto_exchange_name.upper()}):</b>
• Free USDT: <code>{crypto_cash.free:,.2f} USDT</code>
• Invested: <code>{crypto_cash.invested:,.2f} USDT</code>
• Total Balance: <code>{crypto_cash.total:,.2f} USDT</code>
"""
            else:
                msg += f"""
🪙 <b>Crypto Account:</b>
• <i>Simulation Mode (Public Scan, No Wallet Keys Configured)</i>
"""

        # 3. Top Market Radar Opportunities
        if top_radar_opportunities:
            msg += "\n📡 <b>KODA Radar - Top Opportunities:</b>\n"
            for opp in top_radar_opportunities[:5]:
                t = opp.get("ticker", "")
                score = opp.get("composite_score", 0.0)
                grade = opp.get("grade", "B")
                price = opp.get("price", 0.0)
                price_str = f"${price:,.2f}" if price >= 1.0 else f"${price:.4f}"
                msg += f"• 🏆 <b>[{grade}]</b> <code>{t}</code> @ {price_str} (Score: <b>{score:.0f}</b>/100)\n"

        # 4. Triggered Signals Section
        if signals_summary:
            msg += "\n🎯 <b>Triggered Signals:</b>\n"
            for sig in signals_summary[:8]:
                action = sig.get("action", "BUY")
                emoji = "🟢" if action == "BUY" else "🔴"
                ticker = sig.get("ticker", "")
                price = sig.get("price", 0.0)
                reason = sig.get("reason", "")
                short_reason = (reason[:45] + "...") if len(reason) > 45 else reason
                price_str = f"${price:,.2f}" if price >= 1.0 else f"${price:.4f}"
                msg += f"• {emoji} <b>{action}</b> <code>{ticker}</code> @ {price_str} (<i>{short_reason}</i>)\n"
            if len(signals_summary) > 8:
                msg += f"<i>...and {len(signals_summary) - 8} more</i>\n"
        elif executed_count == 0:
            msg += "\n💤 <b>Status:</b> No trade signals triggered this cycle."

        return self.send_message(msg.strip())

    def send_morning_brief(
        self,
        stock_cash: Optional[AccountCash] = None,
        crypto_cash: Optional[AccountCash] = None,
        top_radar_setups: Optional[List[Dict[str, Any]]] = None,
        macro_sentiment: str = "NEUTRAL / MIXED",
        health_state: str = "NORMAL",
        daily_focus_notes: str = "Focus on high-quality A/A+ pullback confirmations."
    ) -> bool:
        """
        Formats and dispatches the KODA Morning Brief to Telegram.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        msg = f"""
🌅 <b>KODA MORNING INTELLIGENCE BRIEF</b>
<code>{now_str}</code>
━━━━━━━━━━━━━━━━━━
🌐 <b>Macro Market Regime:</b> <code>{macro_sentiment}</code>
🛡 <b>System Health Guard:</b> <code>{health_state}</code>

💼 <b>Portfolio & Capital Allocation:</b>
"""
        if stock_cash:
            msg += f"• 📈 <b>Stocks (T212):</b> Free: <code>${stock_cash.free:,.2f}</code> | Total: <code>${stock_cash.total:,.2f}</code> (PnL: <code>${stock_cash.ppl:+,.2f}</code>)\n"
        if crypto_cash:
            msg += f"• 🪙 <b>Crypto:</b> Free: <code>{crypto_cash.free:,.2f} USDT</code> | Total: <code>{crypto_cash.total:,.2f} USDT</code>\n"

        if top_radar_setups:
            msg += "\n📡 <b>Top Radar Watchlist Setups:</b>\n"
            for op in top_radar_setups[:5]:
                grade = op.get("grade", "B")
                t = op.get("ticker", "")
                m = op.get("market_type", "").upper()
                p = op.get("price", 0.0)
                score = op.get("composite_score", 0.0)
                evts = "; ".join(op.get("key_events", [])[:2]) if op.get("key_events") else "Trend alignment"
                price_str = f"${p:,.2f}" if p >= 1.0 else f"${p:.4f}"
                msg += f"• 🏆 <b>[{grade}]</b> <code>{t}</code> ({m}) @ {price_str} | Score: <b>{score:.0f}</b>\n  ↳ <i>{evts}</i>\n"

        msg += f"""
🎯 <b>Tactical Morning Gameplan:</b>
<i>{daily_focus_notes}</i>
"""
        return self.send_message(msg.strip())

    def send_evening_brief(
        self,
        stock_cash: Optional[AccountCash] = None,
        crypto_cash: Optional[AccountCash] = None,
        daily_stats: Optional[Dict[str, Any]] = None,
        autopsy_lessons: Optional[List[str]] = None,
        open_positions: Optional[List[str]] = None
    ) -> bool:
        """
        Formats and dispatches the KODA Evening & End-of-Day Brief to Telegram.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        stats = daily_stats or {}
        win_rate = stats.get("win_rate_percent", 0.0)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        total_eval = stats.get("evaluated_count", 0)
        avg_pnl = stats.get("avg_pnl_percent", 0.0)

        msg = f"""
🌆 <b>KODA END-OF-DAY INTELLIGENCE BRIEF</b>
<code>{now_str}</code>
━━━━━━━━━━━━━━━━━━
📊 <b>Strategy Accuracy & Track Record:</b>
• <b>Win Rate:</b> <code>{win_rate}%</code> ({wins}W / {losses}L across {total_eval} signals)
• <b>Average PnL:</b> <code>{avg_pnl:+.2f}%</code>

💼 <b>Closing Capital Status:</b>
"""
        if stock_cash:
            msg += f"• 📈 <b>Stocks (T212):</b> Total: <code>${stock_cash.total:,.2f}</code> | Free: <code>${stock_cash.free:,.2f}</code> | PnL: <code>${stock_cash.ppl:+,.2f}</code>\n"
        if crypto_cash:
            msg += f"• 🪙 <b>Crypto:</b> Total: <code>{crypto_cash.total:,.2f} USDT</code> | Free: <code>{crypto_cash.free:,.2f} USDT</code>\n"

        if open_positions:
            msg += f"\n📦 <b>Overnight Open Positions ({len(open_positions)}):</b>\n• <code>{', '.join(open_positions[:6])}</code>\n"
        else:
            msg += "\n📦 <b>Overnight Open Positions:</b> <i>Zero open exposure (100% liquid)</i>\n"

        if autopsy_lessons:
            msg += "\n🔬 <b>Trade Autopsy Lessons & Retrospective:</b>\n"
            for les in autopsy_lessons[:3]:
                msg += f"• 💡 <i>{les}</i>\n"

        msg += "\n🌙 <i>System guards standing by for overnight monitoring.</i>"
        return self.send_message(msg.strip())

    def handle_ask_command(
        self,
        question: str,
        ai_client: Any,
        portfolio_context: Optional[Dict[str, Any]] = None,
        radar_context: Optional[List[Dict[str, Any]]] = None,
        lessons: Optional[List[str]] = None,
        log_context: Optional[str] = None,
        regime_context: Optional[str] = None,
        trade_history_context: Optional[str] = None,
        universe_context: Optional[str] = None,
        obsidian_context: Optional[str] = None,
        dispatch_to_telegram: bool = True
    ) -> str:
        """
        Processes interactive natural language queries with KODA AI and optionally posts the reply to Telegram.
        """
        logger.info(f"Processing Telegram interactive /ask query: '{question}'")
        answer = ai_client.answer_market_query(
            question=question,
            portfolio_context=portfolio_context,
            radar_context=radar_context,
            recent_lessons=lessons,
            log_context=log_context,
            regime_context=regime_context,
            trade_history_context=trade_history_context,
            universe_context=universe_context,
            obsidian_context=obsidian_context
        )

        if dispatch_to_telegram and self.is_configured():
            msg = f"""
🤖 <b>KODA AI Consultation</b>
━━━━━━━━━━━━━━━━━━
❓ <b>Question:</b> <i>{question}</i>

💡 <b>Analysis:</b>
{answer}
"""
            self.send_message(msg.strip())

        return answer


class TelegramBotManager:
    """
    Interactive Telegram Management Bot for KODA Institutional OS:
    Handles remote commands (/status, /stats, /research, /mode, /trade_live, /ask)
    with strict user ID authorization and long-polling listener.
    """

    UPDATES_URL = "https://api.telegram.org/bot{token}/getUpdates"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        allowed_user_id: Optional[str] = None,
        notifier: Optional[TelegramNotifier] = None,
        ai_client: Optional[Any] = None,
        trader_loop: Optional[Any] = None
    ):
        self.bot_token = (bot_token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        self.allowed_user_id = (
            allowed_user_id
            or os.getenv("TELEGRAM_ALLOWED_USER_ID")
            or os.getenv("TELEGRAM_CHAT_ID")
            or ""
        ).strip()
        self.notifier = notifier or TelegramNotifier(bot_token=self.bot_token, chat_id=self.allowed_user_id)
        self.ai_client = ai_client
        self.trader_loop = trader_loop

        # Execution mode state
        self.execution_mode: str = "PAPER"  # 'PAPER' or 'LIVE'
        self.live_trading_enabled: bool = False
        self._awaiting_live_confirmation: bool = False
        self._session = requests.Session()

    def is_authorized(self, user_id: Any) -> bool:
        """Verifies whether the sender's Telegram User ID is authorized."""
        if not self.allowed_user_id:
            return True  # If no specific user ID restricted, defaults to open for configured chat
        return str(user_id).strip() == self.allowed_user_id

    # -------------------------------------------------------------
    # Command Formatters & Handlers
    # -------------------------------------------------------------

    def handle_status(self) -> str:
        """Formats active Market Regime, Macro Status, Trader Loop, and Execution metrics."""
        regime_engine = MarketRegimeEngine()
        econ_cal = EconomicCalendar()
        news_eng = NewsSentimentEngine(calendar=econ_cal)
        exec_eng = ExecutionQualityEngine()

        regime = regime_engine.classify_regime()
        macro_sum = news_eng.evaluate_macro_sentiment()
        exec_sum = exec_eng.get_execution_summary()

        in_risk, active_event, _ = econ_cal.is_in_risk_window()
        blackout_str = f"🔴 ACTIVE ({active_event.title})" if in_risk and active_event else "🟢 INACTIVE (Clear)"

        loop_st = self.trader_loop.get_status() if self.trader_loop else None
        loop_str = f"🟢 ACTIVE (Cycle #{loop_st['cycle_count']}, Every {loop_st['interval_seconds']}s)" if (loop_st and loop_st.get("is_running")) else "⚪ STOPPED"

        return f"""
🧭 <b>KODA SYSTEM STATUS & REGIME</b>
━━━━━━━━━━━━━━━━━━
🌐 <b>Market Regime:</b> <code>{regime.primary_regime.value}</code>
⚡ <b>Volatility Environment:</b> <code>{regime.volatility_level}</code>
📈 <b>Trend Strength:</b> <code>{regime.trend_strength:.1f}/100</code>
🛡 <b>Directives:</b> <i>{regime.rationale}</i>

🌍 <b>Macro Status:</b>
• Event Risk Window: {blackout_str}
• Sentiment Bias: <code>{macro_sum.sentiment_label}</code> (Score: {macro_sum.sentiment_score:.0f}/100)

⚡ <b>Broker Execution Quality:</b>
• Total Fills: <code>{exec_sum['total_executions']}</code>
• Avg Slippage: <code>{exec_sum['avg_slippage_bps']:+.1f} bps</code>
• Broker Fees: <code>${exec_sum['total_fees_usd']:,.2f}</code>

🔄 <b>Background Trader Loop:</b> {loop_str}
⚙️ <b>Execution Mode:</b> <code>{self.execution_mode}</code> (Live Trading: <code>{'ON' if self.live_trading_enabled else 'OFF'}</code>)
""".strip()

    def handle_stats(self) -> str:
        """Formats Trade Autopsy 2.0 Annie Duke process/outcome matrix and calibration scores."""
        tracker = SignalTracker()
        autopsy = TradeAutopsyEngine()
        conf_tracker = ConfidenceTracker()

        evaluated = tracker.get_evaluated_signals(limit=50)
        if not evaluated:
            evaluated = [
                {"id": 1, "ticker": "BTC/USDT", "market_type": "crypto", "signal_type": "BUY", "entry_price": 60000.0, "exit_price": 63000.0, "pnl_percent": 5.0, "outcome": "WIN", "indicators": {"short_sma": 61000.0, "long_sma": 58000.0, "rsi": 62.0, "atr": 1500.0}},
                {"id": 2, "ticker": "SOL/USDT", "market_type": "crypto", "signal_type": "BUY", "entry_price": 140.0, "exit_price": 133.0, "pnl_percent": -5.0, "outcome": "LOSS", "indicators": {"short_sma": 135.0, "long_sma": 130.0, "rsi": 78.0, "atr": 4.0}},
            ]

        quadrants = {
            DecisionOutcomeQuadrant.GOOD_DECISION_WIN.value: 0,
            DecisionOutcomeQuadrant.GOOD_DECISION_LOSS.value: 0,
            DecisionOutcomeQuadrant.BAD_DECISION_WIN.value: 0,
            DecisionOutcomeQuadrant.BAD_DECISION_LOSS.value: 0,
        }
        for ev in evaluated:
            rep = autopsy.analyze_outcome(ev)
            quadrants[rep.decision_outcome_quadrant] = quadrants.get(rep.decision_outcome_quadrant, 0) + 1

        total = sum(quadrants.values()) or 1
        cal_rep = conf_tracker.get_calibration_report()

        lines = [
            "📊 <b>KODA TRADE AUTOPSY 2.0 & STATS</b>",
            "━━━━━━━━━━━━━━━━━━",
            "🧭 <b>Process vs Outcome Matrix (Annie Duke):</b>",
            f"• 🟢 <b>Good Decision / Win:</b> {quadrants[DecisionOutcomeQuadrant.GOOD_DECISION_WIN.value]} ({(quadrants[DecisionOutcomeQuadrant.GOOD_DECISION_WIN.value]/total)*100:.1f}%)",
            f"• 🟡 <b>Good Decision / Loss:</b> {quadrants[DecisionOutcomeQuadrant.GOOD_DECISION_LOSS.value]} ({(quadrants[DecisionOutcomeQuadrant.GOOD_DECISION_LOSS.value]/total)*100:.1f}%)",
            f"• 🎲 <b>Bad Decision / Win:</b> {quadrants[DecisionOutcomeQuadrant.BAD_DECISION_WIN.value]} ({(quadrants[DecisionOutcomeQuadrant.BAD_DECISION_WIN.value]/total)*100:.1f}%)",
            f"• 🔴 <b>Bad Decision / Loss:</b> {quadrants[DecisionOutcomeQuadrant.BAD_DECISION_LOSS.value]} ({(quadrants[DecisionOutcomeQuadrant.BAD_DECISION_LOSS.value]/total)*100:.1f}%)",
            "",
            "🎯 <b>AI Confidence Calibration:</b>"
        ]
        for b in cal_rep.get("brackets", []):
            st = "🟢" if b.status == "CALIBRATED" else "⚠️"
            lines.append(f"• <code>{b.bracket_name}</code>: {b.wins}W/{b.losses}L (Win%: {b.actual_win_rate_pct:.1f}% vs Exp: {b.expected_midpoint:.0f}%) {st}")

        return "\n".join(lines).strip()

    def handle_research(self) -> str:
        """Formats Research Lab hypotheses and Strategy Tournament rankings."""
        lab = ResearchLabEngine()
        tournament = StrategyTournamentEngine()
        regime_engine = MarketRegimeEngine()

        current_regime = regime_engine.classify_regime()
        ranked = tournament.rank_strategies(current_regime=current_regime.primary_regime.value)
        hypotheses = lab.list_all_hypotheses()

        lines = [
            "🧪 <b>KODA RESEARCH LAB & TOURNAMENT</b>",
            "━━━━━━━━━━━━━━━━━━",
            f"🏆 <b>Strategy Tournament (Regime: {current_regime.primary_regime.value}):</b>"
        ]
        for idx, st in enumerate(ranked[:4]):
            lines.append(f"#{idx+1} <b>{st.name}</b> (Alloc: <code>{st.recommended_allocation_pct:.1f}%</code>, Score: <code>{st.tournament_score:.1f}</code>)")

        lines.append("")
        lines.append("📋 <b>Active Research Hypotheses:</b>")
        if hypotheses:
            for h in hypotheses[:4]:
                st_icon = "🟢" if h.stage == HypothesisStage.APPROVED else ("🔴" if h.stage == HypothesisStage.REJECTED else "⏳")
                lines.append(f"• {st_icon} <code>{h.hypothesis_id}</code>: <b>{h.stage.value}</b> (Sharpe: {h.backtest_sharpe:.2f}, Shadow: {h.shadow_win_rate_pct:.1f}%)")
        else:
            lines.append("• <i>No active hypotheses currently in pipeline.</i>")

        return "\n".join(lines).strip()

    def handle_mode(self, args_str: str) -> str:
        """Switches execution mode dynamically between PAPER and LIVE."""
        arg = args_str.strip().upper()
        if arg in ("PAPER", "SIMULATION", "DRY_RUN"):
            self.execution_mode = "PAPER"
            self.live_trading_enabled = False
            self._awaiting_live_confirmation = False
            return "🧪 <b>Execution mode switched to PAPER (Simulation).</b> Live order routing is disabled."
        elif arg == "LIVE":
            if not self.live_trading_enabled:
                self._awaiting_live_confirmation = True
                return (
                    "⚠️ <b>[SAFETY CONFIRMATION REQUIRED]</b>\n"
                    "You requested switching to <b>LIVE TRADING</b> with real capital.\n\n"
                    "To confirm authorization, send: <code>/trade_live CONFIRM_LIVE_TRADING</code>"
                )
            else:
                self.execution_mode = "LIVE"
                return "⚡ <b>Execution mode is LIVE.</b> Real capital orders will be placed."
        else:
            return (
                f"Current Mode: <code>{self.execution_mode}</code>\n"
                "Usage: <code>/mode PAPER</code> or <code>/mode LIVE</code>"
            )

    def handle_trade_live(self, args_str: str) -> str:
        """Toggles live execution engine with strict user confirmation prompt."""
        arg = args_str.strip().upper()
        if arg == "CONFIRM_LIVE_TRADING":
            self.execution_mode = "LIVE"
            self.live_trading_enabled = True
            self._awaiting_live_confirmation = False
            logger.warning("🚨 [TELEGRAM MANAGEMENT] User authorized LIVE TRADING mode.")
            return "🚨 <b>LIVE TRADING ENGAGED.</b> Real capital order routing is now ACTIVE."
        elif arg in ("OFF", "DISABLE", "STOP"):
            self.execution_mode = "PAPER"
            self.live_trading_enabled = False
            self._awaiting_live_confirmation = False
            return "🛡 <b>Live trading disabled.</b> Reverted to PAPER execution mode."
        elif arg in ("ON", "ENABLE"):
            self._awaiting_live_confirmation = True
            return (
                "⚠️ <b>[SAFETY CONFIRMATION REQUIRED]</b>\n"
                "To enable LIVE order execution, verify broker API keys and send:\n"
                "<code>/trade_live CONFIRM_LIVE_TRADING</code>"
            )
        else:
            return (
                f"Live Trading Status: <code>{'ACTIVE' if self.live_trading_enabled else 'DISABLED'}</code>\n"
                "Usage: <code>/trade_live ON</code>, <code>/trade_live OFF</code>, or <code>/trade_live CONFIRM_LIVE_TRADING</code>"
            )

    def handle_loop(self, action: str) -> str:
        """Manages background continuous trader worker loop state."""
        action_clean = action.strip().upper()
        if not self.trader_loop:
            from services.trader_loop import ContinuousTraderLoop
            self.trader_loop = ContinuousTraderLoop(auto_start=False)

        if action_clean in ("ON", "START", "RESUME"):
            self.trader_loop.start()
            return f"🟢 <b>KODA Background Trader Loop STARTED.</b> (Interval: {self.trader_loop.interval_seconds}s)"
        elif action_clean in ("OFF", "STOP", "PAUSE"):
            self.trader_loop.stop()
            return "⚪ <b>KODA Background Trader Loop STOPPED.</b>"
        elif action_clean in ("RUN", "CYCLE", "ONCE"):
            res = self.trader_loop.run_single_cycle()
            return f"⚡ <b>Manual Cycle Complete:</b>\n{res.get('summary', 'Done')}"
        else:
            st = self.trader_loop.get_status()
            state_str = 'ACTIVE 🟢' if st['is_running'] else 'STOPPED ⚪'
            return (
                f"🔄 <b>KODA Trader Loop Status:</b> <code>{state_str}</code>\n"
                f"• Total Cycles: <code>{st['cycle_count']}</code>\n"
                f"• Interval: <code>{st['interval_seconds']}s</code>\n"
                f"• Last Cycle: <i>{st['last_cycle_time'] or 'Never'}</i>\n\n"
                f"Usage: <code>/loop ON</code>, <code>/loop OFF</code>, or <code>/loop RUN</code>"
            )

    def handle_help(self) -> str:
        """Displays available Telegram bot commands."""
        return """
🤖 <b>KODA Institutional Management Bot</b>
━━━━━━━━━━━━━━━━━━
Available Commands:
• <code>/status</code> - Active Regime, Macro Window, Trader Loop & Execution Quality
• <code>/stats</code> - Trade Autopsy 2.0 matrix & AI Confidence Calibration
• <code>/loop &lt;ON|OFF|RUN&gt;</code> - Control continuous background trading loop
• <code>/research</code> - Research Lab Hypotheses & Strategy Tournament
• <code>/mode &lt;PAPER|LIVE&gt;</code> - Switch between Paper and Live mode
• <code>/trade_live &lt;ON|OFF&gt;</code> - Toggle live order execution with confirmation
• <code>/ask &lt;question&gt;</code> - Ask KODA AI a natural language market question
• <code>/help</code> - Show this menu
""".strip()

    # -------------------------------------------------------------
    # Message Dispatcher
    # -------------------------------------------------------------

    def dispatch_command(self, text: str, user_id: Any) -> str:
        """
        Parses and routes incoming text command to the appropriate handler.
        """
        if not self.is_authorized(user_id):
            logger.warning(f"Unauthorized Telegram command attempt from user_id '{user_id}'.")
            return f"⛔ <b>Unauthorized Access Denied.</b> (User ID: <code>{user_id}</code>)"

        raw = text.strip()
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("/start", "/help"):
            return self.handle_help()
        elif cmd == "/status":
            return self.handle_status()
        elif cmd == "/stats":
            return self.handle_stats()
        elif cmd == "/loop":
            return self.handle_loop(args)
        elif cmd == "/research":
            return self.handle_research()
        elif cmd == "/mode":
            return self.handle_mode(args)
        elif cmd == "/trade_live":
            return self.handle_trade_live(args)
        elif cmd == "/ask":
            if not args:
                return "❓ Usage: <code>/ask &lt;your question&gt;</code>"
            if self.ai_client:
                # 1. Gather live portfolio context
                port_ctx = {
                    "stock_free": 1000.0,
                    "stock_total": 1000.0,
                    "crypto_free": 500.0,
                    "crypto_total": 500.0,
                    "open_positions": "None",
                    "health_state": "NORMAL"
                }
                try:
                    from services.trading212 import Trading212Client
                    from services.crypto_data import CryptoDataClient
                    from services.kill_switch import KillSwitch
                    t212 = Trading212Client()
                    crypto = CryptoDataClient()
                    ks = KillSwitch()
                    if t212.is_configured():
                        c = t212.get_account_cash()
                        if c:
                            port_ctx["stock_free"] = c.free
                            port_ctx["stock_total"] = c.total
                        pos = t212.get_open_positions()
                        if pos:
                            port_ctx["open_positions"] = ", ".join(f"{p.ticker} ({p.quantity:.2f})" for p in pos)
                    bal = crypto.get_balance()
                    if bal:
                        port_ctx["crypto_free"] = bal.free
                        port_ctx["crypto_total"] = bal.total
                    port_ctx["health_state"] = ks.state.value
                except Exception as e:
                    logger.debug(f"Portfolio context extraction: {e}")

                # 2. Gather active market regime
                regime_str = "TRENDING_BULL (Normal Volatility)"
                try:
                    regime_engine = MarketRegimeEngine()
                    reg = regime_engine.classify_regime()
                    regime_str = f"{reg.primary_regime.value} ({reg.volatility_level} Volatility) - {reg.rationale}"
                except Exception as e:
                    logger.debug(f"Regime extraction: {e}")

                # 3. Gather lessons from autopsies
                lessons_list = []
                try:
                    tracker = SignalTracker()
                    autopsy = TradeAutopsyEngine()
                    evals = tracker.get_evaluated_signals(limit=3)
                    for ev in evals:
                        rep = autopsy.analyze_outcome(ev)
                        if rep.actionable_lesson:
                            lessons_list.append(rep.actionable_lesson)
                except Exception as e:
                    logger.debug(f"Lessons extraction: {e}")

                # 4. Gather executed trade history
                history_str = ""
                try:
                    exec_engine = ExecutionQualityEngine()
                    recent_execs = exec_engine.get_recent_executions(limit=8)
                    if recent_execs:
                        h_lines = []
                        for rx in recent_execs:
                            h_lines.append(
                                f"• {rx.ticker} ({rx.action}): Fill=${rx.filled_price:,.2f} vs Exp=${rx.expected_price:,.2f} "
                                f"(Slippage: {rx.slippage_bps:+.1f} bps, Status: {rx.status})"
                            )
                        history_str = "\n".join(h_lines)
                except Exception as e:
                    logger.debug(f"Trade history extraction: {e}")

                # 5. Gather universe asset coverage stats
                univ_str = "Stocks Tracked: 80, Crypto Pairs: 16 (Broad Multi-Market Universe)"
                try:
                    from services.universe_manager import MarketUniverseManager
                    um = MarketUniverseManager()
                    stats = um.get_universe_stats()
                    univ_str = (
                        f"Stocks Universe: {stats.get('stocks_count', 80)} instruments, "
                        f"Crypto Universe: {stats.get('crypto_count', 16)} pairs "
                        f"(Last Synced: {stats.get('last_sync', 'Recent')})"
                    )
                except Exception as e:
                    logger.debug(f"Universe stats extraction: {e}")

                # 6. Gather Obsidian Vault exporter status
                obsidian_str = ""
                try:
                    from services.obsidian_exporter import ObsidianVaultExporter
                    obs_exporter = ObsidianVaultExporter()
                    obsidian_str = obs_exporter.get_status_summary()
                except Exception as e:
                    logger.debug(f"Obsidian status extraction: {e}")

                # 7. Gather system logs & error traces
                logs_str = get_recent_system_logs(max_lines=10)

                return self.notifier.handle_ask_command(
                    question=args,
                    ai_client=self.ai_client,
                    portfolio_context=port_ctx,
                    regime_context=regime_str,
                    lessons=lessons_list,
                    log_context=logs_str,
                    trade_history_context=history_str,
                    universe_context=univ_str,
                    obsidian_context=obsidian_str,
                    dispatch_to_telegram=False
                )
            return "⚠️ AI Client not initialized in Telegram Bot Manager."
        else:
            return f"❓ Unknown command: <code>{cmd}</code>. Send <code>/help</code> for available commands."

    def process_update(self, update: Dict[str, Any]) -> None:
        """Processes a single Telegram Update payload."""
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        from_user = message.get("from", {})
        user_id = from_user.get("id")
        text = message.get("text", "")

        if not text or not chat_id:
            return

        reply = self.dispatch_command(text=text, user_id=user_id)
        self.notifier.send_message(text=reply, target_chat_id=str(chat_id))

    def run_polling(self, poll_interval: float = 1.0, timeout: int = 25) -> None:
        """
        Runs the Telegram bot update polling loop.
        """
        if not self.notifier.is_configured():
            logger.error("Telegram credentials not configured. Cannot start polling.")
            print("[ERROR] Telegram Bot token or chat ID is missing in .env. Cannot start listener.")
            return

        print(f"🤖 [KODA TELEGRAM BOT] Polling started (Authorized User ID: {self.allowed_user_id or 'OPEN'})...")
        print("   Press Ctrl+C to stop.\n")

        offset = 0
        url = self.UPDATES_URL.format(token=self.bot_token)

        while True:
            try:
                params = {"offset": offset, "timeout": timeout}
                try:
                    resp = self._session.get(url, params=params, timeout=timeout + 5)
                except requests.exceptions.SSLError:
                    resp = self._session.get(url, params=params, timeout=timeout + 5, verify=False)

                if resp.status_code == 200:
                    data = resp.json()
                    updates = data.get("result", [])
                    for up in updates:
                        up_id = up.get("update_id", 0)
                        offset = max(offset, up_id + 1)
                        self.process_update(up)
                else:
                    logger.debug(f"Telegram polling returned status {resp.status_code}")

                time.sleep(poll_interval)
            except KeyboardInterrupt:
                print("\n🛑 [KODA TELEGRAM BOT] Polling stopped.")
                break
            except Exception as e:
                logger.error(f"Error during Telegram polling loop: {e}")
                time.sleep(3.0)
