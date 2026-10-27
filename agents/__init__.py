"""
Forex Swarm Agents Module.
"""
from agents.base_agent import BaseAgent
from agents.data_integrity_agent import DataIntegrityAgent
from agents.emergency_halt_agent import EmergencyHaltAgent
from agents.regime_classifier_agent import RegimeClassifierAgent
from agents.news_sentiment_agent import NewsSentimentAgent
from agents.macro_calendar_agent import MacroCalendarAgent
from agents.microstructure_agent import MicrostructureAgent
from agents.pattern_recognition_agent import PatternRecognitionAgent
from agents.quant_indicator_agent import QuantIndicatorAgent
from agents.decision_maker_agent import DecisionMakerAgent
from agents.portfolio_risk_agent import PortfolioRiskAgent
from agents.risk_manager_agent import RiskManagerAgent
from agents.execution_router_agent import ExecutionRouterAgent
from agents.audit_feedback_agent import AuditFeedbackAgent
from agents.performance_attribution_agent import PerformanceAttributionAgent
from agents.cross_pair_scanner_agent import CrossPairScannerAgent

__all__ = [
    "BaseAgent",
    "DataIntegrityAgent",
    "EmergencyHaltAgent",
    "RegimeClassifierAgent",
    "NewsSentimentAgent",
    "MacroCalendarAgent",
    "MicrostructureAgent",
    "PatternRecognitionAgent",
    "QuantIndicatorAgent",
    "DecisionMakerAgent",
    "PortfolioRiskAgent",
    "RiskManagerAgent",
    "ExecutionRouterAgent",
    "AuditFeedbackAgent",
    "PerformanceAttributionAgent",
    "CrossPairScannerAgent",
]
