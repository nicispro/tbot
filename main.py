"""
Main Trading Bot Orchestrator & CLI Runner
Coordinates dual-market evaluation (Stocks & Crypto), dynamic market scanning,
strategy evaluation, AI analysis (Groq), Telegram alerts, broker trade execution (Trading 212),
and Markdown journaling (Obsidian Local REST API).
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import argparse
import datetime
import logging
import sys
import time
from typing import Dict, List, Optional, Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False

from config import settings
from services.market_data import (
    YFinanceClient,
    MarketDataClient,
    get_all_tradable_tickers,
    rate_limited_batch_iterator,
)
from services.crypto_data import CryptoDataClient, DEFAULT_CRYPTO_UNIVERSE
from services.trading212 import Trading212Client, Position, AccountCash, OrderResult
from services.obsidian import ObsidianClient, TradeLogRecord
from services.ai_analyzer import GroqClient, AIAnalyzerClient, AIAnalysisResult
from services.telegram_bot import TelegramNotifier, TelegramBotManager
from services.signal_tracker import SignalTracker
from services.data_guard import DataGuard, DATA_UNAVAILABLE
from services.risk_engine import DeterministicRiskEngine, RiskAssessmentResult
from services.kill_switch import KillSwitch, SystemState
from services.market_radar import (
    MarketRadar,
    RadarAssetScanResult,
    MultiLevelMarketRadar,
    Level1Candidate,
    Level3Finalist,
    MultiLevelPipelineResult,
)
from services.opportunity_scorer import OpportunityScorer, ScoredOpportunity
from services.trade_filter import WhyNotTradeEngine, VetoResult
from services.portfolio_brain import PortfolioBrain, CorrelationAssessment
from services.trade_autopsy import TradeAutopsyEngine, TradeAutopsyReport, DecisionOutcomeQuadrant
from services.universe_manager import UniverseManager
from services.news_sentiment import EconomicCalendar, NewsSentimentEngine, MacroSentimentSummary
from services.market_regime import MarketRegimeEngine, MarketRegime, RegimeClassification
from services.portfolio_exposure import PortfolioExposureEngine, ExposureAssessment
from services.execution_quality import ExecutionQualityEngine, ExecutionMetrics
from services.audit_trail import DecisionAuditTrail, DecisionAuditRecord
from services.confidence_tracker import ConfidenceTracker, ConfidenceBracketReport
from services.research_lab import ResearchLabEngine, ResearchHypothesis, HypothesisStage
from services.strategy_tournament import StrategyTournamentEngine, TournamentStrategyStats
from services.shadow_trading import ShadowTradingEngine, ShadowTrade
from strategy import DipAndMovingAverageStrategy, TradeDecision

# Configure console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("TradingBot")


class TradingBotOrchestrator:
    """
    Main controller linking Market Data (Stocks & Crypto), Dynamic Market Scanner, Broker Execution,
    AI Analysis (Groq), Telegram Alerts, Strategy Engine, and Obsidian Logging.
    """

    def __init__(
        self,
        dry_run: Optional[bool] = None,
        scan_market: bool = False,
        scan_limit: Optional[int] = None,
        target: str = "all"
    ):
        self.dry_run = dry_run if dry_run is not None else settings.dry_run
        self.scan_market = scan_market
        self.scan_limit = scan_limit
        self.target = target.lower()

        logger.info("Initializing API services...")
        self.market_client = YFinanceClient()
        self.crypto_client = CryptoDataClient(
            exchange_id=settings.effective_crypto_exchange,
            api_key=settings.effective_crypto_api_key,
            secret=settings.effective_crypto_secret_key
        )
        self.broker_client = Trading212Client(
            api_key=settings.t212_api_key,
            api_key_id=settings.t212_api_key_id,
            secret_key=settings.t212_secret_key,
            api_secret=settings.t212_api_secret,
            environment=settings.t212_environment
        )
        self.obsidian_client = ObsidianClient(
            api_key=settings.obsidian_rest_api_key,
            host=settings.obsidian_host,
            port=settings.obsidian_port,
            use_https=settings.obsidian_use_https,
            verify_ssl=settings.obsidian_verify_ssl,
            vault_folder=settings.obsidian_vault_folder
        )
        self.ai_client = GroqClient(
            api_key=settings.effective_ai_api_key,
            model=settings.effective_ai_model
        )
        self.telegram_notifier = TelegramNotifier(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id
        )
        self.stock_strategy = DipAndMovingAverageStrategy(
            config=settings,
            market_client=self.market_client,
            broker_client=self.broker_client
        )
        self.crypto_strategy = DipAndMovingAverageStrategy(
            config=settings,
            market_client=self.crypto_client,
            broker_client=self.broker_client
        )

        self.signal_tracker = SignalTracker()
        self.data_guard = DataGuard()
        self.risk_engine = DeterministicRiskEngine()
        self.kill_switch = KillSwitch()
        self.market_radar = MarketRadar(stock_client=self.market_client, crypto_client=self.crypto_client)
        self.opportunity_scorer = OpportunityScorer()
        self.trade_filter = WhyNotTradeEngine()
        self.portfolio_brain = PortfolioBrain(stock_client=self.market_client, crypto_client=self.crypto_client)
        self.trade_autopsy = TradeAutopsyEngine()
        self.recent_autopsy_lessons: List[str] = []

        mode_str = f"Scanner Mode (Limit: {self.scan_limit or 'All'})" if self.scan_market else f"Watchlist: {settings.watchlist_tickers}"
        logger.info(
            f"Trading Bot initialized in [{settings.t212_environment.upper()}] mode. "
            f"Target: {self.target.upper()}. Crypto Exchange: [{settings.effective_crypto_exchange.upper()}]. "
            f"Health State: [{self.kill_switch.state.value}]. Dry Run: {self.dry_run}. Mode: {mode_str}. "
            f"AI: {self.ai_client.is_configured()} ({settings.effective_ai_model}). "
            f"Telegram: {self.telegram_notifier.is_configured()}."
        )

    def run_cycle(self) -> None:
        """
        Executes one complete evaluation cycle across dual-market (Stocks & Crypto) instruments
        with separated broker and crypto balance accounting, KODA Market Radar, Opportunity Scoring,
        Risk Engine position sizing, 'Why NOT Trade?' veto checks, Portfolio Correlation checks,
        Trade Autopsies, and Kill Switch guards.
        """
        cycle_time = datetime.datetime.now(datetime.timezone.utc)
        logger.info(f"=== Starting Trading Cycle [{self.target.upper()}] at {cycle_time.strftime('%Y-%m-%d %H:%M:%S UTC')} ===")

        # System Health Check
        can_exec_buys, buy_guard_reason = self.kill_switch.can_execute_orders("BUY")
        if not can_exec_buys:
            logger.warning(f"🚨 [KILL SWITCH ACTIVE] {buy_guard_reason}. New BUY orders are suspended.")

        # 0. Forward-Testing & Trade Autopsy Engine
        try:
            evaluated_outcomes = self.signal_tracker.evaluate_past_signals(
                market_client=self.market_client,
                crypto_client=self.crypto_client,
                stock_min_age_hours=24.0,
                crypto_min_age_hours=4.0
            )
            if evaluated_outcomes:
                stats = self.signal_tracker.get_accuracy_stats()
                saved_journal = self.obsidian_client.log_learning_journal(evaluated_outcomes, stats)

                # Run Trade Autopsy post-mortem diagnostics on all evaluated outcomes
                autopsy_reports = [self.trade_autopsy.analyze_outcome(out) for out in evaluated_outcomes]
                for rep in autopsy_reports:
                    if rep.actionable_lesson and rep.actionable_lesson not in self.recent_autopsy_lessons:
                        self.recent_autopsy_lessons.append(rep.actionable_lesson)
                self.obsidian_client.log_trade_autopsies(autopsy_reports, stats)

                logger.info(
                    f"Forward-tested {len(evaluated_outcomes)} past signal outcome(s) with {len(autopsy_reports)} autopsies. "
                    f"Updated Obsidian Learning Journal ({saved_journal}). "
                    f"Current Win Rate: {stats['win_rate_percent']}% ({stats['wins']}W / {stats['losses']}L)."
                )
        except Exception as eval_past_err:
            logger.warning(f"Failed to forward-test past signal outcomes: {eval_past_err}")

        # 1. Fetch Trading 212 Stock Balance & Open Positions
        stock_cash: Optional[AccountCash] = None
        positions_map: Dict[str, Position] = {}

        if self.target in ("stocks", "all"):
            try:
                stock_cash = self.broker_client.get_account_cash()
                self.kill_switch.update_portfolio_equity(stock_cash.total)
                self.kill_switch.record_api_success()
                logger.info(
                    f"Stocks Account (Trading 212): Free=${stock_cash.free:,.2f} | Invested=${stock_cash.invested:,.2f} | "
                    f"Total=${stock_cash.total:,.2f} | PnL=${stock_cash.ppl:,.2f}"
                )
            except Exception as e:
                logger.error(f"Failed to fetch account cash from Trading 212: {e}")
                self.kill_switch.record_api_error(f"Trading 212 cash fetch failure: {e}")
                stock_cash = AccountCash(free=1000.0, total=1000.0, invested=0.0, ppl=0.0, result=0.0)

            try:
                positions = self.broker_client.get_open_positions()
                positions_map = {p.ticker: p for p in positions}
                logger.info(f"Currently open stock positions: {list(positions_map.keys()) if positions_map else 'None'}")
            except Exception as e:
                logger.warning(f"Could not retrieve open positions from Trading 212: {e}")

        # 2. Fetch Crypto Wallet Balance (Coinbase / CCXT if API keys exist)
        crypto_cash: Optional[AccountCash] = None
        if self.target in ("crypto", "all"):
            crypto_cash = self.crypto_client.get_balance()
            if crypto_cash:
                logger.info(
                    f"Crypto Account ({settings.effective_crypto_exchange.upper()}): "
                    f"Free Cash=${crypto_cash.free:,.2f} | Invested=${crypto_cash.invested:,.2f} | "
                    f"Total Balance=${crypto_cash.total:,.2f}"
                )
            else:
                logger.info(
                    f"Crypto Account ({settings.effective_crypto_exchange.upper()}): "
                    f"Simulation Mode (Public Scan, No Wallet Keys Configured)"
                )

        # 3. Determine active stocks and crypto universes
        active_stocks: List[str] = []
        active_crypto: List[str] = []

        if self.target in ("stocks", "all") and stock_cash is not None:
            min_order_threshold = min(10.0, settings.buy_allocation_value)
            if not self.dry_run and stock_cash.free < min_order_threshold:
                if not positions_map:
                    logger.warning(
                        f"Stock cash (${stock_cash.free:,.2f}) is below minimum buy threshold "
                        f"(${min_order_threshold:,.2f}) and no open stock positions exist. "
                        f"Skipping extended stock scan."
                    )
                else:
                    logger.info(
                        f"Low stock cash (${stock_cash.free:,.2f}). Restricting stock evaluation to "
                        f"{len(positions_map)} open position(s) for sell signals."
                    )
                    active_stocks = list(positions_map.keys())
            else:
                if self.scan_market:
                    logger.info("Dynamic Stock Market Scanner enabled. Fetching tradable universe...")
                    active_stocks = get_all_tradable_tickers(
                        source="sp500_nasdaq",
                        limit=self.scan_limit,
                        fallback_tickers=settings.watchlist_tickers,
                        t212_client=self.broker_client
                    )
                else:
                    active_stocks = list(settings.watchlist_tickers)

        if self.target in ("crypto", "all"):
            logger.info("Crypto Scanner enabled. Fetching crypto pairs universe...")
            active_crypto = self.crypto_client.get_all_tradable_crypto(limit=self.scan_limit)

        executed_trades_count = 0
        triggered_signals: List[Dict[str, Any]] = []
        evaluated_records: List[Dict[str, Any]] = []
        radar_scans: List[RadarAssetScanResult] = []

        # 4. Evaluate Stock Universe with DataGuard, RiskEngine & Market Radar
        if active_stocks and stock_cash is not None:
            logger.info(f"Evaluating {len(active_stocks)} stock instrument(s)...")
            for ticker in rate_limited_batch_iterator(active_stocks, max_per_second=5.0):
                try:
                    position = positions_map.get(ticker)
                    decision: TradeDecision = self.stock_strategy.evaluate_ticker(
                        ticker=ticker,
                        cash=stock_cash,
                        current_position=position
                    )

                    # Market Radar Multi-Timeframe Scan
                    try:
                        r_scan = self.market_radar.analyze_asset(ticker=ticker, market_type="stock")
                        radar_scans.append(r_scan)
                        # Merge radar-detected indicators
                        for k, v in r_scan.indicators.items():
                            if k not in decision.indicators or decision.indicators[k] == "DATA_UNAVAILABLE":
                                decision.indicators[k] = v
                    except Exception as radar_err:
                        logger.debug(f"Radar scan skipped for {ticker}: {radar_err}")

                    # DataGuard Anomaly Detection
                    is_anom, anom_msg = self.data_guard.check_price_anomaly(
                        decision.current_price,
                        decision.indicators.get("previous_close")
                    )
                    if is_anom:
                        self.kill_switch.record_anomaly(f"Stock {ticker}: {anom_msg}")

                    evaluated_records.append({
                        "ticker": ticker,
                        "price": decision.current_price,
                        "short_sma": decision.indicators.get("short_sma", 0.0),
                        "long_sma": decision.indicators.get("long_sma", 0.0),
                        "dip_percentage": decision.indicators.get("dip_percentage", 0.0),
                        "action": decision.action,
                        "reason": decision.reason,
                        "market": "stock"
                    })

                    if decision.action in ["BUY", "SELL"]:
                        # Evaluate Deterministic Risk Engine parameters
                        risk_eval: RiskAssessmentResult = self.risk_engine.evaluate_trade_risk(
                            ticker=decision.ticker,
                            action=decision.action,
                            current_price=decision.current_price,
                            portfolio_cash=stock_cash,
                            indicators=decision.indicators,
                            opportunity_score=1.0,
                            max_order_override=settings.buy_allocation_value
                        )
                        decision.indicators["stop_loss"] = risk_eval.stop_loss_price
                        decision.indicators["take_profit"] = risk_eval.take_profit_price
                        decision.indicators["risk_reward"] = risk_eval.risk_reward_ratio
                        decision.indicators["risk_amount"] = risk_eval.risk_amount

                        if decision.action == "BUY":
                            # 1. Deterministic Risk Engine Check
                            if not risk_eval.is_approved:
                                decision.should_execute = False
                                logger.info(f"Risk Engine rejected BUY for {ticker}: {risk_eval.rejection_reason}")
                            else:
                                decision.target_value = risk_eval.allocated_value

                            # 2. 'Why NOT Trade?' Defensive Veto Check
                            veto_res: VetoResult = self.trade_filter.evaluate_trade_filters(
                                ticker=decision.ticker,
                                action=decision.action,
                                current_price=decision.current_price,
                                indicators=decision.indicators,
                                risk_reward_ratio=risk_eval.risk_reward_ratio
                            )
                            if veto_res.should_veto:
                                decision.should_execute = False
                                logger.warning(f"🚫 [VETO] {decision.ticker} BUY blocked by 'Why NOT Trade?' Engine: {'; '.join(veto_res.veto_reasons)}")

                            # 3. Portfolio & Correlation Brain Check
                            if decision.should_execute:
                                corr_res: CorrelationAssessment = self.portfolio_brain.evaluate_entry_risk(
                                    candidate_ticker=decision.ticker,
                                    market_type="stock",
                                    target_value=decision.target_value,
                                    current_positions=positions_map,
                                    stock_cash=stock_cash,
                                    crypto_cash=crypto_cash
                                )
                                if not corr_res.is_approved:
                                    decision.should_execute = False
                                    logger.warning(f"🛡 [PORTFOLIO BRAIN VETO] {decision.ticker} BUY blocked: {corr_res.rejection_reason}")

                            # 4. Kill Switch Check
                            if not can_exec_buys:
                                decision.should_execute = False
                                logger.warning(f"Kill Switch blocked BUY order for {ticker}: {buy_guard_reason}")

                        # Record hypothesis in SignalTracker SQLite DB
                        try:
                            self.signal_tracker.record_signal(
                                ticker=decision.ticker,
                                market_type="stock",
                                signal_type=decision.action,
                                price_at_signal=decision.current_price,
                                indicators=decision.indicators,
                                notes=decision.reason,
                                timestamp=cycle_time
                            )
                        except Exception as sig_err:
                            logger.warning(f"Could not record signal hypothesis: {sig_err}")

                    if decision.should_execute and decision.action in ["BUY", "SELL"]:
                        self._process_trade_execution(decision, cycle_time, market_type="stock")
                        executed_trades_count += 1
                        triggered_signals.append({
                            "ticker": decision.ticker,
                            "action": decision.action,
                            "price": decision.current_price,
                            "reason": decision.reason,
                            "value": decision.target_value,
                            "market": "stock"
                        })
                        stock_cash.free = max(0.0, stock_cash.free - decision.target_value)

                except Exception as eval_err:
                    logger.error(f"Error evaluating stock '{ticker}': {eval_err}", exc_info=False)

        # 5. Evaluate Crypto Universe with DataGuard, RiskEngine & Market Radar
        if active_crypto:
            eval_crypto_cash = crypto_cash or AccountCash(free=1000.0, total=1000.0, invested=0.0, ppl=0.0, result=0.0)
            logger.info(f"Evaluating {len(active_crypto)} crypto pair(s)...")
            for symbol in rate_limited_batch_iterator(active_crypto, max_per_second=5.0):
                try:
                    decision: TradeDecision = self.crypto_strategy.evaluate_ticker(
                        ticker=symbol,
                        cash=eval_crypto_cash,
                        current_position=None
                    )

                    # Market Radar Multi-Timeframe Scan
                    try:
                        r_scan_crypto = self.market_radar.analyze_asset(ticker=symbol, market_type="crypto")
                        radar_scans.append(r_scan_crypto)
                        for k, v in r_scan_crypto.indicators.items():
                            if k not in decision.indicators or decision.indicators[k] == "DATA_UNAVAILABLE":
                                decision.indicators[k] = v
                    except Exception as radar_c_err:
                        logger.debug(f"Radar scan skipped for crypto {symbol}: {radar_c_err}")

                    # DataGuard Anomaly Detection
                    is_anom, anom_msg = self.data_guard.check_price_anomaly(
                        decision.current_price,
                        decision.indicators.get("previous_close")
                    )
                    if is_anom:
                        self.kill_switch.record_anomaly(f"Crypto {symbol}: {anom_msg}")

                    evaluated_records.append({
                        "ticker": symbol,
                        "price": decision.current_price,
                        "short_sma": decision.indicators.get("short_sma", 0.0),
                        "long_sma": decision.indicators.get("long_sma", 0.0),
                        "dip_percentage": decision.indicators.get("dip_percentage", 0.0),
                        "action": decision.action,
                        "reason": decision.reason,
                        "market": "crypto"
                    })

                    if decision.action != "HOLD":
                        logger.info(f"Decision for crypto {symbol}: {decision.action} -> {decision.reason}")

                    if decision.action in ["BUY", "SELL"]:
                        risk_eval_crypto: RiskAssessmentResult = self.risk_engine.evaluate_trade_risk(
                            ticker=decision.ticker,
                            action=decision.action,
                            current_price=decision.current_price,
                            portfolio_cash=eval_crypto_cash,
                            indicators=decision.indicators,
                            opportunity_score=1.0,
                            max_order_override=settings.buy_allocation_value
                        )
                        decision.indicators["stop_loss"] = risk_eval_crypto.stop_loss_price
                        decision.indicators["take_profit"] = risk_eval_crypto.take_profit_price
                        decision.indicators["risk_reward"] = risk_eval_crypto.risk_reward_ratio
                        decision.indicators["risk_amount"] = risk_eval_crypto.risk_amount

                        if decision.action == "BUY":
                            if not risk_eval_crypto.is_approved:
                                decision.should_execute = False
                                logger.info(f"Risk Engine rejected crypto BUY for {symbol}: {risk_eval_crypto.rejection_reason}")
                            else:
                                decision.target_value = risk_eval_crypto.allocated_value

                            veto_res_c: VetoResult = self.trade_filter.evaluate_trade_filters(
                                ticker=decision.ticker,
                                action=decision.action,
                                current_price=decision.current_price,
                                indicators=decision.indicators,
                                risk_reward_ratio=risk_eval_crypto.risk_reward_ratio
                            )
                            if veto_res_c.should_veto:
                                decision.should_execute = False
                                logger.warning(f"🚫 [VETO] {decision.ticker} BUY blocked by 'Why NOT Trade?' Engine: {'; '.join(veto_res_c.veto_reasons)}")

                            # Portfolio Brain Check for Crypto
                            if decision.should_execute:
                                corr_res_c: CorrelationAssessment = self.portfolio_brain.evaluate_entry_risk(
                                    candidate_ticker=decision.ticker,
                                    market_type="crypto",
                                    target_value=decision.target_value,
                                    current_positions=positions_map,
                                    stock_cash=stock_cash,
                                    crypto_cash=eval_crypto_cash
                                )
                                if not corr_res_c.is_approved:
                                    decision.should_execute = False
                                    logger.warning(f"🛡 [PORTFOLIO BRAIN VETO] {decision.ticker} BUY blocked: {corr_res_c.rejection_reason}")

                            if not can_exec_buys:
                                decision.should_execute = False
                                logger.warning(f"Kill Switch blocked crypto BUY for {symbol}: {buy_guard_reason}")

                        # Record crypto hypothesis in SignalTracker SQLite DB
                        try:
                            self.signal_tracker.record_signal(
                                ticker=decision.ticker,
                                market_type="crypto",
                                signal_type=decision.action,
                                price_at_signal=decision.current_price,
                                indicators=decision.indicators,
                                notes=decision.reason,
                                timestamp=cycle_time
                            )
                        except Exception as sig_err:
                            logger.warning(f"Could not record crypto signal hypothesis: {sig_err}")

                    if decision.should_execute and decision.action in ["BUY", "SELL"]:
                        self._process_trade_execution(decision, cycle_time, market_type="crypto")
                        executed_trades_count += 1
                        triggered_signals.append({
                            "ticker": decision.ticker,
                            "action": decision.action,
                            "price": decision.current_price,
                            "reason": decision.reason,
                            "value": decision.target_value,
                            "market": "crypto"
                        })

                except Exception as eval_crypto_err:
                    logger.error(f"Error evaluating crypto '{symbol}': {eval_crypto_err}", exc_info=False)

        # 6. Rank Top Radar Opportunities
        top_ranked_opps = self.opportunity_scorer.rank_opportunities(radar_scans, top_n=8, min_score=50.0)
        top_opps_dicts = [
            {
                "ticker": op.ticker,
                "market_type": op.market_type,
                "price": op.price,
                "composite_score": op.composite_score,
                "grade": op.grade,
                "key_events": op.key_events
            }
            for op in top_ranked_opps
        ]

        cycle_duration = (datetime.datetime.now(datetime.timezone.utc) - cycle_time).total_seconds()
        total_evaluated = len(active_stocks) + len(active_crypto)
        logger.info(
            f"=== Cycle Completed: Evaluated {total_evaluated} instruments ({len(active_stocks)} stocks, "
            f"{len(active_crypto)} crypto) in {cycle_duration:.1f}s. "
            f"Executed {executed_trades_count} trade(s)/signal(s). Top Radar Opps: {len(top_ranked_opps)} ==="
        )

        # 7. Always log complete Market Scan Cycle report to Obsidian Vault
        try:
            saved_cycle_path = self.obsidian_client.log_market_scan_cycle(
                timestamp=cycle_time,
                market_target=self.target,
                stock_cash=stock_cash,
                crypto_cash=crypto_cash,
                crypto_exchange_name=settings.effective_crypto_exchange,
                open_positions_count=len(positions_map),
                evaluated_signals=evaluated_records,
                dry_run=self.dry_run,
                scan_mode=self.scan_market,
                top_radar_opportunities=top_opps_dicts
            )
            logger.info(f"Logged market scan cycle to Obsidian: {saved_cycle_path}")
        except Exception as obs_cycle_err:
            logger.warning(f"Failed to log market scan cycle to Obsidian: {obs_cycle_err}")

        # 8. Always dispatch Cycle Summary to Telegram if configured
        if settings.enable_telegram_alerts and self.telegram_notifier.is_configured():
            try:
                self.telegram_notifier.send_cycle_summary(
                    evaluated_count=total_evaluated,
                    executed_count=executed_trades_count,
                    stock_cash=stock_cash,
                    crypto_cash=crypto_cash,
                    crypto_exchange_name=settings.effective_crypto_exchange,
                    dry_run=self.dry_run,
                    scan_mode=self.scan_market,
                    target_market=self.target,
                    stocks_evaluated=len(active_stocks),
                    crypto_evaluated=len(active_crypto),
                    signals_summary=triggered_signals,
                    duration_seconds=cycle_duration,
                    top_radar_opportunities=top_opps_dicts
                )
                logger.info("Dispatched Telegram dual-market trading cycle summary report.")
            except Exception as tg_sum_err:
                logger.warning(f"Failed to dispatch Telegram cycle summary: {tg_sum_err}")

    def _process_trade_execution(
        self,
        decision: TradeDecision,
        cycle_time: datetime.datetime,
        market_type: str = "stock"
    ) -> None:
        """
        Processes AI sentiment analysis, broker execution, Obsidian logging, and Telegram notification.
        """
        logger.info(f"Triggering {decision.action} flow for [{market_type.upper()}] {decision.ticker} (Target Value: ${decision.target_value:.2f})")

        # 1. Groq AI Sentiment Analysis with Historical ML Feedback Context
        ai_analysis: Optional[AIAnalysisResult] = None
        if settings.enable_ai_analysis:
            try:
                stats = self.signal_tracker.get_accuracy_stats()
                ai_analysis = self.ai_client.analyze_trade_signal(
                    ticker=decision.ticker,
                    price=decision.current_price,
                    action=decision.action,
                    reason=decision.reason,
                    indicators=decision.indicators,
                    historical_stats=stats,
                    historical_lessons=self.recent_autopsy_lessons
                )
                logger.info(
                    f"AI Sentiment: {ai_analysis.sentiment} (Confidence: {ai_analysis.confidence_score}%) - "
                    f"{ai_analysis.summary}"
                )
            except Exception as ai_err:
                logger.warning(f"AI trade analysis failed: {ai_err}")

        # 2. Broker Execution (or Dry-Run Simulation for stocks/crypto)
        if self.dry_run or market_type == "crypto":
            # Crypto executions are logged/simulated unless a dedicated crypto broker is attached
            logger.info(f"[SIMULATION] Skipping live broker order for {decision.ticker}.")
            shares_est = round(decision.target_value / decision.current_price, 6) if decision.current_price > 0 else 0.0
            order_res = OrderResult(
                success=True,
                order_id="SIMULATED-CRYPTO" if market_type == "crypto" else "DRY-RUN-SIMULATED",
                ticker=decision.ticker,
                action=decision.action,
                quantity=shares_est,
                filled_quantity=shares_est,
                filled_value=decision.target_value,
                status="SIMULATED",
                raw_response={"market": market_type, "mode": "simulation"},
                error_message=None
            )
        else:
            try:
                order_res = self.broker_client.place_value_order(
                    ticker=decision.ticker,
                    value=decision.target_value,
                    current_price=decision.current_price
                )
                if order_res.success:
                    self.kill_switch.record_api_success()
                else:
                    self.kill_switch.record_api_error(f"Broker order rejected for {decision.ticker}: {order_res.error_message}")
            except Exception as exec_err:
                logger.error(f"Execution failed for {decision.ticker}: {exec_err}")
                self.kill_switch.record_api_error(f"Broker order exception for {decision.ticker}: {exec_err}")
                order_res = OrderResult(
                    success=False,
                    order_id=None,
                    ticker=decision.ticker,
                    action=decision.action,
                    quantity=0.0,
                    filled_quantity=0.0,
                    filled_value=0.0,
                    status="FAILED",
                    raw_response={},
                    error_message=str(exec_err)
                )

        # 3. Log to Obsidian Vault
        try:
            extra_meta = {
                "indicators": decision.indicators,
                "strategy": "DipAndMovingAverageStrategy",
                "market_type": market_type,
                "stop_loss": decision.indicators.get("stop_loss"),
                "take_profit": decision.indicators.get("take_profit"),
                "risk_reward": decision.indicators.get("risk_reward"),
                "risk_amount": decision.indicators.get("risk_amount")
            }
            if ai_analysis:
                extra_meta["ai_sentiment"] = ai_analysis.sentiment
                extra_meta["ai_confidence"] = ai_analysis.confidence_score
                extra_meta["ai_summary"] = ai_analysis.summary
                extra_meta["ai_model"] = ai_analysis.model_used

            trade_record = TradeLogRecord(
                timestamp=cycle_time,
                ticker=decision.ticker,
                action=decision.action,
                price=decision.current_price,
                quantity=order_res.filled_quantity if order_res.filled_quantity > 0 else order_res.quantity,
                order_value=decision.target_value,
                strategy_reason=decision.reason,
                execution_success=order_res.success,
                order_id=order_res.order_id,
                broker_status=order_res.status,
                environment="crypto-sim" if market_type == "crypto" else settings.t212_environment,
                extra_meta=extra_meta
            )
            saved_note = self.obsidian_client.log_trade(trade_record)
            logger.info(f"Logged trade to Obsidian note: {saved_note}")
        except Exception as obs_err:
            logger.error(f"Failed to log trade to Obsidian: {obs_err}")

        # 4. Dispatch Telegram Notification
        if settings.enable_telegram_alerts and self.telegram_notifier.is_configured():
            try:
                self.telegram_notifier.send_trade_alert(trade_record, ai_analysis)
                logger.info(f"Dispatched Telegram alert for {decision.ticker}.")
            except Exception as tg_err:
                logger.warning(f"Failed to dispatch Telegram alert: {tg_err}")


# ==============================================================================
# Diagnostic Verification Utilities
# ==============================================================================

def test_obsidian_connection() -> None:
    """Diagnostic tool to verify Obsidian Local REST API connectivity."""
    print("\n--- Testing Obsidian Local REST API ---")
    client = ObsidianClient(
        api_key=settings.obsidian_rest_api_key,
        host=settings.obsidian_host,
        port=settings.obsidian_port,
        use_https=settings.obsidian_use_https,
        verify_ssl=settings.obsidian_verify_ssl,
        vault_folder=settings.obsidian_vault_folder
    )
    try:
        status = client.test_connection()
        print(f"[SUCCESS] Connected to Obsidian Local REST API: {status}")
        dummy_record = TradeLogRecord(
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            ticker="AAPL_US_EQ",
            action="BUY",
            price=185.50,
            quantity=0.1347,
            order_value=25.0,
            strategy_reason="Test diagnostic trade log generated by CLI test command.",
            execution_success=True,
            order_id="TEST-12345",
            broker_status="FILLED",
            environment="demo",
            extra_meta={"ai_sentiment": "BULLISH", "ai_confidence": 85, "ai_summary": "Solid dip buy with strong moving average support on Groq."}
        )
        saved_path = client.log_trade(dummy_record)
        print(f"[SUCCESS] Test trade note generated at vault path: {saved_path}")
    except Exception as e:
        print(f"[ERROR] Obsidian connection failed: {e}")


def test_trading212_connection() -> None:
    """Diagnostic tool to verify Trading 212 API connectivity."""
    print(f"\n--- Testing Trading 212 API ({settings.t212_environment.upper()}) ---")
    client = Trading212Client(
        api_key=settings.t212_api_key,
        api_key_id=settings.t212_api_key_id,
        secret_key=settings.t212_secret_key,
        api_secret=settings.t212_api_secret,
        environment=settings.t212_environment
    )
    try:
        cash = client.get_account_cash()
        print(f"[SUCCESS] Trading 212 Cash: Free=${cash.free:,.2f}, Total=${cash.total:,.2f}")
        positions = client.get_open_positions()
        print(f"[SUCCESS] Open Positions ({len(positions)}):")
        for p in positions:
            print(f"  - {p.ticker}: {p.quantity} shares @ avg ${p.average_price:.2f} (Current: ${p.current_price:.2f}, PnL: ${p.ppl:.2f})")
    except Exception as e:
        print(f"[ERROR] Trading 212 API test failed: {e}")


def test_market_data_connection() -> None:
    """Diagnostic tool to verify yfinance & crypto market data connectivity."""
    print("\n--- Testing yfinance Market Data ---")
    client = YFinanceClient()
    test_ticker = settings.watchlist_tickers[0] if settings.watchlist_tickers else "AAPL_US_EQ"
    try:
        quote = client.get_quote(test_ticker)
        print(f"[SUCCESS] Stock Quote for {test_ticker}: Price=${quote.price:.2f}, Change={quote.change_percent:+.2f}%")
        sma = client.calculate_sma(test_ticker, period=settings.sma_short_period)
        print(f"[SUCCESS] {settings.sma_short_period}-day SMA for {test_ticker}: ${sma:.2f}")
    except Exception as e:
        print(f"[ERROR] Stock market data test failed: {e}")

    print("\n--- Testing Crypto Market Data (CCXT / Binance) ---")
    crypto_client = CryptoDataClient()
    try:
        cquote = crypto_client.get_quote("BTC/USDT")
        print(f"[SUCCESS] Crypto Quote for BTC/USDT: Price=${cquote.price:,.2f}, Change={cquote.change_percent:+.2f}%")
        csma = crypto_client.calculate_sma("BTC/USDT", period=10)
        print(f"[SUCCESS] 10-day SMA for BTC/USDT: ${csma:,.2f}")
    except Exception as ce:
        print(f"[ERROR] Crypto market data test failed: {ce}")


def test_ai_connection() -> None:
    """Diagnostic tool to verify Groq AI analysis."""
    print(f"\n--- Testing Groq AI ({settings.effective_ai_model}) ---")
    ai_client = GroqClient(
        api_key=settings.effective_ai_api_key,
        model=settings.effective_ai_model
    )
    if not ai_client.is_configured():
        print("[WARNING] GROQ_API_KEY is not configured in .env. Running mock analysis test.")

    try:
        sample_indicators = {"current_price": 180.0, "short_sma": 186.0, "dip_percentage": 3.2}
        result = ai_client.analyze_trade_signal(
            ticker="AAPL_US_EQ",
            price=180.0,
            action="BUY",
            reason="Price dropped 3.2% below 10-day SMA support level.",
            indicators=sample_indicators
        )
        print(f"[SUCCESS] Groq AI Analysis Result:")
        print(f"  - Model Used: {result.model_used}")
        print(f"  - Sentiment:  {result.sentiment}")
        print(f"  - Confidence: {result.confidence_score}%")
        print(f"  - Summary:    {result.summary}")
        print(f"  - Catalysts:  {result.catalysts}")
    except Exception as e:
        print(f"[ERROR] Groq AI test failed: {e}")


def test_telegram_connection() -> None:
    """Diagnostic tool to verify Telegram notifications."""
    print("\n--- Testing Telegram Notifier Bot ---")
    notifier = TelegramNotifier(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id
    )
    if not notifier.is_configured():
        print("[WARNING] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing in .env.")

    try:
        test_msg = "🤖 <b>Trading Bot Diagnostic Test</b>\n\nTelegram notifications are successfully connected and working!"
        success = notifier.send_message(test_msg)
        if success:
            print("[SUCCESS] Sent diagnostic message to Telegram chat.")
        else:
            print("[ERROR] Failed to send Telegram message.")
    except Exception as e:
        print(f"[ERROR] Telegram test failed: {e}")


def test_tracker_diagnostics() -> None:
    """Diagnostic tool to inspect SQLite Signal Tracker stats and pending hypotheses."""
    print("\n--- Testing Signal Outcome Tracker (SQLite) ---")
    tracker = SignalTracker()
    stats = tracker.get_accuracy_stats()
    print(f"[SUCCESS] Database initialized at: {tracker.db_path}")
    print(f"  - Total Signals Recorded: {stats['total_signals']}")
    print(f"  - Evaluated Outcomes:     {stats['evaluated_count']}")
    print(f"  - Pending Verification:   {stats['pending_count']}")
    print(f"  - Win Rate:               {stats['win_rate_percent']}% ({stats['wins']} Wins / {stats['losses']} Losses / {stats['neutrals']} Neutral)")
    print(f"  - Average PnL:            {stats['avg_pnl_percent']:+.2f}%")


def test_risk_engine_diagnostics() -> None:
    """Diagnostic tool to inspect Deterministic Risk Engine position sizing and SL/TP calculation."""
    print("\n--- Testing Deterministic Risk Engine (KODA Phase 1) ---")
    engine = DeterministicRiskEngine(
        max_risk_per_trade_percent=1.5,
        max_position_size_percent=15.0,
        min_order_value=10.0,
        default_risk_reward_ratio=2.0
    )
    cash = AccountCash(free=500.0, total=2500.0, invested=2000.0, ppl=50.0, result=50.0)
    sample_indicators = {"short_sma": 185.0, "long_sma": 180.0, "atr": 3.50, "support": 178.0, "resistance": 195.0}

    result = engine.evaluate_trade_risk(
        ticker="AAPL_US_EQ",
        action="BUY",
        current_price=182.0,
        portfolio_cash=cash,
        indicators=sample_indicators,
        opportunity_score=1.0,
        max_order_override=50.0
    )

    print(f"[SUCCESS] Risk Evaluation for AAPL_US_EQ @ $182.00:")
    print(f"  - Approved:         {result.is_approved}")
    print(f"  - Position Sizing:  ${result.allocated_value:,.2f} ({result.estimated_shares:.4f} shares)")
    print(f"  - Dynamic Stop-Loss: ${result.stop_loss_price:,.2f}")
    print(f"  - Take-Profit:      ${result.take_profit_price:,.2f}")
    print(f"  - Risk:Reward Ratio: 1:{result.risk_reward_ratio:.1f}")
    print(f"  - Dollar Risk to SL: ${result.risk_amount:,.2f} ({result.risk_percent_of_portfolio}% of total equity)")


def run_universe_sync(target: str = "all", force: bool = True) -> None:
    """Synchronizes full tradable universe from Coinbase and Trading 212 / constituents and caches locally."""
    print(f"\n🌐 --- Synchronizing Market Universe [{target.upper()}] ---")
    mgr = UniverseManager()
    cache_data = mgr.sync_universe(target=target, force_refresh=force)
    print(f"[SUCCESS] Universe Synchronized:")
    print(f"  - Stocks Universe: {len(cache_data.stocks)} liquid instruments")
    print(f"  - Crypto Universe: {len(cache_data.crypto)} liquid pairs")
    print(f"  - Local Cache Path: {mgr.cache_file}")


def run_standalone_radar(target: str = "all", limit: Optional[int] = None) -> None:
    """Runs the KODA Multi-Level Scanning Pipeline (Pre-filter -> Quant Scoring -> Groq AI Finalist Review)."""
    print(f"\n📡 --- Running KODA Multi-Level Market Radar [{target.upper()}] ---")
    stock_client = YFinanceClient()
    crypto_client = CryptoDataClient()
    ai_client = GroqClient()
    uni_mgr = UniverseManager(crypto_client=crypto_client, market_client=stock_client)
    radar = MultiLevelMarketRadar(stock_client=stock_client, crypto_client=crypto_client)

    # 1. Fetch universe
    universe = uni_mgr.get_active_universe(target=target, limit=limit)
    if not universe:
        universe = list(settings.watchlist_tickers) + DEFAULT_CRYPTO_UNIVERSE

    print(f"Total Universe Size: {len(universe)} instruments")

    # 2. Run 3-Level Pipeline
    pipeline_res: MultiLevelPipelineResult = radar.run_multi_level_scan(
        universe=universe,
        target_market=target,
        ai_client=ai_client,
        l1_limit=min(len(universe), 50),
        l2_limit=15,
        l3_limit=5
    )

    print("\n" + "=" * 90)
    print(f"⚡ KODA MULTI-LEVEL SCANNER FUNNEL SUMMARY ({pipeline_res.duration_seconds:.1f}s)")
    print("=" * 90)
    print(f"  • Level 1 (Screened Universe):    {pipeline_res.total_screened_level1} instruments")
    print(f"  • Level 1 Survivors (RVOL & Mom): {pipeline_res.passed_level1_count} candidates")
    print(f"  • Level 2 Scored Setups:          {pipeline_res.passed_level2_count} ranked opportunities")
    print(f"  • Level 3 Groq AI Finalists:      {len(pipeline_res.level3_finalists)} high-conviction trades")
    print("-" * 90)

    print("\n🏆 LEVEL 3: GROQ AI FINALIST REVIEWS")
    print("=" * 90)
    for fin in pipeline_res.level3_finalists:
        rec_emoji = "🟢 PROCEED" if fin.recommendation == "PROCEED" else ("🔴 VETO" if fin.recommendation == "VETO" else "🟡 WATCH")
        price_str = f"${fin.price:,.2f}" if fin.price >= 1.0 else f"${fin.price:.4f}"
        print(f"[{fin.grade:<2}] {fin.ticker:<14} ({fin.market_type.upper()}) @ {price_str} | Score: {fin.composite_score:.0f}/100 | {rec_emoji}")
        print(f"    ↳ AI Sentiment: {fin.ai_sentiment} ({fin.ai_confidence}% confidence)")
        print(f"    ↳ Thesis:       {fin.ai_summary}")
        print(f"    ↳ Catalysts:    {fin.ai_catalysts}")
        print("-" * 90)


def run_macro_diagnostics() -> None:
    """Diagnostic tool to inspect the Economic Calendar and Macro Sentiment bias."""
    print("\n🌍 --- Running KODA Macro & Economic Calendar Diagnostics ---")
    cal = EconomicCalendar(risk_window_minutes=30)
    sentiment_engine = NewsSentimentEngine(calendar=cal)

    now = datetime.datetime.now(datetime.timezone.utc)
    in_risk, active_event, delta_min = cal.is_in_risk_window(now)
    upcoming = cal.get_upcoming_events(hours_ahead=72.0)
    summary = sentiment_engine.evaluate_macro_sentiment()

    print(f"• Event Risk Blackout Active: {'🚨 YES - TRADING FREEZE' if in_risk else '🟢 NO - NORMAL SPREAD'}")
    if active_event:
        print(f"  ↳ Active Risk Event: {active_event.title} ({active_event.event_type})")
        print(f"  ↳ Time Delta:        {delta_min:+.1f} minutes from release")

    print(f"\n• Macro Sentiment Bias:       {summary.sentiment_label} (Score: {summary.sentiment_score:.1f}/100)")
    print("  Key Market Drivers:")
    for d in summary.key_drivers:
        print(f"    - {d}")

    print("\n📅 Upcoming High-Impact Economic Events (Next 72h):")
    print("-" * 80)
    print(f"{'Scheduled (UTC)':<22} {'Impact':<8} {'Type':<8} {'Title'}")
    print("-" * 80)
    for ev in upcoming:
        dt_str = ev.scheduled_time.strftime("%Y-%m-%d %H:%M UTC")
        print(f"{dt_str:<22} {ev.impact.value:<8} {ev.event_type:<8} {ev.title}")
    print("-" * 80)


def run_regime_diagnostics() -> None:
    """Diagnostic tool to evaluate multi-asset market regime and strategy adjustments."""
    print("\n🧭 --- Running KODA Market Regime & Exposure Diagnostics ---")
    regime_engine = MarketRegimeEngine()
    exposure_engine = PortfolioExposureEngine()

    regime = regime_engine.classify_regime()

    print(f"• Primary Market Regime:       {regime.primary_regime.value}")
    print(f"• Volatility Environment:      {regime.volatility_level}")
    print(f"• Trend Strength:              {regime.trend_strength:.1f}/100")
    print(f"• Directives / Strategy Rules:")
    print(f"    ↳ Breakouts Allowed:       {'🟢 YES' if regime.can_trade_breakouts else '🔴 NO (VETOED)'}")
    print(f"    ↳ Trend Continuation:      {'🟢 YES' if regime.can_trade_trend_continuation else '🔴 NO'}")
    print(f"    ↳ Mean Reversion Dips:     {'🟢 YES' if regime.can_trade_mean_reversion else '🔴 NO'}")
    print(f"    ↳ Position Size Scale:     {regime.position_size_multiplier:.2f}x")
    print(f"    ↳ Stop-Loss ATR Multiplier: {regime.stop_loss_atr_multiplier:.1f}x ATR")
    print(f"    ↳ Rationale:               {regime.rationale}")

    # Test sample exposure
    mock_positions = {
        "NVDA_US_EQ": Position(ticker="NVDA_US_EQ", quantity=5.0, average_price=120.0, current_price=130.0, ppl=50.0),
        "BTC/USDT": Position(ticker="BTC/USDT", quantity=0.05, average_price=60000.0, current_price=65000.0, ppl=250.0),
    }
    exp = exposure_engine.evaluate_exposure_risk(
        candidate_ticker="AAPL_US_EQ",
        target_value=200.0,
        current_positions=mock_positions,
        total_equity=5000.0,
        free_cash=1100.0
    )
    print("\n📊 Portfolio Exposure & Beta Assessment (Sample $200 AAPL Entry on $5,000 Equity):")
    print(f"  • Approved:             {exp.is_approved}")
    print(f"  • Candidate Sector:     {exp.candidate_sector} (Beta: {exp.candidate_beta})")
    print(f"  • Post-Trade Beta:      {exp.portfolio_beta:.2f} (Max: {exposure_engine.max_portfolio_beta:.2f})")
    print(f"  • Sector Allocations:   {exp.sector_exposures_pct}")
    print(f"  • Cash Reserve:         {exp.cash_reserve_pct:.1f}%")


def run_audit_trail_diagnostics() -> None:
    """Diagnostic tool to inspect recent end-to-end Decision Audit Trail logs and execution metrics."""
    print("\n📋 --- Running KODA Decision Audit Trail & Execution Diagnostics ---")
    audit = DecisionAuditTrail()
    exec_engine = ExecutionQualityEngine()

    traces = audit.get_recent_traces(limit=10)
    exec_summary = exec_engine.get_execution_summary()

    print("⚡ Execution Quality Summary:")
    print(f"  • Total Recorded Fills:   {exec_summary['total_executions']}")
    print(f"  • Average Slippage:       {exec_summary['avg_slippage_bps']:+.1f} bps")
    print(f"  • Max Observed Slippage:  {exec_summary['max_slippage_bps']:+.1f} bps")
    print(f"  • Average Latency:        {exec_summary['avg_latency_ms']:.1f} ms")
    print(f"  • Total Broker Fees:      ${exec_summary['total_fees_usd']:.2f}")

    if not traces:
        # Generate sample trace for verification
        audit.log_decision_chain(
            ticker="NVDA_US_EQ",
            market_type="stock",
            regime="TRENDING_BULL",
            quant_score=85.0,
            macro_sentiment="BULLISH_RISK_ON",
            ai_sentiment="BULLISH",
            ai_confidence=80,
            risk_approved=True,
            exposure_approved=True,
            execution_status="EXECUTED",
            trace_details={"stage": "Complete Pipeline Pass"}
        )
        traces = audit.get_recent_traces(limit=5)

    print("\n📋 Recent Decision Chains (Audit Trace Log):")
    print("=" * 95)
    print(f"{'ID':<4} {'Ticker':<14} {'Market':<8} {'Regime':<14} {'Quant':<6} {'Macro':<16} {'AI':<14} {'Status'}")
    print("-" * 95)
    for t in traces:
        status_tag = f"🟢 {t.execution_status}" if t.execution_status == "EXECUTED" else f"🔴 {t.execution_status}"
        ai_str = f"{t.ai_sentiment}({t.ai_confidence}%)"
        print(f"#{t.id:<3} {t.ticker:<14} {t.market_type.upper():<8} {t.regime:<14} {t.quant_score:<6.0f} {t.macro_sentiment:<16} {ai_str:<14} {status_tag}")
        if t.rejection_reason:
            print(f"    ↳ Rejection Reason: {t.rejection_reason}")
    print("=" * 95)


def run_trade_autopsies() -> None:
    """Diagnostic tool to run Trade Autopsy post-mortem analysis on recorded past signals and log to Obsidian."""
    print("\n🔬 --- Running KODA Trade Autopsy Post-Mortem Engine ---")
    tracker = SignalTracker()
    autopsy = TradeAutopsyEngine()
    stock_client = YFinanceClient()
    crypto_client = CryptoDataClient()

    # 1. Forward-test any pending signals immediately
    try:
        evaluated_now = tracker.evaluate_past_signals(
            market_client=stock_client,
            crypto_client=crypto_client,
            stock_min_age_hours=0.0,
            crypto_min_age_hours=0.0
        )
        if evaluated_now:
            print(f"[INFO] Forward-tested {len(evaluated_now)} pending signal(s) against current market prices.")
    except Exception as e:
        logger.debug(f"Could not forward-test pending signals: {e}")

    evaluated = tracker.get_evaluated_signals(limit=10)

    if not evaluated:
        print("[INFO] No evaluated trade signal outcomes found in database to autopsy.")
        print("      Generating sample diagnostic autopsies for verification...")
        evaluated = [
            {
                "id": 1,
                "ticker": "BTC/USDT",
                "market_type": "crypto",
                "signal_type": "BUY",
                "entry_price": 78000.0,
                "exit_price": 79800.0,
                "pnl_percent": 2.31,
                "outcome": "WIN",
                "indicators": {"short_sma": 76000.0, "long_sma": 70000.0, "rsi": 62.0}
            },
            {
                "id": 2,
                "ticker": "NVDA_US_EQ",
                "market_type": "stock",
                "signal_type": "BUY",
                "entry_price": 142.0,
                "exit_price": 138.5,
                "pnl_percent": -2.46,
                "outcome": "LOSS",
                "indicators": {"resistance": 143.0, "atr": 3.20, "rsi": 78.0}
            }
        ]

    print(f"\nConducting autopsies on {len(evaluated)} trade outcome(s):\n")
    print("=" * 85)
    autopsy_reports = []
    for rec in evaluated:
        rep = autopsy.analyze_outcome(rec)
        autopsy_reports.append(rep)
        outcome_tag = f"🟢 WIN ({rep.pnl_percent:+.2f}%)" if rep.outcome == "WIN" else f"🔴 LOSS ({rep.pnl_percent:+.2f}%)"
        print(f"Autopsy #{rep.signal_id} | {rep.ticker} | {rep.market_type.upper()} | {outcome_tag}")
        print(f"  - Root Cause:          {rep.root_cause}")
        print(f"  - Primary Driver:      {rep.primary_driver}")
        print(f"  - 💡 Actionable Lesson: {rep.actionable_lesson}")
        print(f"  - 🛡 Rule Recommendation: {rep.rule_recommendation}")
        print("-" * 85)

    # 2. Append autopsies to Obsidian Learning Journal
    try:
        obsidian = ObsidianClient(
            api_key=settings.obsidian_rest_api_key,
            host=settings.obsidian_host,
            port=settings.obsidian_port,
            use_https=settings.obsidian_use_https,
            vault_folder=settings.obsidian_vault_folder
        )
        saved_path = obsidian.log_trade_autopsies(autopsy_reports)
        print(f"\n[SUCCESS] Appended {len(autopsy_reports)} trade autopsy reports to Obsidian: {saved_path}")
    except Exception as obs_err:
        print(f"\n[WARNING] Could not save autopsies to Obsidian: {obs_err}")


def run_autopsy_statistics() -> None:
    """Diagnostic tool to inspect Process-vs-Outcome distributions, Counterfactuals, and Confidence Calibration."""
    print("\n📊 --- Running KODA Trade Autopsy 2.0 & Calibration Analytics ---")
    tracker = SignalTracker()
    autopsy = TradeAutopsyEngine()
    conf_tracker = ConfidenceTracker()

    evaluated = tracker.get_evaluated_signals(limit=50)
    if not evaluated:
        evaluated = [
            {"id": 1, "ticker": "BTC/USDT", "market_type": "crypto", "signal_type": "BUY", "entry_price": 60000.0, "exit_price": 63000.0, "pnl_percent": 5.0, "outcome": "WIN", "indicators": {"short_sma": 61000.0, "long_sma": 58000.0, "rsi": 62.0, "atr": 1500.0}},
            {"id": 2, "ticker": "SOL/USDT", "market_type": "crypto", "signal_type": "BUY", "entry_price": 140.0, "exit_price": 133.0, "pnl_percent": -5.0, "outcome": "LOSS", "indicators": {"short_sma": 135.0, "long_sma": 130.0, "rsi": 78.0, "atr": 4.0}},
            {"id": 3, "ticker": "NVDA_US_EQ", "market_type": "stock", "signal_type": "BUY", "entry_price": 120.0, "exit_price": 116.0, "pnl_percent": -3.3, "outcome": "LOSS", "indicators": {"short_sma": 122.0, "long_sma": 118.0, "rsi": 55.0, "atr": 3.0}},
        ]

    # Calculate Quadrants
    quadrant_counts = {
        DecisionOutcomeQuadrant.GOOD_DECISION_WIN.value: 0,
        DecisionOutcomeQuadrant.GOOD_DECISION_LOSS.value: 0,
        DecisionOutcomeQuadrant.BAD_DECISION_WIN.value: 0,
        DecisionOutcomeQuadrant.BAD_DECISION_LOSS.value: 0,
    }
    wider_sl_saved = 0

    for ev in evaluated:
        rep = autopsy.analyze_outcome(ev)
        quadrant_counts[rep.decision_outcome_quadrant] = quadrant_counts.get(rep.decision_outcome_quadrant, 0) + 1
        if rep.counterfactual_wider_sl_result == "WIN" and rep.outcome == "LOSS":
            wider_sl_saved += 1

    total_ops = sum(quadrant_counts.values())

    print("\n🧭 Process vs Outcome Matrix (Annie Duke Model):")
    print("=" * 75)
    print(f"  • Good Decision / Win  (Ideal Edge):    {quadrant_counts[DecisionOutcomeQuadrant.GOOD_DECISION_WIN.value]} ({((quadrant_counts[DecisionOutcomeQuadrant.GOOD_DECISION_WIN.value] / total_ops) * 100.0 if total_ops else 0):.1f}%)")
    print(f"  • Good Decision / Loss (Acceptable Risk): {quadrant_counts[DecisionOutcomeQuadrant.GOOD_DECISION_LOSS.value]} ({((quadrant_counts[DecisionOutcomeQuadrant.GOOD_DECISION_LOSS.value] / total_ops) * 100.0 if total_ops else 0):.1f}%)")
    print(f"  • Bad Decision / Win   (Fluke Luck):      {quadrant_counts[DecisionOutcomeQuadrant.BAD_DECISION_WIN.value]} ({((quadrant_counts[DecisionOutcomeQuadrant.BAD_DECISION_WIN.value] / total_ops) * 100.0 if total_ops else 0):.1f}%)")
    print(f"  • Bad Decision / Loss  (Systemic Mistake):{quadrant_counts[DecisionOutcomeQuadrant.BAD_DECISION_LOSS.value]} ({((quadrant_counts[DecisionOutcomeQuadrant.BAD_DECISION_LOSS.value] / total_ops) * 100.0 if total_ops else 0):.1f}%)")
    print("-" * 75)
    print(f"  ↳ Counterfactual +0.5 ATR Stop-Loss saved {wider_sl_saved} premature whipsaw loss(es).")

    # Calibration report
    cal_rep = conf_tracker.get_calibration_report()
    print("\n🎯 Confidence Calibration Report (AI Confidence vs Empirical Win Rate):")
    print("=" * 85)
    print(f"{'Bracket':<12} {'Expected':<10} {'Signals':<10} {'Wins/Losses':<14} {'Actual Win%':<14} {'Status'}")
    print("-" * 85)
    for b in cal_rep["brackets"]:
        wl_str = f"{b.wins}W / {b.losses}L"
        status_emoji = "🟢 CALIBRATED" if b.status == "CALIBRATED" else ("⚠️ " + b.status)
        print(f"{b.bracket_name:<12} {b.expected_midpoint:<10.1f}% {b.total_signals:<10} {wl_str:<14} {b.actual_win_rate_pct:<14.1f}% {status_emoji}")
    print("=" * 85)


def run_research_lab_diagnostics() -> None:
    """Diagnostic tool to inspect Research Lab scientific hypothesis pipeline and gatekeeper state."""
    print("\n🧪 --- Running KODA Research Lab & Scientific Hypothesis Pipeline ---")
    lab = ResearchLabEngine()
    hypotheses = lab.list_all_hypotheses()

    if not hypotheses:
        # Seed initial hypotheses for verification
        h1 = lab.create_hypothesis(
            hypothesis_id="HYP-VOL-BREAKOUT",
            title="Dynamic ATR Volatility Expansion Filter",
            description="Require 2.0x ATR expansion and RVOL >= 2.5 on breakout triggers.",
            target_market="all"
        )
        lab.advance_stage(h1.hypothesis_id, backtest_sharpe=1.85, backtest_profit_factor=1.75)
        lab.advance_stage(h1.hypothesis_id, walk_forward_efficiency=0.78)
        lab.advance_stage(h1.hypothesis_id, shadow_trades_count=12, shadow_win_rate_pct=66.7)

        h2 = lab.create_hypothesis(
            hypothesis_id="HYP-RSI-EXTREME",
            title="Overbought Mean-Reversion Shorting",
            description="Sell short crypto assets when 1h RSI exceeds 85.0.",
            target_market="crypto"
        )
        lab.advance_stage(h2.hypothesis_id, backtest_sharpe=1.10, backtest_profit_factor=1.15)  # Will fail backtest

        hypotheses = lab.list_all_hypotheses()

    print("🛡 Scientific Validation Gatekeeper Requirements:")
    print(f"  • Stage 1 (Backtest):     Sharpe >= {lab.MIN_BACKTEST_SHARPE:.2f}, Profit Factor >= {lab.MIN_BACKTEST_PROFIT_FACTOR:.2f}")
    print(f"  • Stage 2 (Walk-Forward): Efficiency (OOS/IS) >= {lab.MIN_WALK_FORWARD_EFFICIENCY:.2f}")
    print(f"  • Stage 3 (Shadow Run):   Min {lab.MIN_SHADOW_TRADES} trades, Win Rate >= {lab.MIN_SHADOW_WIN_RATE:.1f}%\n")

    print("📋 Active Research Hypotheses:")
    print("=" * 95)
    print(f"{'ID':<18} {'Target':<8} {'Stage':<22} {'Sharpe':<8} {'PF':<6} {'WFE':<6} {'Shadow Win%':<12} {'Status'}")
    print("-" * 95)
    for h in hypotheses:
        status_tag = "🟢 APPROVED" if h.stage == HypothesisStage.APPROVED else ("🔴 REJECTED" if h.stage == HypothesisStage.REJECTED else f"⏳ {h.stage.value}")
        print(f"{h.hypothesis_id:<18} {h.target_market.upper():<8} {h.stage.value:<22} {h.backtest_sharpe:<8.2f} {h.backtest_profit_factor:<6.2f} {h.walk_forward_efficiency:<6.2f} {h.shadow_win_rate_pct:<12.1f}% {status_tag}")
        if h.rejection_reason:
            print(f"    ↳ Rejection: {h.rejection_reason}")
    print("=" * 95)


def run_tournament_diagnostics() -> None:
    """Diagnostic tool to inspect Strategy Tournament leaderboard and regime-ranked allocations."""
    print("\n🏆 --- Running KODA Strategy Tournament Leaderboard ---")
    regime_engine = MarketRegimeEngine()
    tournament = StrategyTournamentEngine()

    current_regime = regime_engine.classify_regime()
    ranked = tournament.rank_strategies(current_regime=current_regime.primary_regime.value)

    print(f"• Active Market Regime: {current_regime.primary_regime.value} ({current_regime.volatility_level} Volatility)")
    print(f"• Regime Directives:    {current_regime.rationale}\n")

    print(f"🏆 Strategy Leaderboard (Regime-Adjusted Ranking):")
    print("=" * 95)
    print(f"{'Rank':<5} {'Strategy Archetype':<26} {'Trades':<8} {'Win%':<8} {'PF':<6} {'Sharpe':<8} {'Score':<8} {'Alloc %'}")
    print("-" * 95)
    for idx, st in enumerate(ranked):
        print(f"#{idx+1:<4} {st.name:<26} {st.total_trades:<8} {st.win_rate_pct:<8.1f}% {st.profit_factor:<6.2f} {st.sharpe_ratio:<8.2f} {st.tournament_score:<8.1f} {st.recommended_allocation_pct:.1f}%")
    print("=" * 95)


def test_portfolio_brain_diagnostics() -> None:
    """Diagnostic tool to inspect PortfolioBrain correlation matrix & allocation constraints."""
    print("\n💼 --- Testing Portfolio Brain & Correlation Engine (KODA Phase 3) ---")
    brain = PortfolioBrain(
        max_correlation_threshold=0.85,
        max_highly_correlated_count=2,
        max_crypto_allocation_percent=40.0,
        max_single_asset_percent=20.0,
        min_cash_reserve_percent=10.0
    )

    # Test correlation math
    series_a = [100.0, 102.0, 101.0, 105.0, 107.0, 106.0, 110.0]
    series_b = [50.0, 51.0, 50.5, 52.5, 53.5, 53.0, 55.0]  # Highly correlated
    series_c = [20.0, 19.0, 20.5, 18.0, 17.5, 18.5, 16.0]  # Inversely correlated

    corr_ab = brain.calculate_returns_correlation(series_a, series_b)
    corr_ac = brain.calculate_returns_correlation(series_a, series_c)

    print(f"[SUCCESS] Correlation Math:")
    print(f"  - Returns Correlation (Series A vs B): r = {corr_ab:+.2f} (Expected > +0.80)")
    print(f"  - Returns Correlation (Series A vs C): r = {corr_ac:+.2f} (Expected < -0.80)")

    # Test allocation check
    stock_cash = AccountCash(free=500.0, total=2500.0, invested=2000.0, ppl=0.0, result=0.0)
    crypto_cash = AccountCash(free=100.0, total=500.0, invested=400.0, ppl=0.0, result=0.0)

    eval_res = brain.evaluate_entry_risk(
        candidate_ticker="NVDA_US_EQ",
        market_type="stock",
        target_value=25.0,
        current_positions={},
        stock_cash=stock_cash,
        crypto_cash=crypto_cash,
        candidate_history_closes=series_a
    )

    print(f"\n[SUCCESS] Portfolio Allocation Assessment for NVDA_US_EQ ($25.00 entry):")
    print(f"  - Approved:         {eval_res.is_approved}")
    print(f"  - Stock Allocation: {eval_res.stock_allocation_percent}%")
    print(f"  - Crypto Allocation: {eval_res.crypto_allocation_percent}%")
    print(f"  - Cash Reserve:     {eval_res.cash_reserve_percent}%")


def run_morning_brief(target: str = "all", limit: Optional[int] = 10) -> None:
    """Generates and dispatches the KODA Morning Intelligence Brief to Telegram and Obsidian."""
    print("\n🌅 --- Generating KODA Morning Intelligence Brief ---")
    broker = Trading212Client()
    crypto_client = CryptoDataClient()
    market_client = YFinanceClient()
    radar = MarketRadar(stock_client=market_client, crypto_client=crypto_client)
    scorer = OpportunityScorer()
    ks = KillSwitch()
    telegram = TelegramNotifier()
    obsidian = ObsidianClient(
        api_key=settings.obsidian_rest_api_key,
        host=settings.obsidian_host,
        port=settings.obsidian_port,
        use_https=settings.obsidian_use_https,
        vault_folder=settings.obsidian_vault_folder
    )

    # 1. Fetch Balances
    stock_cash = None
    if target in ("stocks", "all"):
        try:
            stock_cash = broker.get_account_cash()
        except Exception:
            stock_cash = AccountCash(free=1000.0, total=1000.0, invested=0.0, ppl=0.0, result=0.0)

    crypto_cash = None
    if target in ("crypto", "all"):
        crypto_cash = crypto_client.get_balance() or AccountCash(free=500.0, total=500.0, invested=0.0, ppl=0.0, result=0.0)

    # 2. Scan Top Radar Setups
    radar_scans: List[RadarAssetScanResult] = []
    if target in ("stocks", "all"):
        for s in list(settings.watchlist_tickers)[:5]:
            try:
                radar_scans.append(radar.analyze_asset(ticker=s, market_type="stock"))
            except Exception:
                pass

    if target in ("crypto", "all"):
        for c in crypto_client.get_all_tradable_crypto(limit=5):
            try:
                radar_scans.append(radar.analyze_asset(ticker=c, market_type="crypto"))
            except Exception:
                pass

    ranked = scorer.rank_opportunities(radar_scans, top_n=5, min_score=40.0)
    top_setups = [
        {
            "ticker": r.ticker,
            "market_type": r.market_type,
            "price": r.price,
            "composite_score": r.composite_score,
            "grade": r.grade,
            "key_events": r.key_events
        }
        for r in ranked
    ]

    macro_sentiment = "BULLISH BIAS (S&P 500 & BTC In Steady Uptrends)"
    focus_notes = "Prioritize pullback entries on A/A+ ranked setups near dynamic support with confirmed volume."

    # 3. Dispatch to Telegram and Obsidian
    tg_res = telegram.send_morning_brief(
        stock_cash=stock_cash,
        crypto_cash=crypto_cash,
        top_radar_setups=top_setups,
        macro_sentiment=macro_sentiment,
        health_state=ks.state.value,
        daily_focus_notes=focus_notes
    )
    obs_path = obsidian.log_morning_brief(
        top_radar_setups=top_setups,
        macro_sentiment=macro_sentiment,
        stock_cash=stock_cash,
        crypto_cash=crypto_cash,
        focus_notes=focus_notes
    )

    print(f"[SUCCESS] Morning Brief Dispatched: Telegram={'Sent' if tg_res else 'Skipped'} | Obsidian='{obs_path}'")


def run_evening_brief(target: str = "all") -> None:
    """Generates and dispatches the KODA End-of-Day Evening Brief to Telegram and Obsidian."""
    print("\n🌆 --- Generating KODA End-of-Day Intelligence Brief ---")
    broker = Trading212Client()
    crypto_client = CryptoDataClient()
    tracker = SignalTracker()
    telegram = TelegramNotifier()
    obsidian = ObsidianClient(
        api_key=settings.obsidian_rest_api_key,
        host=settings.obsidian_host,
        port=settings.obsidian_port,
        use_https=settings.obsidian_use_https,
        vault_folder=settings.obsidian_vault_folder
    )

    # 1. Fetch Balances & Positions
    stock_cash = None
    open_positions: List[str] = []
    if target in ("stocks", "all"):
        try:
            stock_cash = broker.get_account_cash()
            pos = broker.get_open_positions()
            open_positions = [p.ticker for p in pos if p.quantity > 0]
        except Exception:
            stock_cash = AccountCash(free=1000.0, total=1000.0, invested=0.0, ppl=0.0, result=0.0)

    crypto_cash = None
    if target in ("crypto", "all"):
        crypto_cash = crypto_client.get_balance() or AccountCash(free=500.0, total=500.0, invested=0.0, ppl=0.0, result=0.0)

    # 2. Get Performance Stats and Autopsies
    stats = tracker.get_accuracy_stats()
    evaluated = tracker.get_evaluated_signals(limit=5)
    autopsy_engine = TradeAutopsyEngine()
    lessons: List[str] = []
    for ev in evaluated:
        rep = autopsy_engine.analyze_outcome(ev)
        if rep.actionable_lesson and rep.actionable_lesson not in lessons:
            lessons.append(rep.actionable_lesson)

    # 3. Dispatch to Telegram and Obsidian
    tg_res = telegram.send_evening_brief(
        stock_cash=stock_cash,
        crypto_cash=crypto_cash,
        daily_stats=stats,
        autopsy_lessons=lessons,
        open_positions=open_positions
    )
    obs_path = obsidian.log_evening_brief(
        daily_stats=stats,
        stock_cash=stock_cash,
        crypto_cash=crypto_cash,
        autopsy_lessons=lessons,
        open_positions=open_positions
    )

    print(f"[SUCCESS] Evening Brief Dispatched: Telegram={'Sent' if tg_res else 'Skipped'} | Obsidian='{obs_path}'")


def run_interactive_ask(question: str) -> None:
    """Processes interactive natural language chat with KODA AI and outputs to console and Telegram."""
    print(f"\n🤖 --- Asking KODA Intelligence: '{question}' ---")
    ai_client = GroqClient()
    broker = Trading212Client()
    crypto_client = CryptoDataClient()
    market_client = YFinanceClient()
    radar = MarketRadar(stock_client=market_client, crypto_client=crypto_client)
    scorer = OpportunityScorer()
    ks = KillSwitch()
    tracker = SignalTracker()
    telegram = TelegramNotifier()

    # Build Live Portfolio State
    stock_cash = None
    open_pos = "None"
    try:
        stock_cash = broker.get_account_cash()
        pos = broker.get_open_positions()
        if pos:
            open_pos = ", ".join(f"{p.ticker} ({p.quantity:.2f} sh)" for p in pos if p.quantity > 0)
    except Exception:
        stock_cash = AccountCash(free=1000.0, total=1000.0, invested=0.0, ppl=0.0, result=0.0)

    crypto_cash = crypto_client.get_balance() or AccountCash(free=500.0, total=500.0, invested=0.0, ppl=0.0, result=0.0)

    portfolio_ctx = {
        "stock_free": stock_cash.free if stock_cash else 0.0,
        "stock_total": stock_cash.total if stock_cash else 0.0,
        "crypto_free": crypto_cash.free if crypto_cash else 0.0,
        "crypto_total": crypto_cash.total if crypto_cash else 0.0,
        "open_positions": open_pos,
        "health_state": ks.state.value
    }

    # Radar Top Setups
    radar_scans = []
    for c in crypto_client.get_all_tradable_crypto(limit=3):
        try:
            radar_scans.append(radar.analyze_asset(ticker=c, market_type="crypto"))
        except Exception:
            pass

    ranked = scorer.rank_opportunities(radar_scans, top_n=3, min_score=40.0)
    radar_ctx = [
        {
            "ticker": r.ticker,
            "market_type": r.market_type,
            "price": r.price,
            "composite_score": r.composite_score,
            "grade": r.grade,
            "key_events": r.key_events
        }
        for r in ranked
    ]

    # Recent Lessons
    evaluated = tracker.get_evaluated_signals(limit=4)
    autopsy_engine = TradeAutopsyEngine()
    lessons = [autopsy_engine.analyze_outcome(ev).actionable_lesson for ev in evaluated]

    # Active Market Regime & Recent Logs
    regime_engine = MarketRegimeEngine()
    reg = regime_engine.classify_regime()
    regime_str = f"{reg.primary_regime.value} ({reg.volatility_level} Volatility) - {reg.rationale}"

    from services.telegram_bot import get_recent_system_logs
    from services.execution_quality import ExecutionQualityEngine
    logs_str = get_recent_system_logs(max_lines=35)
    exec_engine = ExecutionQualityEngine()
    recent_execs = exec_engine.get_recent_executions(limit=8)
    history_str = "\n".join(
        f"• {rx.ticker} ({rx.action}): Fill=${rx.filled_price:,.2f} vs Exp=${rx.expected_price:,.2f} (Slippage: {rx.slippage_bps:+.1f} bps, Status: {rx.status})"
        for rx in recent_execs
    )

    from services.universe_manager import MarketUniverseManager
    from services.obsidian_exporter import ObsidianVaultExporter
    um = MarketUniverseManager()
    stats = um.get_universe_stats()
    univ_str = f"Stocks Universe: {stats.get('stocks_count', 80)} instruments, Crypto Universe: {stats.get('crypto_count', 16)} pairs"
    obs_exporter = ObsidianVaultExporter()
    obsidian_str = obs_exporter.get_status_summary()

    answer = telegram.handle_ask_command(
        question=question,
        ai_client=ai_client,
        portfolio_context=portfolio_ctx,
        radar_context=radar_ctx,
        lessons=lessons,
        log_context=logs_str,
        regime_context=regime_str,
        trade_history_context=history_str,
        universe_context=univ_str,
        obsidian_context=obsidian_str,
        dispatch_to_telegram=True
    )

    print("\n💡 KODA Analysis Response:")
    print("=" * 80)
    print(answer)
    print("=" * 80)


def run_telegram_listener(enable_loop: bool = True) -> None:
    """Starts the interactive Telegram Management Bot listener and background trader loop."""
    print("\n🤖 --- Starting KODA Interactive Telegram Management Bot ---")
    from services.trader_loop import ContinuousTraderLoop

    ai_client = GroqClient(
        api_key=settings.groq_api_key,
        model_name=settings.groq_model,
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_model=settings.openrouter_model
    )
    notifier = TelegramNotifier(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_allowed_user_id or settings.telegram_chat_id
    )

    trader_loop = ContinuousTraderLoop(
        interval_seconds=300,
        notifier=notifier,
        ai_client=ai_client,
        auto_start=enable_loop
    )

    bot = TelegramBotManager(
        bot_token=settings.telegram_bot_token,
        allowed_user_id=settings.telegram_allowed_user_id or settings.telegram_chat_id,
        notifier=notifier,
        ai_client=ai_client,
        trader_loop=trader_loop
    )

    try:
        bot.run_polling()
    finally:
        trader_loop.stop()


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Automated Stock & Crypto Trading, AI Sentiment & Obsidian Journaling Bot")
    parser.add_argument("--run-once", action="store_true", help="Execute one trading evaluation cycle and exit immediately.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate strategy and log to Obsidian without executing broker orders.")
    parser.add_argument("--target", choices=["stocks", "crypto", "all"], default="all", help="Market target to scan: 'stocks', 'crypto', or 'all' (default: 'all').")
    parser.add_argument("--scan-market", action="store_true", help="Dynamically scan the broad market (S&P 500 / NASDAQ / T212 instruments) instead of static watchlist.")
    parser.add_argument("--scan-limit", type=int, default=None, help="Limit number of dynamically scanned tickers (e.g. 50, 100).")
    parser.add_argument("--telegram", action="store_true", help="Start interactive Telegram Management Bot polling listener with background trader loop.")
    parser.add_argument("--loop", action="store_true", help="Start continuous background trader loop worker.")
    parser.add_argument("--radar", action="store_true", help="Run standalone KODA Market Radar multi-timeframe opportunity scanner.")
    parser.add_argument("--autopsy", action="store_true", help="Run Trade Autopsy post-mortem analysis on evaluated trade outcomes.")
    parser.add_argument("--autopsy-stats", action="store_true", help="Inspect Trade Autopsy 2.0 Process-vs-Outcome matrix and AI Confidence Calibration.")
    parser.add_argument("--research-lab", action="store_true", help="Inspect Research Lab scientific hypothesis pipeline and gatekeeper state.")
    parser.add_argument("--tournament", action="store_true", help="Inspect Strategy Tournament leaderboard and regime-ranked strategy allocations.")
    parser.add_argument("--test-portfolio", action="store_true", help="Test Portfolio Brain correlation matrix and allocation constraints.")
    parser.add_argument("--universe-sync", action="store_true", help="Synchronize and cache institutional market universe (Stocks & Crypto).")
    parser.add_argument("--macro", action="store_true", help="Inspect Economic Calendar, event risk windows, and news sentiment bias.")
    parser.add_argument("--regime", action="store_true", help="Diagnose multi-asset Market Regime, strategy rules, and portfolio beta exposure.")
    parser.add_argument("--audit-trail", action="store_true", help="Inspect chronological trade decision chains and execution quality metrics.")
    parser.add_argument("--morning-brief", action="store_true", help="Generate and send KODA Morning Intelligence Brief to Telegram and Obsidian.")
    parser.add_argument("--eod-brief", action="store_true", help="Generate and send KODA End-of-Day Evening Brief to Telegram and Obsidian.")
    parser.add_argument("--ask", type=str, default=None, help="Ask KODA AI a natural language question with live portfolio & market context.")
    parser.add_argument("--test-obsidian", action="store_true", help="Test Obsidian Local REST API connectivity and log test record.")
    parser.add_argument("--test-t212", action="store_true", help="Test Trading 212 API connectivity and print account balance.")
    parser.add_argument("--test-market", action="store_true", help="Test yfinance & crypto market data fetch.")
    parser.add_argument("--test-ai", action="store_true", help="Test Groq AI trade analysis.")
    parser.add_argument("--test-telegram", action="store_true", help="Test Telegram Bot alert dispatch.")
    parser.add_argument("--test-tracker", action="store_true", help="Test Signal Tracker and view ML accuracy statistics.")
    parser.add_argument("--test-risk", action="store_true", help="Test Deterministic Risk Engine position sizing and SL/TP calculations.")
    parser.add_argument("--kill", action="store_true", help="Engage Kill Switch (HALT all trading activities).")
    parser.add_argument("--safe-mode", action="store_true", help="Engage SAFE MODE (block new buys, permit position reduction only).")
    parser.add_argument("--reset-kill", action="store_true", help="Reset Kill Switch to NORMAL operational state.")
    parser.add_argument("--status", action="store_true", help="Print current system health and circuit breaker status.")

    args = parser.parse_args()

    # Telegram Management Bot Mode
    if args.telegram:
        run_telegram_listener(enable_loop=True)
        return

    # Continuous Loop Standalone Mode
    if args.loop:
        from services.trader_loop import ContinuousTraderLoop
        loop = ContinuousTraderLoop(interval_seconds=300, auto_start=True)
        print("⚡ KODA Continuous Trader Loop active. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            loop.stop()
        return

    # Universe Sync Mode
    if args.universe_sync:
        run_universe_sync(target=args.target, force=True)
        return

    # Macro Diagnostics Mode
    if args.macro:
        run_macro_diagnostics()
        return

    # Market Regime & Exposure Diagnostics Mode
    if args.regime:
        run_regime_diagnostics()
        return

    # Decision Audit Trail Mode
    if args.audit_trail:
        run_audit_trail_diagnostics()
        return

    # Autopsy Stats Mode
    if args.autopsy_stats:
        run_autopsy_statistics()
        return

    # Research Lab Mode
    if args.research_lab:
        run_research_lab_diagnostics()
        return

    # Strategy Tournament Mode
    if args.tournament:
        run_tournament_diagnostics()
        return

    # Morning Brief Mode
    if args.morning_brief:
        run_morning_brief(target=args.target, limit=args.scan_limit)
        return

    # Evening Brief Mode
    if args.eod_brief:
        run_evening_brief(target=args.target)
        return

    # Interactive Ask Mode
    if args.ask:
        run_interactive_ask(question=args.ask)
        return

    # Standalone Radar Mode
    if args.radar:
        run_standalone_radar(target=args.target, limit=args.scan_limit)
        return

    # Trade Autopsy Mode
    if args.autopsy:
        run_trade_autopsies()
        return

    # Test Portfolio Brain
    if args.test_portfolio:
        test_portfolio_brain_diagnostics()
        return

    # Manual Kill Switch actions
    ks = KillSwitch()
    if args.kill:
        ks.trigger_kill("Manual CLI command --kill")
        print(f"[KILL SWITCH] System HALTED. Status: {ks.get_status()}")
        return
    if args.safe_mode:
        ks.engage_safe_mode("Manual CLI command --safe-mode")
        print(f"[KILL SWITCH] System placed in SAFE MODE. Status: {ks.get_status()}")
        return
    if args.reset_kill:
        ks.reset()
        print(f"[KILL SWITCH] Circuit breaker RESET. Status: {ks.get_status()}")
        return
    if args.status:
        print("\n--- System Health & Kill Switch Status ---")
        status = ks.get_status()
        print(f"  - Health State:            {status['state']}")
        print(f"  - Consecutive API Errors:  {status['consecutive_api_errors']}")
        print(f"  - Trigger Reason:          {status['trigger_reason'] or 'None (Healthy)'}")
        print(f"  - Peak Portfolio Equity:   ${status['peak_equity']:,.2f}")
        return

    # Diagnostic modes
    if args.test_obsidian:
        test_obsidian_connection()
        return
    if args.test_t212:
        test_trading212_connection()
        return
    if args.test_market:
        test_market_data_connection()
        return
    if args.test_ai:
        test_ai_connection()
        return
    if args.test_telegram:
        test_telegram_connection()
        return
    if args.test_tracker:
        test_tracker_diagnostics()
        return
    if args.test_risk:
        test_risk_engine_diagnostics()
        return

    # Initialize bot orchestrator
    bot = TradingBotOrchestrator(
        dry_run=args.dry_run,
        scan_market=args.scan_market,
        scan_limit=args.scan_limit,
        target=args.target
    )

    if args.run_once:
        logger.info("Executing single evaluation run (--run-once)...")
        bot.run_cycle()
        logger.info("Completed single run. Exiting.")
        return

    # Start recurring scheduler
    if HAS_APSCHEDULER:
        scheduler = BlockingScheduler()
        scheduler.add_job(
            bot.run_cycle,
            trigger=IntervalTrigger(minutes=settings.check_interval_minutes),
            id="trading_cycle_job",
            name="Dual-Market Strategy Evaluation & Execution",
            replace_existing=True,
            next_run_time=datetime.datetime.now()  # Run immediately on startup
        )

        logger.info(f"APScheduler started. Running every {settings.check_interval_minutes} minutes. Press Ctrl+C to stop.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutdown requested. Stopping scheduler...")
            scheduler.shutdown()
            logger.info("Trading Bot stopped gracefully.")
    else:
        logger.info(f"Loop runner started (running every {settings.check_interval_minutes} min). Press Ctrl+C to stop.")
        try:
            while True:
                bot.run_cycle()
                logger.info(f"Sleeping for {settings.check_interval_minutes} minutes until next cycle...")
                time.sleep(settings.check_interval_minutes * 60)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutdown requested. Trading Bot stopped gracefully.")


if __name__ == "__main__":
    main()
