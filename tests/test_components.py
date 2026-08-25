"""
Unit and Integration Tests for Trading Bot Components
Tests strategy calculation, yfinance ticker normalization, dynamic market scanner,
Crypto market data service (CCXT/Binance), Trading 212 HTTP Basic Authentication & instruments,
Groq AI analysis with fallback routing, Telegram notifications, and Obsidian Markdown formatting.
"""

import base64
import os
import unittest
from unittest.mock import MagicMock, patch
import datetime

from services.market_data import (
    YFinanceClient,
    MarketDataClient,
    MarketQuote,
    DailyBar,
    get_all_tradable_tickers,
    RateLimiter,
    rate_limited_batch_iterator,
    TOP_LIQUID_US_TICKERS,
)
from services.crypto_data import CryptoDataClient, DEFAULT_CRYPTO_UNIVERSE
from services.trading212 import Trading212Client, AccountCash, Position, OrderResult
from services.obsidian import ObsidianClient, TradeLogRecord
from services.ai_analyzer import GroqClient, AIAnalysisResult, GROQ_FALLBACK_MODELS
from services.telegram_bot import TelegramNotifier, TelegramBotManager
from services.signal_tracker import SignalTracker
from services.data_guard import DataGuard, DATA_UNAVAILABLE
from services.risk_engine import DeterministicRiskEngine, RiskAssessmentResult
from services.kill_switch import KillSwitch, SystemState
from services.market_radar import (
    MarketRadar,
    MarketEventType,
    TimeframeTrend,
    RadarAssetScanResult,
    MultiTimeframeAnalysis,
    MultiLevelMarketRadar,
    Level1Candidate,
    Level3Finalist,
    MultiLevelPipelineResult,
)
from services.opportunity_scorer import OpportunityScorer, ScoredOpportunity
from services.trade_filter import WhyNotTradeEngine, VetoResult
from services.portfolio_brain import PortfolioBrain, CorrelationAssessment
from services.trade_autopsy import TradeAutopsyEngine, TradeAutopsyReport, DecisionOutcomeQuadrant
from services.universe_manager import UniverseManager, UniverseCacheData, AssetMetadata
from services.news_sentiment import EconomicCalendar, NewsSentimentEngine, MacroEvent, EventImpact, MacroSentimentSummary
from services.market_regime import MarketRegimeEngine, MarketRegime, RegimeClassification
from services.portfolio_exposure import PortfolioExposureEngine, ExposureAssessment
from services.execution_quality import ExecutionQualityEngine, ExecutionMetrics
from services.audit_trail import DecisionAuditTrail, DecisionAuditRecord
from services.confidence_tracker import ConfidenceTracker, ConfidenceBracketReport
from services.research_lab import ResearchLabEngine, ResearchHypothesis, HypothesisStage
from services.strategy_tournament import StrategyTournamentEngine, TournamentStrategyStats
from services.shadow_trading import ShadowTradingEngine, ShadowTrade
from strategy import DipAndMovingAverageStrategy, TradeDecision
from config import Settings


class TestTradingBotComponents(unittest.TestCase):

    def setUp(self):
        self.config = Settings(
            t212_api_key="mock_t212_key",
            t212_secret_key="mock_t212_secret",
            t212_environment="demo",
            groq_api_key="gsk_mock_groq_key",
            groq_model="llama-3.3-70b-versatile",
            telegram_bot_token="mock_bot_token",
            telegram_chat_id="123456789",
            obsidian_rest_api_key="mock_obsidian_key",
            watchlist_tickers="AAPL_US_EQ,MSFT_US_EQ,LLOY_UK_EQ",
            buy_allocation_value=25.0,
            dip_threshold_percent=2.0,
            sma_short_period=10,
            sma_long_period=50
        )

    def test_yfinance_ticker_normalization(self):
        self.assertEqual(YFinanceClient.normalize_ticker("AAPL_US_EQ"), "AAPL")
        self.assertEqual(YFinanceClient.normalize_ticker("BRK.B_US_EQ"), "BRK-B")
        self.assertEqual(YFinanceClient.normalize_ticker("BF.B_US_EQ"), "BF-B")
        self.assertEqual(YFinanceClient.normalize_ticker("BRK.B"), "BRK-B")
        self.assertEqual(YFinanceClient.normalize_ticker("VUAGl_EQ"), "VUAG.L")
        self.assertEqual(YFinanceClient.normalize_ticker("VWCEd_EQ"), "VWCE.DE")
        self.assertEqual(YFinanceClient.normalize_ticker("IQQHd_EQ"), "IQQH.DE")
        self.assertEqual(YFinanceClient.normalize_ticker("ENRd_EQ"), "ENR.DE")
        self.assertEqual(YFinanceClient.normalize_ticker("LLOY_UK_EQ"), "LLOY.L")
        self.assertEqual(YFinanceClient.normalize_ticker("SAP_DE_EQ"), "SAP.DE")
        self.assertEqual(YFinanceClient.normalize_ticker("BNP_FR_EQ"), "BNP.PA")
        self.assertEqual(YFinanceClient.normalize_ticker("ASML_NL_EQ"), "ASML.AS")
        self.assertEqual(YFinanceClient.normalize_ticker("TSLA"), "TSLA")
        # Also test extract_yahoo_symbol alias
        self.assertEqual(YFinanceClient.extract_yahoo_symbol("VUAGl_EQ"), "VUAG.L")

    def test_crypto_data_client(self):
        self.assertEqual(CryptoDataClient.normalize_crypto_symbol("BTCUSDT"), "BTC/USDT")
        self.assertEqual(CryptoDataClient.normalize_crypto_symbol("ETH/USDT"), "ETH/USDT")
        self.assertEqual(CryptoDataClient.normalize_crypto_symbol("SOLUSD"), "SOL/USD")

        client = CryptoDataClient()
        universe = client.get_all_tradable_crypto(limit=5)
        self.assertEqual(len(universe), 5)
        self.assertIn("BTC/USDT", universe)

        mock_quote = MarketQuote(
            ticker="BTC/USDT",
            price=60000.0,
            open=59000.0,
            high=61000.0,
            low=58500.0,
            volume=100000,
            latest_trading_day="2026-08-25",
            previous_close=59000.0,
            change=1000.0,
            change_percent=1.69
        )
        with patch.object(client, "get_quote", return_value=mock_quote):
            q = client.get_quote("BTC/USDT")
            self.assertEqual(q.price, 60000.0)
            self.assertEqual(q.ticker, "BTC/USDT")

        # Test balance retrieval without credentials (returns None in simulation mode)
        self.assertFalse(client.has_credentials())
        self.assertIsNone(client.get_balance())

        # Test Coinbase balance retrieval with credentials
        coinbase_client = CryptoDataClient(exchange_id="coinbase", api_key="cb_api_key", secret="cb_secret")
        self.assertTrue(coinbase_client.has_credentials())
        mock_cb = MagicMock()
        mock_cb.fetch_balance.return_value = {
            "USD": {"free": 1000.0, "total": 1000.0},
            "USDC": {"free": 500.0, "total": 500.0},
            "USDT": {"free": 200.0, "total": 200.0},
            "total": {"USD": 3500.0}
        }
        coinbase_client._exchange = mock_cb
        balance = coinbase_client.get_balance()
        self.assertIsNotNone(balance)
        self.assertEqual(balance.free, 1700.0)  # 1000 + 500 + 200
        self.assertEqual(balance.total, 3500.0)
        self.assertEqual(balance.invested, 1800.0)  # 3500 - 1700

    def test_dynamic_market_scanner_tickers(self):
        # 1. Test fallback to top liquid list when web is mocked to fail
        with patch("services.market_data.fetch_sp500_tickers_from_web", side_effect=Exception("Web down")):
            tickers = get_all_tradable_tickers(source="sp500_nasdaq", limit=10)
            self.assertEqual(len(tickers), 10)
            self.assertIn("AAPL_US_EQ", tickers)
            self.assertIn("MSFT_US_EQ", tickers)

        # 2. Test Trading 212 instruments discovery
        mock_t212 = MagicMock()
        mock_t212.get_instruments.return_value = [
            {"ticker": "AAPL_US_EQ", "type": "EQUITY"},
            {"ticker": "NVDA_US_EQ", "type": "EQUITY"},
            {"ticker": "EURUSD", "type": "FOREX"}
        ]
        t212_tickers = get_all_tradable_tickers(source="trading212", t212_client=mock_t212)
        self.assertEqual(t212_tickers, ["AAPL_US_EQ", "NVDA_US_EQ"])

    def test_rate_limiter_and_batch_iterator(self):
        items = ["A", "B", "C"]
        generator = rate_limited_batch_iterator(items, max_per_second=100.0)
        results = list(generator)
        self.assertEqual(results, ["A", "B", "C"])

    def test_get_quotes_batch(self):
        client = YFinanceClient()
        mock_quote = MarketQuote(
            ticker="AAPL_US_EQ",
            price=180.0,
            open=185.0,
            high=186.0,
            low=179.5,
            volume=50000000,
            latest_trading_day="2026-08-25",
            previous_close=185.0,
            change=-5.0,
            change_percent=-2.70
        )
        with patch.object(client, "get_quote", return_value=mock_quote):
            quotes = client.get_quotes_batch(["AAPL_US_EQ", "MSFT_US_EQ"], max_workers=2)
            self.assertEqual(len(quotes), 2)
            self.assertIn("AAPL_US_EQ", quotes)
            self.assertIn("MSFT_US_EQ", quotes)

    def test_trading212_basic_auth_headers(self):
        api_key = "my_api_key"
        secret_key = "my_secret_key"
        expected_raw = f"{api_key}:{secret_key}"
        expected_b64 = base64.b64encode(expected_raw.encode("utf-8")).decode("utf-8")
        expected_auth_header = f"Basic {expected_b64}"

        client = Trading212Client(api_key=api_key, secret_key=secret_key)
        headers = client._get_headers()
        self.assertEqual(headers["Authorization"], expected_auth_header)
        self.assertEqual(client._session.headers.get("Authorization"), expected_auth_header)

        client_alias = Trading212Client(api_key_id="alias_key", secret_key="alias_secret")
        expected_alias_b64 = base64.b64encode(b"alias_key:alias_secret").decode("utf-8")
        self.assertEqual(client_alias._get_headers()["Authorization"], f"Basic {expected_alias_b64}")

        client_single = Trading212Client(api_key="standalone_token_123")
        headers_single = client_single._get_headers()
        self.assertEqual(headers_single["Authorization"], "standalone_token_123")

    def test_groq_endpoint_and_headers(self):
        client = GroqClient(
            api_key="gsk_test_key_12345",
            model="llama-3.3-70b-versatile"
        )
        self.assertEqual(client.url, "https://api.groq.com/openai/v1/chat/completions")
        headers = client._get_headers()
        self.assertEqual(headers["Authorization"], "Bearer gsk_test_key_12345")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertTrue(client.is_configured())

    def test_groq_fallback_routing_on_429_or_404(self):
        fallback_list = ["llama-3.1-8b-instant"]
        client = GroqClient(
            api_key="gsk_mock_key",
            model="failing-model",
            fallback_models=fallback_list
        )

        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.ok = False
        mock_429.text = "Rate limit reached"

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.ok = True
        mock_200.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"sentiment": "BULLISH", "confidence_score": 85, "summary": "Groq fallback model recovered analysis.", "catalysts": "Volume breakout"}'
                }
            }]
        }

        with patch.object(client._session, "post", side_effect=[mock_429, mock_200]) as mock_post:
            result = client.analyze_trade_signal(
                ticker="AAPL_US_EQ",
                price=180.0,
                action="BUY",
                reason="Dip below SMA",
                indicators={"current_price": 180.0}
            )
            self.assertEqual(mock_post.call_count, 2)
            self.assertEqual(result.sentiment, "BULLISH")
            self.assertEqual(result.confidence_score, 85)
            self.assertEqual(result.model_used, "llama-3.1-8b-instant")
            self.assertIn("Groq fallback model recovered", result.summary)

    def test_groq_ai_analyzer_mock(self):
        client = GroqClient(api_key="gsk_mock_key", model="llama-3.3-70b-versatile")
        self.assertTrue(client.is_configured())

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"sentiment": "BULLISH", "confidence_score": 88, "summary": "Great dip opportunity on Groq.", "catalysts": "10-day SMA rebound"}'
                }
            }]
        }
        mock_response.raise_for_status.return_value = None

        with patch.object(client._session, "post", return_value=mock_response):
            analysis = client.analyze_trade_signal(
                ticker="AAPL_US_EQ",
                price=180.0,
                action="BUY",
                reason="Dip below SMA",
                indicators={"current_price": 180.0}
            )
            self.assertEqual(analysis.sentiment, "BULLISH")
            self.assertEqual(analysis.confidence_score, 88)
            self.assertIn("Great dip opportunity on Groq", analysis.summary)

    def test_telegram_notifier_mock(self):
        notifier = TelegramNotifier(bot_token="12345:ABCDE", chat_id="987654321")
        self.assertTrue(notifier.is_configured())

        mock_post = MagicMock()
        mock_post.return_value.raise_for_status.return_value = None

        with patch.object(notifier._session, "post", return_value=mock_post()):
            record = TradeLogRecord(
                timestamp=datetime.datetime(2026, 8, 24, 14, 30, 0),
                ticker="AAPL_US_EQ",
                action="BUY",
                price=185.50,
                quantity=0.1347,
                order_value=25.00,
                strategy_reason="Price dropped 2.5% below 10-day SMA",
                execution_success=True,
                order_id="ORD-998877",
                broker_status="FILLED",
                environment="demo"
            )
            ai_analysis = AIAnalysisResult(
                summary="Strong technical support.",
                sentiment="BULLISH",
                confidence_score=85,
                catalysts="Moving average support"
            )
            success = notifier.send_trade_alert(record, ai_analysis)
            self.assertTrue(success)

    def test_telegram_cycle_summary_mock(self):
        notifier = TelegramNotifier(bot_token="12345:ABCDE", chat_id="987654321")
        self.assertTrue(notifier.is_configured())

        mock_post = MagicMock()
        mock_post.return_value.raise_for_status.return_value = None

        with patch.object(notifier._session, "post", return_value=mock_post()):
            cash = AccountCash(free=500.0, total=1000.0, invested=500.0, ppl=25.0, result=25.0)
            signals = [{"ticker": "BTC/USDT", "action": "BUY", "price": 60000.0, "reason": "SMA dip"}]
            success = notifier.send_cycle_summary(
                evaluated_count=60,
                executed_count=1,
                cash=cash,
                dry_run=True,
                scan_mode=True,
                target_market="all",
                stocks_evaluated=50,
                crypto_evaluated=10,
                signals_summary=signals,
                duration_seconds=5.2
            )
            self.assertTrue(success)

    def test_strategy_buy_signal_on_dip(self):
        mock_market = MagicMock()
        mock_market.get_quote.return_value = MarketQuote(
            ticker="AAPL_US_EQ",
            price=180.0,
            open=185.0,
            high=186.0,
            low=179.5,
            volume=50000000,
            latest_trading_day="2026-08-24",
            previous_close=185.0,
            change=-5.0,
            change_percent=-2.70
        )
        mock_market.calculate_sma.side_effect = lambda ticker, period: 190.0 if period == 10 else 188.0

        mock_broker = MagicMock()
        cash = AccountCash(free=500.0, total=1000.0, invested=500.0, ppl=20.0, result=20.0)

        strategy = DipAndMovingAverageStrategy(self.config, mock_market, mock_broker)
        decision = strategy.evaluate_ticker("AAPL_US_EQ", cash, None)

        self.assertEqual(decision.action, "BUY")
        self.assertTrue(decision.should_execute)
        self.assertAlmostEqual(decision.target_value, 25.0)
        self.assertGreater(decision.indicators["dip_percentage"], 2.0)
        self.assertIn("BUY Signal Triggered", decision.reason)

    def test_strategy_hold_on_insufficient_cash(self):
        mock_market = MagicMock()
        mock_market.get_quote.return_value = MarketQuote(
            ticker="AAPL_US_EQ",
            price=180.0,
            open=185.0,
            high=186.0,
            low=179.5,
            volume=50000000,
            latest_trading_day="2026-08-24",
            previous_close=185.0,
            change=-5.0,
            change_percent=-2.70
        )
        mock_market.calculate_sma.return_value = 190.0

        mock_broker = MagicMock()
        # Free cash is only $10, less than $25 buy allocation
        cash = AccountCash(free=10.0, total=500.0, invested=490.0, ppl=5.0, result=5.0)

        strategy = DipAndMovingAverageStrategy(self.config, mock_market, mock_broker)
        decision = strategy.evaluate_ticker("AAPL_US_EQ", cash, None)

        self.assertEqual(decision.action, "HOLD")
        self.assertFalse(decision.should_execute)
        self.assertIn("Insufficient free cash", decision.reason)

    def test_obsidian_markdown_formatting_with_ai(self):
        obsidian = ObsidianClient(
            api_key="test_key",
            vault_folder="Trading-Logs"
        )
        record = TradeLogRecord(
            timestamp=datetime.datetime(2026, 8, 24, 14, 30, 0),
            ticker="AAPL_US_EQ",
            action="BUY",
            price=185.50,
            quantity=0.1347,
            order_value=25.00,
            strategy_reason="Price dropped 2.5% below 10-day SMA",
            execution_success=True,
            order_id="ORD-998877",
            broker_status="FILLED",
            environment="demo",
            extra_meta={
                "ai_sentiment": "BULLISH",
                "ai_confidence": 90,
                "ai_summary": "High-confidence reversal setup on Groq."
            }
        )

        table_row, callout = obsidian._format_trade_entry_markdown(record)

        self.assertIn("AAPL_US_EQ", table_row)
        self.assertIn("BUY", table_row)
        self.assertIn("$185.50", table_row)

        self.assertIn("> [!success] Trade Entry: 🟢 BUY `AAPL_US_EQ`", callout)
        self.assertIn("Price dropped 2.5% below 10-day SMA", callout)
        self.assertIn("🤖 **AI Analysis:** `BULLISH` (90% confidence)", callout)

    def test_obsidian_log_market_scan_cycle(self):
        obsidian = ObsidianClient(
            api_key="test_key",
            vault_folder="Trading-Logs"
        )
        cash = AccountCash(free=500.0, total=1000.0, invested=500.0, ppl=25.0, result=25.0)
        signals = [{
            "ticker": "AAPL_US_EQ",
            "price": 180.0,
            "short_sma": 186.0,
            "long_sma": 182.5,
            "dip_percentage": 3.23,
            "action": "BUY",
            "reason": "Price dropped 3.2% below SMA"
        }]

        written_content = {}

        def mock_get_content(path):
            return written_content.get(path, None)

        def mock_write_file(path, content):
            written_content[path] = content
            return True

        with patch.object(obsidian, "get_file_content", side_effect=mock_get_content), \
             patch.object(obsidian, "write_file", side_effect=mock_write_file):
            now = datetime.datetime(2026, 8, 25, 1, 10, 0)
            vault_path = obsidian.log_market_scan_cycle(
                timestamp=now,
                market_target="stocks",
                cash=cash,
                open_positions_count=2,
                evaluated_signals=signals,
                dry_run=True,
                scan_mode=True
            )
            self.assertIn("Trading-Logs/Trades-Log-2026-08-25.md", vault_path)
            content = written_content[vault_path]
            self.assertIn("tags:", content)
            self.assertIn("stocks", content)
            self.assertIn("AAPL_US_EQ", content)
            self.assertIn("3.23%", content)
            self.assertIn("Trading 212", content)
            self.assertIn("Free: `$500.00`", content)

    def test_signal_tracker_sqlite(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            tracker = SignalTracker(db_path=db_path)
            old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=30)
            sig_id = tracker.record_signal(
                ticker="AAPL_US_EQ",
                market_type="stock",
                signal_type="BUY",
                price_at_signal=180.0,
                indicators={"short_sma": 186.0},
                notes="SMA dip test",
                timestamp=old_time
            )
            self.assertGreater(sig_id, 0)

            # Test pending signals query
            pending = tracker.get_pending_signals(older_than_hours=24.0, market_type="stock")
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["ticker"], "AAPL_US_EQ")

            # Forward-test outcome with higher current price (WIN)
            mock_market = MagicMock()
            mock_market.get_quote.return_value = MarketQuote(
                ticker="AAPL_US_EQ",
                price=189.0,  # +5% profit
                open=185.0,
                high=190.0,
                low=184.0,
                volume=1000000,
                latest_trading_day="2026-08-25",
                previous_close=180.0,
                change=9.0,
                change_percent=5.0
            )
            mock_crypto = MagicMock()

            outcomes = tracker.evaluate_past_signals(
                market_client=mock_market,
                crypto_client=mock_crypto,
                stock_min_age_hours=24.0,
                crypto_min_age_hours=4.0
            )
            self.assertEqual(len(outcomes), 1)
            self.assertEqual(outcomes[0]["outcome"], "WIN")
            self.assertEqual(outcomes[0]["pnl_percent"], 5.0)

            # Test accuracy stats
            stats = tracker.get_accuracy_stats()
            self.assertEqual(stats["total_signals"], 1)
            self.assertEqual(stats["evaluated_count"], 1)
            self.assertEqual(stats["wins"], 1)
            self.assertEqual(stats["losses"], 0)
            self.assertEqual(stats["win_rate_percent"], 100.0)

        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_obsidian_log_learning_journal(self):
        obsidian = ObsidianClient(
            api_key="test_key",
            vault_folder="Trading-Logs"
        )
        stats = {
            "win_rate_percent": 80.0,
            "evaluated_count": 10,
            "wins": 8,
            "losses": 2,
            "neutrals": 0,
            "avg_pnl_percent": 3.45,
            "avg_win_percent": 4.80,
            "avg_loss_percent": -1.95
        }
        outcomes = [{
            "id": 1,
            "signal_time": "2026-08-24T12:00:00",
            "ticker": "BTC/USDT",
            "market_type": "crypto",
            "signal_type": "BUY",
            "entry_price": 60000.0,
            "exit_price": 62500.0,
            "pnl_percent": 4.17,
            "outcome": "WIN"
        }]

        written = {}

        def mock_get(path):
            return written.get(path, None)

        def mock_write(path, content):
            written[path] = content
            return True

        with patch.object(obsidian, "get_file_content", side_effect=mock_get), \
             patch.object(obsidian, "write_file", side_effect=mock_write):
            path = obsidian.log_learning_journal(outcomes, stats)
            self.assertIn("Learning-Journal.md", path)
            journal_text = written[path]
            self.assertIn("learning-log", journal_text)
            self.assertIn("win_rate: 80.0%", journal_text)
            self.assertIn("BTC/USDT", journal_text)
            self.assertIn("#win", journal_text)

    def test_data_guard_validation(self):
        # 1. Test quote sanitization with invalid / missing values
        raw_quote = {
            "ticker": "AAPL_US_EQ",
            "price": 180.5,
            "open": None,
            "high": 170.0,
            "low": 185.0,  # Invalid: low > high
            "volume": "invalid",
            "change_percent": 1.25
        }
        sanitized = DataGuard.sanitize_quote(raw_quote)
        self.assertEqual(sanitized["ticker"], "AAPL_US_EQ")
        self.assertEqual(sanitized["price"], 180.5)
        self.assertEqual(sanitized["open"], DATA_UNAVAILABLE)
        # Coherence check tripped -> high and low set to DATA_UNAVAILABLE
        self.assertEqual(sanitized["high"], DATA_UNAVAILABLE)
        self.assertEqual(sanitized["low"], DATA_UNAVAILABLE)
        self.assertEqual(sanitized["volume"], DATA_UNAVAILABLE)
        self.assertEqual(sanitized["change_percent"], 1.25)

        # 2. Test indicator sanitization
        raw_indicators = {
            "short_sma": 185.0,
            "long_sma": -10.0,  # Invalid negative SMA
            "rsi": 150.0,       # Invalid out of [0, 100]
            "dip_percentage": 2.5
        }
        clean_ind = DataGuard.sanitize_indicators(raw_indicators)
        self.assertEqual(clean_ind["short_sma"], 185.0)
        self.assertEqual(clean_ind["long_sma"], DATA_UNAVAILABLE)
        self.assertEqual(clean_ind["rsi"], DATA_UNAVAILABLE)
        self.assertEqual(clean_ind["dip_percentage"], 2.5)

        # 3. Test price anomaly detection
        is_anom, msg = DataGuard.check_price_anomaly(current_price=300.0, previous_price=150.0, max_jump_percent=50.0)
        self.assertTrue(is_anom)
        self.assertIn("100.0%", msg)

        is_normal, _ = DataGuard.check_price_anomaly(current_price=155.0, previous_price=150.0, max_jump_percent=50.0)
        self.assertFalse(is_normal)

    def test_deterministic_risk_engine(self):
        engine = DeterministicRiskEngine(
            max_risk_per_trade_percent=1.5,
            max_position_size_percent=15.0,
            min_order_value=10.0,
            default_risk_reward_ratio=2.0,
            atr_multiplier_sl=1.5,
            atr_multiplier_tp=3.0
        )
        cash = AccountCash(free=500.0, total=2000.0, invested=1500.0, ppl=0.0, result=0.0)
        indicators = {"atr": 4.0, "support": 175.0, "resistance": 200.0}

        # 1. Test normal approved BUY trade
        res = engine.evaluate_trade_risk(
            ticker="AAPL_US_EQ",
            action="BUY",
            current_price=180.0,
            portfolio_cash=cash,
            indicators=indicators,
            opportunity_score=1.0,
            max_order_override=50.0
        )
        self.assertTrue(res.is_approved)
        self.assertEqual(res.entry_price, 180.0)
        self.assertLess(res.stop_loss_price, 180.0)
        self.assertGreater(res.take_profit_price, 180.0)
        self.assertGreater(res.risk_reward_ratio, 1.0)
        self.assertLessEqual(res.allocated_value, 50.0)

        # 2. Test rejection when cash is below minimum order value
        low_cash = AccountCash(free=5.0, total=2000.0, invested=1995.0, ppl=0.0, result=0.0)
        res_low = engine.evaluate_trade_risk(
            ticker="AAPL_US_EQ",
            action="BUY",
            current_price=180.0,
            portfolio_cash=low_cash,
            indicators=indicators
        )
        self.assertFalse(res_low.is_approved)
        self.assertIn("below minimum threshold", res_low.rejection_reason)

    def test_kill_switch_lifecycle(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            state_file = tf.name

        try:
            # Recreate kill switch with temporary state file
            KillSwitch._instance = None
            ks = KillSwitch(max_consecutive_api_errors=3, state_file=state_file)
            self.assertEqual(ks.state, SystemState.NORMAL)

            can_buy, _ = ks.can_execute_orders("BUY")
            self.assertTrue(can_buy)

            # Record 2 errors -> still NORMAL
            ks.record_api_error("Timeout 1")
            ks.record_api_error("Timeout 2")
            self.assertEqual(ks.state, SystemState.NORMAL)

            # 3rd error -> trips SAFE_MODE
            ks.record_api_error("Timeout 3")
            self.assertEqual(ks.state, SystemState.SAFE_MODE)

            can_buy_safe, buy_reason = ks.can_execute_orders("BUY")
            self.assertFalse(can_buy_buy := can_buy_safe)
            self.assertIn("SAFE MODE", buy_reason)

            # Sells/risk-reduction are still allowed in SAFE_MODE
            can_sell, _ = ks.can_execute_orders("SELL")
            self.assertTrue(can_sell)

            # Reset Kill Switch -> back to NORMAL
            ks.reset()
            self.assertEqual(ks.state, SystemState.NORMAL)
            self.assertTrue(ks.can_execute_orders("BUY")[0])

            # Trigger Manual HALT
            ks.trigger_kill("Emergency HALT triggered")
            self.assertEqual(ks.state, SystemState.HALTED)
            self.assertFalse(ks.can_execute_orders("BUY")[0])
            self.assertFalse(ks.can_execute_orders("SELL")[0])

        finally:
            KillSwitch._instance = None
            if os.path.exists(state_file):
                os.remove(state_file)

    def test_market_radar_event_detection_and_confluence(self):
        radar = MarketRadar()

        # Build mock 25-day daily bar series
        base_date = datetime.date(2026, 8, 1)
        history = []
        for i in range(25):
            d = base_date + datetime.timedelta(days=i)
            # Upward trending series ending with a strong breakout candle
            price = 100.0 + (i * 1.5)
            vol = 100000 if i < 24 else 250000  # 2.5x volume surge on last day
            high = price + 2.0 if i < 24 else price + 8.0  # Volatility surge
            low = price - 1.0
            history.append(DailyBar(date=d, open=price - 0.5, high=high, low=low, close=price + 1.0, volume=vol))

        quote = MarketQuote(
            ticker="NVDA_US_EQ",
            price=140.0,
            open=136.0,
            high=144.0,
            low=135.0,
            volume=250000,
            latest_trading_day="2026-08-25",
            previous_close=135.2,
            change=4.8,
            change_percent=3.5
        )

        scan_res = radar.analyze_asset("NVDA_US_EQ", market_type="stock", quote=quote, history=history)
        self.assertEqual(scan_res.ticker, "NVDA_US_EQ")
        self.assertGreaterEqual(len(scan_res.detected_events), 1)

        event_types = [e.event_type for e in scan_res.detected_events]
        # Breakout or Volume Spike or Volatility Spike detected
        self.assertTrue(
            MarketEventType.BREAKOUT in event_types
            or MarketEventType.VOLUME_SPIKE in event_types
            or MarketEventType.MOMENTUM_SURGE in event_types
        )
        self.assertTrue(scan_res.timeframe_analysis.is_confluent_bullish)
        self.assertGreaterEqual(scan_res.timeframe_analysis.confluence_score, 80.0)

    def test_opportunity_scorer_grading_and_ranking(self):
        scorer = OpportunityScorer()

        # High quality setup (A+)
        high_quality_analysis = MultiTimeframeAnalysis(
            macro_1d=TimeframeTrend.BULLISH,
            intermediate_1h=TimeframeTrend.BULLISH,
            micro_5m=TimeframeTrend.BULLISH,
            is_confluent_bullish=True,
            is_confluent_bearish=False,
            confluence_score=95.0
        )
        high_scan = RadarAssetScanResult(
            ticker="BTC/USDT",
            market_type="crypto",
            current_price=65000.0,
            detected_events=[],
            timeframe_analysis=high_quality_analysis,
            indicators={"rsi": 60.0, "dip_percentage": 2.5, "short_sma": 64000.0, "long_sma": 60000.0},
            volume_surge_multiplier=2.1,
            volatility_atr_ratio=1.5
        )
        scored_high = scorer.score_asset(high_scan)
        self.assertIn(scored_high.grade, ["A+", "A"])
        self.assertGreaterEqual(scored_high.composite_score, 75.0)

        # Mediocre setup
        low_quality_analysis = MultiTimeframeAnalysis(
            macro_1d=TimeframeTrend.BEARISH,
            intermediate_1h=TimeframeTrend.BEARISH,
            micro_5m=TimeframeTrend.BEARISH,
            is_confluent_bullish=False,
            is_confluent_bearish=True,
            confluence_score=10.0
        )
        low_scan = RadarAssetScanResult(
            ticker="DUMP/USDT",
            market_type="crypto",
            current_price=1.0,
            detected_events=[],
            timeframe_analysis=low_quality_analysis,
            indicators={"rsi": 25.0, "dip_percentage": 15.0, "short_sma": 1.2, "long_sma": 1.5},
            volume_surge_multiplier=0.4,
            volatility_atr_ratio=4.5
        )
        scored_low = scorer.score_asset(low_scan)
        self.assertIn(scored_low.grade, ["C", "D"])

        # Ranking
        ranked = scorer.rank_opportunities([low_scan, high_scan], top_n=5, min_score=40.0)
        self.assertEqual(len(ranked), 1)  # Only high_scan passes min_score 40.0
        self.assertEqual(ranked[0].ticker, "BTC/USDT")

    def test_why_not_trade_engine_vetos(self):
        engine = WhyNotTradeEngine(
            min_resistance_atr_buffer=1.5,
            min_risk_reward_ratio=1.5,
            max_overbought_rsi=80.0
        )

        # 1. Test Resistance Proximity Veto (Resistance is only $1 away, but 1.5x ATR is $6)
        indicators_res_block = {
            "atr": 4.0,
            "resistance": 101.0,
            "rsi": 55.0,
            "short_sma": 98.0,
            "long_sma": 95.0
        }
        veto_res = engine.evaluate_trade_filters(
            ticker="XYZ_US_EQ",
            action="BUY",
            current_price=100.0,
            indicators=indicators_res_block,
            risk_reward_ratio=2.0
        )
        self.assertTrue(veto_res.should_veto)
        self.assertTrue(any("resistance" in r.lower() for r in veto_res.veto_reasons))

        # 2. Test Low Risk:Reward Veto (1:1.1 is below 1:1.5)
        indicators_rr = {"atr": 2.0, "resistance": 120.0, "rsi": 50.0}
        veto_rr = engine.evaluate_trade_filters(
            ticker="ABC_US_EQ",
            action="BUY",
            current_price=100.0,
            indicators=indicators_rr,
            risk_reward_ratio=1.1
        )
        self.assertTrue(veto_rr.should_veto)
        self.assertTrue(any("risk:reward" in r.lower() for r in veto_rr.veto_reasons))

        # 3. Test Extreme Overbought RSI Veto (RSI 85 > 80)
        indicators_rsi = {"atr": 2.0, "resistance": 150.0, "rsi": 85.0}
        veto_rsi = engine.evaluate_trade_filters(
            ticker="PUMP_US_EQ",
            action="BUY",
            current_price=100.0,
            indicators=indicators_rsi,
            risk_reward_ratio=2.5
        )
        self.assertTrue(veto_rsi.should_veto)
        self.assertTrue(any("overbought" in r.lower() for r in veto_rsi.veto_reasons))

        # 4. Clean setup passes all defense filters
        indicators_clean = {
            "atr": 2.0,
            "resistance": 115.0,  # $15 away > 1.5 * $2 = $3
            "rsi": 55.0,
            "short_sma": 102.0,
            "long_sma": 95.0
        }
        pass_res = engine.evaluate_trade_filters(
            ticker="WINNER_US_EQ",
            action="BUY",
            current_price=100.0,
            indicators=indicators_clean,
            risk_reward_ratio=2.5
        )
        self.assertFalse(pass_res.should_veto)
        self.assertGreaterEqual(len(pass_res.passed_checks), 3)

    def test_portfolio_brain_correlation_and_allocation(self):
        brain = PortfolioBrain(
            max_correlation_threshold=0.85,
            max_highly_correlated_count=2,
            max_crypto_allocation_percent=40.0,
            max_single_asset_percent=20.0
        )

        # 1. Test Pearson returns correlation math
        series_a = [100.0, 102.0, 101.0, 105.0, 107.0, 106.0, 110.0]
        series_b = [50.0, 51.0, 50.5, 52.5, 53.5, 53.0, 55.0]  # Positive correlation
        series_c = [20.0, 19.0, 20.5, 18.0, 17.5, 18.5, 16.0]  # Negative correlation

        corr_pos = brain.calculate_returns_correlation(series_a, series_b)
        corr_neg = brain.calculate_returns_correlation(series_a, series_c)
        self.assertGreater(corr_pos, 0.80)
        self.assertLess(corr_neg, -0.70)

        # 2. Test Allocation Cap Veto
        stock_cash = AccountCash(free=500.0, total=1000.0, invested=500.0, ppl=0.0, result=0.0)
        crypto_cash = AccountCash(free=50.0, total=500.0, invested=450.0, ppl=0.0, result=0.0)

        # Trying to add crypto when crypto already has $450 out of $1500 (30%) + $200 (13.3%) = 43.3% > 40%
        alloc_res = brain.evaluate_entry_risk(
            candidate_ticker="SOL/USDT",
            market_type="crypto",
            target_value=200.0,
            current_positions={},
            stock_cash=stock_cash,
            crypto_cash=crypto_cash,
            candidate_history_closes=series_a
        )
        self.assertFalse(alloc_res.is_approved)
        self.assertIn("exceed max limit", alloc_res.rejection_reason)

        # 3. Approved Entry
        app_res = brain.evaluate_entry_risk(
            candidate_ticker="AAPL_US_EQ",
            market_type="stock",
            target_value=50.0,
            current_positions={},
            stock_cash=stock_cash,
            crypto_cash=crypto_cash,
            candidate_history_closes=series_a
        )
        self.assertTrue(app_res.is_approved)
        self.assertIsNone(app_res.rejection_reason)

    def test_trade_autopsy_diagnostics(self):
        engine = TradeAutopsyEngine()

        # 1. Test Loss Autopsy: Resistance Trap
        loss_res_data = {
            "id": 101,
            "ticker": "AAPL_US_EQ",
            "market_type": "stock",
            "signal_type": "BUY",
            "entry_price": 180.0,
            "exit_price": 175.0,
            "pnl_percent": -2.78,
            "outcome": "LOSS",
            "indicators": {
                "resistance": 181.0,
                "atr": 3.0,
                "rsi": 60.0
            }
        }
        rep_loss = engine.analyze_outcome(loss_res_data)
        self.assertEqual(rep_loss.outcome, "LOSS")
        self.assertEqual(rep_loss.root_cause, "RESISTANCE_TRAP")
        self.assertIn("overhead resistance", rep_loss.actionable_lesson)

        # 2. Test Loss Autopsy: Overbought Exhaustion
        loss_rsi_data = {
            "id": 102,
            "ticker": "BTC/USDT",
            "market_type": "crypto",
            "signal_type": "BUY",
            "entry_price": 70000.0,
            "exit_price": 66000.0,
            "pnl_percent": -5.71,
            "outcome": "LOSS",
            "indicators": {
                "rsi": 82.0,
                "resistance": 80000.0,
                "atr": 1500.0
            }
        }
        rep_rsi = engine.analyze_outcome(loss_rsi_data)
        self.assertEqual(rep_rsi.root_cause, "OVERBOUGHT_EXHAUSTION")
        self.assertIn("RSI > 75", rep_rsi.actionable_lesson)

        # 3. Test Win Autopsy: Trend Momentum Expansion
        win_data = {
            "id": 103,
            "ticker": "NVDA_US_EQ",
            "market_type": "stock",
            "signal_type": "BUY",
            "entry_price": 130.0,
            "exit_price": 140.0,
            "pnl_percent": 7.69,
            "outcome": "WIN",
            "indicators": {
                "short_sma": 132.0,
                "long_sma": 120.0,
                "rsi": 62.0
            }
        }
        rep_win = engine.analyze_outcome(win_data)
        self.assertEqual(rep_win.outcome, "WIN")
        self.assertEqual(rep_win.root_cause, "TREND_MOMENTUM_EXPANSION")
        self.assertIn("moving average", rep_win.actionable_lesson)

    def test_obsidian_log_trade_autopsies(self):
        obsidian = ObsidianClient(api_key="mock_key", vault_folder="Trading-Logs")
        written = {}

        def mock_get(path):
            return written.get(path, None)

        def mock_write(path, content):
            written[path] = content
            return True

        rep = TradeAutopsyReport(
            signal_id=201,
            ticker="TSLA_US_EQ",
            market_type="stock",
            signal_type="BUY",
            entry_price=220.0,
            exit_price=240.0,
            pnl_percent=9.09,
            outcome="WIN",
            root_cause="TREND_MOMENTUM_EXPANSION",
            primary_driver="Golden cross momentum follow-through",
            actionable_lesson="Trend alignment maximizes win rate.",
            rule_recommendation="Continue prioritizing Golden Cross setups."
        )

        with patch.object(obsidian, "get_file_content", side_effect=mock_get), \
             patch.object(obsidian, "write_file", side_effect=mock_write):
            path = obsidian.log_trade_autopsies([rep])
            self.assertIn("Learning-Journal.md", path)
            content = written[path]
            self.assertIn("Autopsy #201: TSLA_US_EQ", content)
            self.assertIn("TREND_MOMENTUM_EXPANSION", content)
            self.assertIn("Trend alignment maximizes win rate.", content)

    def test_telegram_morning_and_evening_briefs(self):
        tg = TelegramNotifier(bot_token="mock_token", chat_id="12345")
        sent_messages = []

        with patch.object(tg, "send_message", side_effect=lambda msg: (sent_messages.append(msg), True)[1]):
            # 1. Test Morning Brief
            stock_cash = AccountCash(free=500.0, total=2500.0, invested=2000.0, ppl=50.0, result=0.0)
            crypto_cash = AccountCash(free=100.0, total=500.0, invested=400.0, ppl=0.0, result=0.0)
            top_setups = [{
                "ticker": "BTC/USDT",
                "market_type": "crypto",
                "price": 80000.0,
                "composite_score": 85.0,
                "grade": "A+",
                "key_events": ["Triple Timeframe Alignment"]
            }]
            mb_ok = tg.send_morning_brief(
                stock_cash=stock_cash,
                crypto_cash=crypto_cash,
                top_radar_setups=top_setups,
                macro_sentiment="BULLISH REGIME"
            )
            self.assertTrue(mb_ok)
            self.assertIn("MORNING INTELLIGENCE BRIEF", sent_messages[0])
            self.assertIn("BULLISH REGIME", sent_messages[0])
            self.assertIn("BTC/USDT", sent_messages[0])

            # 2. Test Evening Brief
            eod_ok = tg.send_evening_brief(
                stock_cash=stock_cash,
                crypto_cash=crypto_cash,
                daily_stats={"win_rate_percent": 75.0, "wins": 3, "losses": 1, "evaluated_count": 4, "avg_pnl_percent": 2.45},
                autopsy_lessons=["Wait for volume confirmation on breakouts"],
                open_positions=["AAPL_US_EQ"]
            )
            self.assertTrue(eod_ok)
            self.assertIn("END-OF-DAY INTELLIGENCE BRIEF", sent_messages[1])
            self.assertIn("75.0%", sent_messages[1])
            self.assertIn("AAPL_US_EQ", sent_messages[1])

    def test_interactive_ask_command(self):
        tg = TelegramNotifier(bot_token="mock_token", chat_id="12345")
        ai_client = GroqClient(api_key="mock_groq_key")

        mock_answer = "KODA Analysis: Current risk levels are optimal with 65% cash reserve."
        with patch.object(ai_client, "answer_market_query", return_value=mock_answer), \
             patch.object(tg, "send_message", return_value=True):
            resp = tg.handle_ask_command(
                question="What is our cash posture?",
                ai_client=ai_client,
                portfolio_context={"stock_free": 1000.0, "stock_total": 1500.0},
                radar_context=[],
                lessons=[]
            )
            self.assertEqual(resp, mock_answer)

    def test_obsidian_morning_and_evening_briefs(self):
        obsidian = ObsidianClient(api_key="mock_key", vault_folder="Trading-Logs")
        written = {}

        def mock_get(path):
            return written.get(path, None)

        def mock_write(path, content):
            written[path] = content
            return True

        with patch.object(obsidian, "get_file_content", side_effect=mock_get), \
             patch.object(obsidian, "write_file", side_effect=mock_write):
            # 1. Morning Brief Log
            mb_path = obsidian.log_morning_brief(
                top_radar_setups=[{"grade": "A", "ticker": "NVDA_US_EQ", "market_type": "stock", "price": 135.0, "composite_score": 80.0, "key_events": ["Breakout"]}],
                macro_sentiment="BULLISH",
                stock_cash=AccountCash(free=500.0, total=2500.0, invested=2000.0, ppl=50.0, result=0.0)
            )
            self.assertIn(mb_path, written)
            self.assertIn("Morning Intelligence Brief", written[mb_path])
            self.assertIn("NVDA_US_EQ", written[mb_path])

            # 2. Evening Brief Log
            eod_path = obsidian.log_evening_brief(
                daily_stats={"win_rate_percent": 80.0, "wins": 4, "losses": 1, "evaluated_count": 5, "avg_pnl_percent": 3.10},
                stock_cash=AccountCash(free=500.0, total=2500.0, invested=2000.0, ppl=50.0, result=0.0),
                autopsy_lessons=["Enforce dynamic stop loss buffer"]
            )
            self.assertIn("End-of-Day Intelligence Brief", written[eod_path])
            self.assertIn("80.0%", written[eod_path])

    def test_universe_manager_caching_and_filtering(self):
        import tempfile
        temp_cache = os.path.join(tempfile.gettempdir(), "test_universe_cache.json")
        if os.path.exists(temp_cache):
            os.remove(temp_cache)

        try:
            mgr = UniverseManager(cache_file_path=temp_cache, cache_ttl_hours=1.0)

            # Test fallback syncing
            crypto_universe = mgr.sync_crypto_universe()
            self.assertGreaterEqual(len(crypto_universe), 5)
            self.assertTrue(any("BTC" in c for c in crypto_universe))

            stock_universe = mgr.sync_stocks_universe()
            self.assertGreaterEqual(len(stock_universe), 5)
            self.assertTrue(any("AAPL" in s for s in stock_universe))

            # Test caching round-trip
            cache_data = mgr.sync_universe(target="all", force_refresh=True)
            self.assertTrue(os.path.exists(temp_cache))
            self.assertGreater(len(cache_data.stocks), 0)
            self.assertGreater(len(cache_data.crypto), 0)

            # Verify active universe load from cache
            loaded = mgr.get_active_universe(target="crypto", limit=3)
            self.assertEqual(len(loaded), 3)

        finally:
            if os.path.exists(temp_cache):
                os.remove(temp_cache)

    def test_multilevel_market_radar_pipeline(self):
        radar = MultiLevelMarketRadar()

        test_universe = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AAPL_US_EQ", "NVDA_US_EQ"]

        def mock_crypto_quote(*args, **kwargs):
            sym = kwargs.get("symbol") or kwargs.get("ticker") or (args[0] if args else "CRYPTO")
            return MarketQuote(
                ticker=sym,
                price=100.0,
                open=98.0,
                high=105.0,
                low=95.0,
                volume=500000,
                latest_trading_day="2026-08-25",
                previous_close=97.0,
                change=3.0,
                change_percent=3.5
            )

        def mock_stock_quote(*args, **kwargs):
            sym = kwargs.get("ticker") or kwargs.get("symbol") or (args[0] if args else "STOCK")
            return MarketQuote(
                ticker=sym,
                price=150.0,
                open=148.0,
                high=152.0,
                low=148.0,
                volume=2000000,
                latest_trading_day="2026-08-25",
                previous_close=147.0,
                change=3.0,
                change_percent=2.0
            )

        mock_bars = [
            DailyBar(date="2026-08-20", open=95.0, high=100.0, low=94.0, close=98.0, volume=10000),
            DailyBar(date="2026-08-21", open=98.0, high=102.0, low=97.0, close=101.0, volume=15000),
            DailyBar(date="2026-08-22", open=101.0, high=105.0, low=100.0, close=104.0, volume=20000),
        ]

        with patch.object(radar.crypto_client, "get_quote", side_effect=mock_crypto_quote), \
             patch.object(radar.stock_client, "get_quote", side_effect=mock_stock_quote), \
             patch.object(radar.crypto_client, "fetch_ohlcv", return_value=mock_bars), \
             patch.object(radar.stock_client, "get_daily_history", return_value=mock_bars):

            res: MultiLevelPipelineResult = radar.run_multi_level_scan(
                universe=test_universe,
                target_market="all",
                ai_client=None,
                l1_limit=3,
                l2_limit=2,
                l3_limit=2
            )

            self.assertEqual(res.total_screened_level1, 5)
            self.assertEqual(res.passed_level1_count, 3)
            self.assertLessEqual(res.passed_level2_count, 2)
            self.assertLessEqual(len(res.level3_finalists), 2)
            self.assertIn(res.level3_finalists[0].recommendation, ["PROCEED", "WATCH", "VETO"])

    def test_economic_calendar_and_risk_windows(self):
        cal = EconomicCalendar(risk_window_minutes=30)
        sentiment_engine = NewsSentimentEngine(calendar=cal)

        # 1. Normal time (outside risk window)
        normal_time = datetime.datetime(2026, 8, 25, 10, 0, tzinfo=datetime.timezone.utc)
        in_risk, event, delta = cal.is_in_risk_window(current_time=normal_time)
        self.assertFalse(in_risk)
        self.assertIsNone(event)

        # 2. Add custom event and test active risk window
        test_event = MacroEvent(
            event_id="TEST_CPI",
            title="US Consumer Price Index",
            event_type="CPI",
            scheduled_time=datetime.datetime(2026, 8, 25, 12, 30, tzinfo=datetime.timezone.utc),
            impact=EventImpact.HIGH
        )
        cal.add_custom_event(test_event)

        # Test timestamp 10 minutes prior to release
        near_time = datetime.datetime(2026, 8, 25, 12, 20, tzinfo=datetime.timezone.utc)
        in_risk_active, active_ev, delta_active = cal.is_in_risk_window(current_time=near_time, buffer_minutes=30)
        self.assertTrue(in_risk_active)
        self.assertIsNotNone(active_ev)
        self.assertEqual(active_ev.event_id, "TEST_CPI")
        self.assertAlmostEqual(delta_active, 10.0, places=1)

        # 3. Test sentiment bias de-risking
        summary = sentiment_engine.evaluate_macro_sentiment()
        self.assertIn(summary.sentiment_label, ["BULLISH_RISK_ON", "BEARISH_RISK_OFF", "NEUTRAL"])
        self.assertGreater(len(summary.key_drivers), 0)

    def test_market_regime_classification_and_rules(self):
        engine = MarketRegimeEngine()

        # 1. High Volatility (ATR ratio >= 2.0)
        high_vol_regime = engine.classify_regime(atr_ratio=2.2)
        self.assertEqual(high_vol_regime.primary_regime, MarketRegime.HIGH_VOLATILITY)
        self.assertFalse(high_vol_regime.can_trade_breakouts)
        self.assertEqual(high_vol_regime.position_size_multiplier, 0.5)
        self.assertEqual(high_vol_regime.stop_loss_atr_multiplier, 2.5)

        # 2. Risk-Off selloff
        risk_off_regime = engine.classify_regime(spy_change_pct=-1.5, btc_change_pct=-3.2, atr_ratio=1.0)
        self.assertEqual(risk_off_regime.primary_regime, MarketRegime.RISK_OFF)
        self.assertFalse(risk_off_regime.can_trade_breakouts)
        self.assertFalse(risk_off_regime.can_trade_trend_continuation)
        self.assertEqual(risk_off_regime.position_size_multiplier, 0.5)

        # 3. Trending Bull / Risk-On
        bull_regime = engine.classify_regime(spy_change_pct=0.8, btc_change_pct=2.0, rsi_composite=65.0)
        self.assertEqual(bull_regime.primary_regime, MarketRegime.TRENDING_BULL)
        self.assertTrue(bull_regime.can_trade_breakouts)
        self.assertTrue(bull_regime.can_trade_trend_continuation)
        self.assertEqual(bull_regime.position_size_multiplier, 1.0)

        # 4. Ranging Compression
        ranging_regime = engine.classify_regime(spy_change_pct=0.05, btc_change_pct=-0.2, atr_ratio=0.9, rsi_composite=48.0)
        self.assertEqual(ranging_regime.primary_regime, MarketRegime.RANGING)
        self.assertFalse(ranging_regime.can_trade_breakouts)
        self.assertEqual(ranging_regime.position_size_multiplier, 0.75)

    def test_portfolio_exposure_and_beta_limits(self):
        engine = PortfolioExposureEngine(
            max_sector_exposure_pct=40.0,
            max_portfolio_beta=1.80,
            max_crypto_exposure_pct=40.0
        )

        # Existing tech position ($1,800 on $5,000 equity = 36%)
        existing_positions = {
            "NVDA_US_EQ": Position(ticker="NVDA_US_EQ", quantity=15.0, average_price=120.0, current_price=120.0, ppl=0.0)
        }

        # 1. Proposed $500 AAPL entry in same Tech sector -> total $2,300 / $5,000 = 46% (Exceeds 40% cap)
        over_sector = engine.evaluate_exposure_risk(
            candidate_ticker="AAPL_US_EQ",
            target_value=500.0,
            current_positions=existing_positions,
            total_equity=5000.0,
            free_cash=2000.0
        )
        self.assertFalse(over_sector.is_approved)
        self.assertIn("Sector exposure limit breached", over_sector.rejection_reason)

        # 2. Approved entry in a different sector (Healthcare - JNJ)
        approved_entry = engine.evaluate_exposure_risk(
            candidate_ticker="JNJ_US_EQ",
            target_value=400.0,
            current_positions=existing_positions,
            total_equity=5000.0,
            free_cash=2000.0
        )
        self.assertTrue(approved_entry.is_approved)
        self.assertEqual(approved_entry.candidate_sector, "Healthcare")
        self.assertIsNone(approved_entry.rejection_reason)
        self.assertLessEqual(approved_entry.portfolio_beta, 1.80)

    def test_execution_quality_slippage_and_latency(self):
        import tempfile
        temp_db = os.path.join(tempfile.gettempdir(), "test_exec_quality.db")
        if os.path.exists(temp_db):
            os.remove(temp_db)

        try:
            engine = ExecutionQualityEngine(db_path=temp_db)

            # 1. Test BUY slippage calculation (Filled higher = positive adverse slippage)
            pct, bps = engine.calculate_slippage(action="BUY", expected_price=100.0, filled_price=100.25)
            self.assertEqual(pct, 0.25)
            self.assertEqual(bps, 25.0)

            # 2. Record execution
            rec = engine.record_execution(
                order_id="ORD-12345",
                ticker="AAPL_US_EQ",
                action="BUY",
                market_type="stock",
                expected_price=100.0,
                filled_price=100.25,
                filled_quantity=10.0,
                latency_ms=125.5,
                fee_usd=1.50
            )
            self.assertEqual(rec.order_id, "ORD-12345")
            self.assertEqual(rec.slippage_bps, 25.0)
            self.assertEqual(rec.execution_latency_ms, 125.5)

            # 3. Summary metrics
            summary = engine.get_execution_summary()
            self.assertEqual(summary["total_executions"], 1)
            self.assertEqual(summary["avg_slippage_bps"], 25.0)
            self.assertEqual(summary["total_fees_usd"], 1.50)

        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_decision_audit_trail_logging_and_retrieval(self):
        import tempfile
        temp_db = os.path.join(tempfile.gettempdir(), "test_audit_trail.db")
        if os.path.exists(temp_db):
            os.remove(temp_db)

        try:
            audit = DecisionAuditTrail(db_path=temp_db)

            # Log decision chain
            record = audit.log_decision_chain(
                ticker="BTC/USDT",
                market_type="crypto",
                regime="TRENDING_BULL",
                quant_score=88.5,
                macro_sentiment="BULLISH_RISK_ON",
                ai_sentiment="BULLISH",
                ai_confidence=85,
                risk_approved=True,
                exposure_approved=True,
                execution_status="EXECUTED",
                rejection_reason=None,
                trace_details={"stage": "Complete Pass"}
            )
            self.assertIsNotNone(record.id)
            self.assertEqual(record.ticker, "BTC/USDT")
            self.assertEqual(record.regime, "TRENDING_BULL")
            self.assertEqual(record.execution_status, "EXECUTED")

            # Retrieve traces
            traces = audit.get_recent_traces(limit=5)
            self.assertEqual(len(traces), 1)
            self.assertEqual(traces[0].ticker, "BTC/USDT")
            self.assertTrue(traces[0].risk_approved)
            self.assertEqual(traces[0].trace_details.get("stage"), "Complete Pass")

        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_trade_autopsy_counterfactual_and_quadrants(self):
        engine = TradeAutopsyEngine()

        # 1. Good Decision / Win
        good_win = engine.analyze_outcome({
            "id": 101,
            "ticker": "BTC/USDT",
            "market_type": "crypto",
            "signal_type": "BUY",
            "entry_price": 60000.0,
            "exit_price": 63000.0,
            "pnl_percent": 5.0,
            "outcome": "WIN",
            "indicators": {"short_sma": 61000.0, "long_sma": 58000.0, "rsi": 60.0, "atr": 1500.0}
        })
        self.assertEqual(good_win.decision_outcome_quadrant, DecisionOutcomeQuadrant.GOOD_DECISION_WIN.value)
        self.assertEqual(good_win.process_quality_score, 90.0)

        # 2. Bad Decision / Loss (Chasing into resistance and high RSI)
        bad_loss = engine.analyze_outcome({
            "id": 102,
            "ticker": "SOL/USDT",
            "market_type": "crypto",
            "signal_type": "BUY",
            "entry_price": 140.0,
            "exit_price": 130.0,
            "pnl_percent": -7.14,
            "outcome": "LOSS",
            "indicators": {"short_sma": 135.0, "long_sma": 130.0, "rsi": 82.0, "atr": 4.0}
        })
        self.assertEqual(bad_loss.decision_outcome_quadrant, DecisionOutcomeQuadrant.BAD_DECISION_LOSS.value)
        self.assertEqual(bad_loss.root_cause, "OVERBOUGHT_EXHAUSTION")
        self.assertEqual(bad_loss.process_quality_score, 25.0)

        # 3. Good Decision / Loss (Volatility whipsaw with wider SL counterfactual test)
        whipsaw_loss = engine.analyze_outcome({
            "id": 103,
            "ticker": "ETH/USDT",
            "market_type": "crypto",
            "signal_type": "BUY",
            "entry_price": 3000.0,
            "exit_price": 2940.0,
            "pnl_percent": -2.0,
            "outcome": "LOSS",
            "indicators": {"short_sma": 3020.0, "long_sma": 2980.0, "rsi": 55.0, "atr": 30.0}
        })
        self.assertEqual(whipsaw_loss.decision_outcome_quadrant, DecisionOutcomeQuadrant.GOOD_DECISION_LOSS.value)
        self.assertEqual(whipsaw_loss.counterfactual_wider_sl_result, "WIN")

    def test_confidence_tracker_calibration(self):
        import tempfile
        temp_db = os.path.join(tempfile.gettempdir(), "test_conf_tracker.db")
        if os.path.exists(temp_db):
            os.remove(temp_db)

        try:
            tracker = ConfidenceTracker(db_path=temp_db)

            # Record predictions in 80-89% bracket
            tracker.record_prediction(signal_id=1, ticker="NVDA_US_EQ", confidence_score=85)
            tracker.record_prediction(signal_id=2, ticker="AAPL_US_EQ", confidence_score=82)
            tracker.record_prediction(signal_id=3, ticker="MSFT_US_EQ", confidence_score=88)

            # Record outcomes: 2 Wins, 1 Loss -> 66.7% Win Rate
            tracker.record_outcome(signal_id=1, is_win=True)
            tracker.record_outcome(signal_id=2, is_win=True)
            tracker.record_outcome(signal_id=3, is_win=False)

            report = tracker.get_calibration_report()
            self.assertEqual(report["total_evaluated"], 3)

            b80 = next(b for b in report["brackets"] if b.bracket_name == "80-89%")
            self.assertEqual(b80.total_signals, 3)
            self.assertEqual(b80.wins, 2)
            self.assertEqual(b80.losses, 1)
            self.assertAlmostEqual(b80.actual_win_rate_pct, 66.7, places=1)

        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_research_lab_hypothesis_pipeline(self):
        import tempfile
        temp_db = os.path.join(tempfile.gettempdir(), "test_research_lab.db")
        if os.path.exists(temp_db):
            os.remove(temp_db)

        try:
            lab = ResearchLabEngine(db_path=temp_db)

            # 1. Create hypothesis
            hyp = lab.create_hypothesis(
                hypothesis_id="HYP-TEST-01",
                title="Dynamic Volatility Breakout",
                description="Test hypothesis"
            )
            self.assertEqual(hyp.stage, HypothesisStage.PROPOSED)

            # 2. Advance through Backtest
            ok, hyp, _ = lab.advance_stage(hyp.hypothesis_id, backtest_sharpe=1.65, backtest_profit_factor=1.60)
            self.assertTrue(ok)
            self.assertEqual(hyp.stage, HypothesisStage.BACKTEST_PASSED)

            # 3. Advance through Walk-Forward
            ok, hyp, _ = lab.advance_stage(hyp.hypothesis_id, walk_forward_efficiency=0.75)
            self.assertTrue(ok)
            self.assertEqual(hyp.stage, HypothesisStage.WALK_FORWARD_PASSED)

            # 4. Advance through Shadow Trading -> Full Approval
            ok, hyp, _ = lab.advance_stage(hyp.hypothesis_id, shadow_trades_count=6, shadow_win_rate_pct=66.7)
            self.assertTrue(ok)
            self.assertEqual(hyp.stage, HypothesisStage.APPROVED)
            self.assertEqual(hyp.approval_status, "APPROVED_FOR_PRODUCTION")

        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_strategy_tournament_ranking(self):
        tournament = StrategyTournamentEngine()

        # 1. Test ranking in TRENDING_BULL (Breakout and Trend continuation boosted)
        bull_ranked = tournament.rank_strategies(current_regime="TRENDING_BULL")
        self.assertGreater(len(bull_ranked), 0)
        self.assertIn(bull_ranked[0].archetype, ["BREAKOUT", "MEAN_REVERSION", "TREND_FOLLOWING"])

        # 2. Test ranking in RANGING (Mean Reversion boosted, Breakouts penalized)
        ranging_ranked = tournament.rank_strategies(current_regime="RANGING")
        self.assertEqual(ranging_ranked[0].archetype, "MEAN_REVERSION")

        # Verify allocation percentages sum to 100%
        total_alloc = sum(s.recommended_allocation_pct for s in ranging_ranked)
        self.assertAlmostEqual(total_alloc, 100.0, places=0)

    def test_shadow_trading_sandbox_execution(self):
        import tempfile
        temp_db = os.path.join(tempfile.gettempdir(), "test_shadow.db")
        if os.path.exists(temp_db):
            os.remove(temp_db)

        try:
            shadow = ShadowTradingEngine(db_path=temp_db)

            # 1. Open shadow trade
            trade = shadow.open_shadow_trade(
                ticker="BTC/USDT",
                market_type="crypto",
                action="BUY",
                signal_price=60000.0,
                current_tick_price=60010.0,
                quantity=0.1,
                stop_loss=58000.0,
                take_profit=64000.0
            )
            self.assertEqual(trade.status, "OPEN")
            self.assertEqual(trade.simulated_fill_price, 60010.0)

            # 2. Update price tick below Stop Loss -> should trigger CLOSED_SL
            updated = shadow.update_ticks({"BTC/USDT": 57900.0})
            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0].status, "CLOSED_SL")
            self.assertLess(updated[0].realized_pnl_pct, 0.0)

            # 3. Performance summary
            summary = shadow.get_performance_summary()
            self.assertEqual(summary["total_closed_trades"], 1)
            self.assertEqual(summary["losses"], 1)

        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_telegram_command_handler_and_authorization(self):
        # 1. Test Authorization
        manager = TelegramBotManager(allowed_user_id="12345678")
        self.assertTrue(manager.is_authorized("12345678"))
        self.assertFalse(manager.is_authorized("99999999"))

        # Unauthorized dispatch
        unauth_reply = manager.dispatch_command("/status", user_id="99999999")
        self.assertIn("Unauthorized Access Denied", unauth_reply)

        # 2. Test Help Command
        help_reply = manager.dispatch_command("/help", user_id="12345678")
        self.assertIn("KODA Institutional Management Bot", help_reply)
        self.assertIn("/status", help_reply)
        self.assertIn("/stats", help_reply)

        # 3. Test Status & Stats Commands
        status_reply = manager.dispatch_command("/status", user_id="12345678")
        self.assertIn("KODA SYSTEM STATUS & REGIME", status_reply)

        stats_reply = manager.dispatch_command("/stats", user_id="12345678")
        self.assertIn("KODA TRADE AUTOPSY 2.0 & STATS", stats_reply)

        research_reply = manager.dispatch_command("/research", user_id="12345678")
        self.assertIn("KODA RESEARCH LAB & TOURNAMENT", research_reply)

        # 4. Test Mode Switching
        mode_paper = manager.dispatch_command("/mode PAPER", user_id="12345678")
        self.assertEqual(manager.execution_mode, "PAPER")
        self.assertIn("switched to PAPER", mode_paper)

        mode_live_req = manager.dispatch_command("/mode LIVE", user_id="12345678")
        self.assertIn("SAFETY CONFIRMATION REQUIRED", mode_live_req)

        # 5. Test Live Trading Toggle with Confirmation
        live_toggle_on = manager.dispatch_command("/trade_live ON", user_id="12345678")
        self.assertIn("SAFETY CONFIRMATION REQUIRED", live_toggle_on)
        self.assertFalse(manager.live_trading_enabled)

        # Confirm Live Trading
        live_confirm = manager.dispatch_command("/trade_live CONFIRM_LIVE_TRADING", user_id="12345678")
        self.assertIn("LIVE TRADING ENGAGED", live_confirm)
        self.assertTrue(manager.live_trading_enabled)
        self.assertEqual(manager.execution_mode, "LIVE")

        # Disable Live Trading
        live_off = manager.dispatch_command("/trade_live OFF", user_id="12345678")
        self.assertIn("Live trading disabled", live_off)
        self.assertFalse(manager.live_trading_enabled)
        self.assertEqual(manager.execution_mode, "PAPER")


if __name__ == "__main__":
    unittest.main()
