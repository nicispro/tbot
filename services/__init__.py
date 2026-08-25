"""
Services package initialization.
Exports core API clients for market data (Stocks & Crypto), broker execution, AI analysis (Groq),
Telegram alerts, journal logging, automated signal outcome tracking, and KODA Institutional Architecture engines.
"""

from .market_data import (
    YFinanceClient,
    MarketDataClient,
    AlphaVantageClient,
    MarketQuote,
    DailyBar,
    get_all_tradable_tickers,
    RateLimiter,
    rate_limited_batch_iterator,
    TOP_LIQUID_US_TICKERS,
)
from .crypto_data import CryptoDataClient, DEFAULT_CRYPTO_UNIVERSE
from .trading212 import Trading212Client, OrderResult, AccountCash, Position
from .obsidian import ObsidianClient, TradeLogRecord
from .obsidian_exporter import ObsidianVaultExporter
from .ai_analyzer import GroqClient, AIAnalyzerClient, OpenRouterClient, AIAnalysisResult
from .telegram_bot import TelegramNotifier, TelegramBotManager
from .signal_tracker import SignalTracker, SignalRecord
from .data_guard import DataGuard, DATA_UNAVAILABLE
from .risk_engine import DeterministicRiskEngine, RiskAssessmentResult
from .kill_switch import KillSwitch, SystemState
from .market_radar import (
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
from .opportunity_scorer import OpportunityScorer, ScoredOpportunity
from .trade_filter import WhyNotTradeEngine, VetoResult
from .portfolio_brain import PortfolioBrain, CorrelationAssessment
from .trade_autopsy import TradeAutopsyEngine, TradeAutopsyReport, DecisionOutcomeQuadrant
from .universe_manager import (
    UniverseManager,
    MarketUniverseManager,
    AssetMetadata,
    UniverseCacheData,
    DEFAULT_CRYPTO_UNIVERSE,
    DEFAULT_STOCKS_UNIVERSE,
)
from .market_regime import MarketRegime, RegimeClassification, MarketRegimeEngine
from .portfolio_exposure import PortfolioExposureEngine, ExposureAssessment, SECTOR_MAP, BETA_MAP
from .execution_quality import ExecutionQualityEngine, ExecutionMetrics
from .audit_trail import DecisionAuditTrail, DecisionAuditRecord
from .confidence_tracker import ConfidenceTracker, ConfidenceBracketReport
from .research_lab import ResearchLabEngine, ResearchHypothesis, HypothesisStage, KODAResearchLab
from .strategy_tournament import StrategyTournamentEngine, TournamentStrategyStats
from .shadow_trading import ShadowTradingEngine, ShadowTrade
from .trader_loop import ContinuousTraderLoop

__all__ = [
    "ContinuousTraderLoop",
    "YFinanceClient",
    "MarketDataClient",
    "AlphaVantageClient",
    "MarketQuote",
    "DailyBar",
    "get_all_tradable_tickers",
    "RateLimiter",
    "rate_limited_batch_iterator",
    "TOP_LIQUID_US_TICKERS",
    "CryptoDataClient",
    "DEFAULT_CRYPTO_UNIVERSE",
    "Trading212Client",
    "OrderResult",
    "AccountCash",
    "Position",
    "ObsidianClient",
    "ObsidianVaultExporter",
    "TradeLogRecord",
    "GroqClient",
    "AIAnalyzerClient",
    "OpenRouterClient",
    "AIAnalysisResult",
    "TelegramNotifier",
    "TelegramBotManager",
    "SignalTracker",
    "SignalRecord",
    "DataGuard",
    "DATA_UNAVAILABLE",
    "DeterministicRiskEngine",
    "RiskAssessmentResult",
    "KillSwitch",
    "SystemState",
    "MarketRadar",
    "MarketEventType",
    "TimeframeTrend",
    "RadarAssetScanResult",
    "MultiTimeframeAnalysis",
    "MultiLevelMarketRadar",
    "Level1Candidate",
    "Level3Finalist",
    "MultiLevelPipelineResult",
    "OpportunityScorer",
    "ScoredOpportunity",
    "WhyNotTradeEngine",
    "VetoResult",
    "PortfolioBrain",
    "CorrelationAssessment",
    "TradeAutopsyEngine",
    "TradeAutopsyReport",
    "DecisionOutcomeQuadrant",
    "UniverseManager",
    "MarketUniverseManager",
    "DEFAULT_CRYPTO_UNIVERSE",
    "DEFAULT_STOCKS_UNIVERSE",
    "AssetMetadata",
    "UniverseCacheData",
    "EconomicCalendar",
    "NewsSentimentEngine",
    "MacroEvent",
    "EventImpact",
    "MacroSentimentSummary",
    "MarketRegime",
    "RegimeClassification",
    "MarketRegimeEngine",
    "PortfolioExposureEngine",
    "ExposureAssessment",
    "SECTOR_MAP",
    "BETA_MAP",
    "ExecutionQualityEngine",
    "ExecutionMetrics",
    "DecisionAuditTrail",
    "DecisionAuditRecord",
    "ConfidenceTracker",
    "ConfidenceBracketReport",
    "ResearchLabEngine",
    "KODAResearchLab",
    "ResearchHypothesis",
    "HypothesisStage",
    "StrategyTournamentEngine",
    "TournamentStrategyStats",
    "ShadowTradingEngine",
    "ShadowTrade",
]
