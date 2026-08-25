"""
Continuous Background Trading Loop Service (KODA Institutional Architecture)
Runs periodically in the background (e.g. every 5–15 minutes) alongside Telegram Bot listener.
Evaluates market momentum and triggers Binance Futures Testnet trades with automated
Obsidian Vault Markdown logging and Git synchronization.
"""

import os
import time
import datetime
import logging
import threading
from typing import Optional, Dict, Any, List

from services.crypto_data import CryptoDataClient, DEFAULT_CRYPTO_UNIVERSE
from services.telegram_bot import TelegramNotifier
from services.ai_analyzer import GroqClient
from services.obsidian_exporter import ObsidianVaultExporter

logger = logging.getLogger(__name__)


class ContinuousTraderLoop:
    """
    Background trading worker loop for KODA Institutional OS.
    Executes automated crypto market evaluations and Binance Futures Testnet orders.
    """

    def __init__(
        self,
        interval_seconds: int = 300,
        crypto_client: Optional[CryptoDataClient] = None,
        notifier: Optional[TelegramNotifier] = None,
        ai_client: Optional[GroqClient] = None,
        target_symbols: Optional[List[str]] = None,
        min_ai_confidence: int = 70,
        auto_start: bool = False
    ):
        self.interval_seconds = max(10, interval_seconds)
        self.crypto_client = crypto_client or CryptoDataClient()
        self.notifier = notifier or TelegramNotifier()
        self.ai_client = ai_client or GroqClient()
        self.target_symbols = target_symbols or list(DEFAULT_CRYPTO_UNIVERSE)
        self.min_ai_confidence = min_ai_confidence
        self.exporter = ObsidianVaultExporter()

        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self.cycle_count = 0
        self.last_cycle_time: Optional[datetime.datetime] = None
        self.last_trade_executed: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None
        self.last_cycle_summary: str = "Initialized. No cycles executed yet."

        if auto_start:
            self.start()

    def start(self) -> None:
        """Starts the background trading loop thread."""
        if self.is_running:
            logger.info("ContinuousTraderLoop is already running.")
            return

        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="KODA-TraderLoop", daemon=True)
        self._thread.start()
        logger.info(f"Continuous background trader loop started (Interval: {self.interval_seconds}s, Assets: {len(self.target_symbols)}).")

    def stop(self) -> None:
        """Stops the background trading loop cleanly."""
        if not self.is_running:
            return

        logger.info("Stopping continuous background trader loop...")
        self.is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Continuous background trader loop stopped.")

    def _run_loop(self) -> None:
        """Internal daemon loop running single trading cycles periodically."""
        logger.info("Background trader loop thread active.")
        while self.is_running and not self._stop_event.is_set():
            try:
                self.run_single_cycle()
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Error in trader loop cycle #{self.cycle_count + 1}: {e}")

            # Sleep in 1-second chunks to allow prompt shutdown
            for _ in range(self.interval_seconds):
                if self._stop_event.is_set() or not self.is_running:
                    break
                time.sleep(1)

    def run_single_cycle(self) -> Dict[str, Any]:
        """
        Executes a single market scan across the expanded universe, evaluates momentum,
        filters via AI conviction gatekeeper, and executes qualified test futures orders.
        """
        self.cycle_count += 1
        now = datetime.datetime.now(datetime.timezone.utc)
        self.last_cycle_time = now
        logger.info(f"--- [KODA Loop Cycle #{self.cycle_count}] Scanning {len(self.target_symbols)} crypto assets at {now.strftime('%H:%M:%S UTC')} ---")

        evaluated_assets: List[Dict[str, Any]] = []
        trade_result: Optional[Dict[str, Any]] = None

        for symbol in self.target_symbols:
            try:
                # Rate limit pacing across large universe
                time.sleep(0.03)

                quote = self.crypto_client.get_quote(symbol)
                try:
                    sma20 = self.crypto_client.calculate_sma(symbol, period=20, timeframe="1d")
                except Exception:
                    sma20 = quote.previous_close

                diff_pct = ((quote.price - sma20) / sma20 * 100.0) if sma20 > 0 else 0.0
                evaluated_assets.append({
                    "symbol": symbol,
                    "price": quote.price,
                    "sma20": sma20,
                    "diff_pct": diff_pct,
                    "change_24h": quote.change_percent
                })

                # Momentum breakout / dip evaluation condition:
                # Trigger test futures order if price breaks above SMA by > 0.5% or dips by < -1.5%
                if trade_result is None and (diff_pct >= 0.5 or diff_pct <= -1.5):
                    action = "BUY" if diff_pct >= 0.5 else "SELL"
                    order_qty = 0.01 if "BTC" in symbol else (0.1 if "ETH" in symbol else 1.0)
                    reason = (
                        f"Trend Momentum Trigger: Price (${quote.price:,.2f}) vs 20-SMA (${sma20:,.2f}) "
                        f"Deviation {diff_pct:+.2f}%"
                    )

                    # 1. Generate thorough AI reasoning & reflection before execution
                    ai_result = None
                    if self.ai_client and self.ai_client.is_configured():
                        try:
                            ai_result = self.ai_client.analyze_trade_signal(
                                ticker=symbol,
                                price=quote.price,
                                action=action,
                                reason=reason,
                                indicators={
                                    "current_price": quote.price,
                                    "sma20": sma20,
                                    "deviation_pct": round(diff_pct, 2),
                                    "change_24h": quote.change_percent,
                                    "volume": quote.volume
                                }
                            )
                            logger.info(
                                f"AI Thesis Generated for {symbol} ({action}): "
                                f"{ai_result.sentiment} ({ai_result.confidence_score}%) - {ai_result.summary}"
                            )

                            # 2. AI Confidence & Sentiment Gatekeeper
                            # Filter out weak or conflicting setups below the confidence threshold
                            ai_agrees = (
                                (action == "BUY" and ai_result.sentiment in ("BULLISH", "NEUTRAL")) or
                                (action == "SELL" and ai_result.sentiment in ("BEARISH", "NEUTRAL"))
                            )
                            if not ai_agrees or ai_result.confidence_score < self.min_ai_confidence:
                                logger.info(
                                    f"🛡 [AI VETO] Setup for {symbol} ({action}) rejected by AI Gatekeeper: "
                                    f"Sentiment={ai_result.sentiment}, Confidence={ai_result.confidence_score}% (Min: {self.min_ai_confidence}%). "
                                    f"Thesis: {ai_result.summary}"
                                )
                                continue

                        except Exception as ai_err:
                            logger.warning(f"AI reasoning generation notice for {symbol}: {ai_err}")

                    # 3. Execute futures order on Binance Testnet with embedded AI thesis in Obsidian note
                    trade_result = self.crypto_client.create_order(
                        symbol=symbol,
                        side=action,
                        amount=order_qty,
                        price=quote.price,
                        strategy_reason=reason,
                        ai_analysis=ai_result,
                        export_to_obsidian=True
                    )
                    self.last_trade_executed = trade_result

                    # 4. Send rich Telegram Alert with AI Reasoning if configured
                    if self.notifier.is_configured():
                        ai_section = ""
                        if ai_result:
                            ai_section = (
                                f"\n🧠 <b>AI Thesis:</b> <code>{ai_result.sentiment}</code> (Confidence: <code>{ai_result.confidence_score}%</code>)\n"
                                f"• <i>{ai_result.summary}</i>\n"
                                f"• <b>Catalysts:</b> <i>{ai_result.catalysts}</i>\n"
                            )

                        msg = (
                            f"⚡ <b>KODA Automated Testnet Trade</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"• <b>Symbol:</b> <code>{symbol}</code> ({action})\n"
                            f"• <b>Fill Price:</b> <code>${trade_result.get('price', quote.price):,.2f}</code>\n"
                            f"• <b>Quantity:</b> <code>{order_qty}</code>\n"
                            f"• <b>Strategy:</b> <i>{reason}</i>\n"
                            f"• <b>Status:</b> <code>{trade_result.get('status', 'FILLED')}</code> ({trade_result.get('environment', 'testnet')})"
                            f"{ai_section}\n"
                            f"📓 <i>Note exported to Obsidian Vault and Git synced.</i>"
                        )
                        self.notifier.send_message(msg)

            except Exception as item_err:
                logger.warning(f"Error evaluating crypto asset '{symbol}': {item_err}")

        summary = (
            f"Cycle #{self.cycle_count} completed at {now.strftime('%Y-%m-%d %H:%M:%S UTC')}. "
            f"Evaluated {len(evaluated_assets)} assets. "
            f"Trade Executed: {trade_result['symbol'] + ' ' + trade_result['action'] if trade_result else 'None (Market Filtered)'}"
        )
        self.last_cycle_summary = summary
        logger.info(summary)

        return {
            "cycle": self.cycle_count,
            "timestamp": now.isoformat(),
            "evaluated_assets": evaluated_assets,
            "trade": trade_result,
            "summary": summary
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns structured health and operational status of the loop."""
        return {
            "is_running": self.is_running,
            "cycle_count": self.cycle_count,
            "interval_seconds": self.interval_seconds,
            "last_cycle_time": self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            "last_trade": self.last_trade_executed,
            "last_error": self.last_error,
            "summary": self.last_cycle_summary,
            "target_symbols": self.target_symbols,
        }
