"""
Swarm Orchestrator.
Coordinates the execution pipeline across all 14 agents and 4 tiers:
Tier 0: Safety & Data Governance (DataIntegrity, EmergencyHalt, RegimeClassifier)
Tier 1: Perception & Market Intelligence (NewsSentiment, MacroCalendar, Microstructure)
Tier 2: Technical & Quantitative Reasoning (PatternRecognition, QuantIndicator)
Tier 3: Strategy & Risk Governance (DecisionMaker, PortfolioRisk, RiskManager [Absolute Veto + Time Machine])
Tier 4: Execution, Telemetry & Evolution (ExecutionRouter [Sequential Entry Timer], MockBroker, AuditFeedback, PerformanceAttribution)
+ Cross-Pair 28-Universe Scanner & Real-Time Alert Dispatcher.
"""
from typing import Dict, Any, List, Optional
from config import config
from core.bus import SwarmEventBus
from core.gemini_explainer import GeminiExplainer
from core.alert_dispatcher import global_alert_dispatcher
from core.calibration_validator import global_calibration_validator
from data.feed import MarketDataFeed
from engine.mock_broker import MockBrokerEngine

from agents import (
    DataIntegrityAgent,
    EmergencyHaltAgent,
    RegimeClassifierAgent,
    NewsSentimentAgent,
    MacroCalendarAgent,
    MicrostructureAgent,
    PatternRecognitionAgent,
    QuantIndicatorAgent,
    DecisionMakerAgent,
    PortfolioRiskAgent,
    RiskManagerAgent,
    ExecutionRouterAgent,
    AuditFeedbackAgent,
    PerformanceAttributionAgent,
    CrossPairScannerAgent
)

class SwarmOrchestrator:
    def __init__(self):
        self.bus = SwarmEventBus()
        self.blackboard = self.bus.blackboard
        self.broker = MockBrokerEngine(initial_balance=config.account_initial_balance)
        self.data_feed = MarketDataFeed(tracked_pairs=config.tracked_pairs)
        self.explainer = GeminiExplainer()

        # Instantiate all 14 Agents
        self.data_integrity_agent = DataIntegrityAgent(self.bus, config)
        self.emergency_halt_agent = EmergencyHaltAgent(self.bus, config)
        self.regime_classifier_agent = RegimeClassifierAgent(self.bus, config)
        
        self.news_sentiment_agent = NewsSentimentAgent(self.bus, config)
        self.macro_calendar_agent = MacroCalendarAgent(self.bus, config)
        self.microstructure_agent = MicrostructureAgent(self.bus, config)
        
        self.pattern_recognition_agent = PatternRecognitionAgent(self.bus, config)
        self.quant_indicator_agent = QuantIndicatorAgent(self.bus, config)
        
        self.decision_maker_agent = DecisionMakerAgent(self.bus, config)
        self.portfolio_risk_agent = PortfolioRiskAgent(self.bus, config)
        self.risk_manager_agent = RiskManagerAgent(self.bus, config, initial_equity=config.account_initial_balance)
        
        self.execution_router_agent = ExecutionRouterAgent(self.bus, self.broker, config)
        self.audit_feedback_agent = AuditFeedbackAgent(self.bus, config)
        self.performance_attribution_agent = PerformanceAttributionAgent(self.bus, config)
        self.cross_pair_scanner_agent = CrossPairScannerAgent(self.bus, config)

        self.current_timeframe = "1M"

    async def run_cycle(self, pair: str = "EUR/USD", timeframe: str = "1M", binary_payout_pct: float = 87.0) -> Dict[str, Any]:
        """
        Executes one complete end-to-end swarm cognition cycle for the given pair & timeframe.
        """
        self.current_timeframe = timeframe
        base, quote = pair.split("/")

        # 1. Fetch Market Data & Ticks
        tick = self.data_feed.generate_tick(pair)
        candles = self.data_feed.generate_candles(pair, count=50, timeframe=timeframe, end_price=tick.bid)
        await self.blackboard.update_tick(tick)
        self.blackboard.candles[pair] = candles

        # 2. TIER 0: Data Integrity & Health
        health_report = await self.data_integrity_agent.validate_tick(tick)
        if not health_report.feed_healthy:
            # Trigger Emergency Halt if corrupt
            await self.emergency_halt_agent.trigger_kill_switch(
                f"CORRUPT_FEED on {pair}: {health_report.rationale}",
                triggered_by="DATA_INTEGRITY_AGENT"
            )

        # 3. TIER 0: Regime Classification
        regime_report = await self.regime_classifier_agent.classify_regime(pair, candles)

        # 4. TIER 1: Perception & Market Intelligence
        sentiment_base = await self.news_sentiment_agent.analyze_sentiment(base)
        sentiment_quote = await self.news_sentiment_agent.analyze_sentiment(quote)
        macro_base = await self.macro_calendar_agent.evaluate_economic_schedule(base)
        macro_quote = await self.macro_calendar_agent.evaluate_economic_schedule(quote)
        micro_report = await self.microstructure_agent.analyze_tick(tick)

        # 5. TIER 2: Technical & Quantitative Reasoning
        pattern_report = await self.pattern_recognition_agent.analyze_patterns(pair, candles)
        quant_report = await self.quant_indicator_agent.calculate_indicators(pair, candles)

        # 6. TIER 3: Strategy & Proposal Formulation
        trade_proposal = await self.decision_maker_agent.generate_proposal(pair, binary_payout_pct=binary_payout_pct)

        # 7. TIER 3: Portfolio Exposure Check & Risk Manager Evaluation
        exposure = await self.portfolio_risk_agent.evaluate_portfolio_heat(pair, trade_proposal.direction)
        risk_evaluation = await self.risk_manager_agent.evaluate_proposal(trade_proposal)

        # 8. TIER 4: Execution Router (if approved)
        order_execution = None
        if risk_evaluation.approved:
            order_execution = await self.execution_router_agent.execute_approved_trade(risk_evaluation)
            self.risk_manager_agent.update_equity(self.broker.equity)

        # 9. Narrative Synthesis via Explainer (Gemini / Institutional Template)
        explanation = self.explainer.generate_explanation(
            pair=pair,
            proposal=trade_proposal.model_dump(mode="json"),
            risk_eval=risk_evaluation.model_dump(mode="json"),
            regime_report=regime_report.model_dump(mode="json"),
            timeframe=timeframe
        )

        # 10. Format Candles for Real-Time Canvas / Lightweight Charts
        chart_candles = [
            {
                "time": int(c.timestamp.timestamp()),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            }
            for c in candles
        ]

        return {
            "pair": pair,
            "timeframe": timeframe,
            "tick": tick.model_dump(mode="json"),
            "candles": chart_candles,
            "health": health_report.model_dump(mode="json"),
            "regime": regime_report.model_dump(mode="json"),
            "sentiment_base": sentiment_base.model_dump(mode="json"),
            "sentiment_quote": sentiment_quote.model_dump(mode="json"),
            "macro_base": macro_base.model_dump(mode="json"),
            "macro_quote": macro_quote.model_dump(mode="json"),
            "microstructure": micro_report.model_dump(mode="json"),
            "pattern": pattern_report.model_dump(mode="json"),
            "quant": quant_report.model_dump(mode="json"),
            "proposal": trade_proposal.model_dump(mode="json"),
            "portfolio_exposure": exposure.model_dump(mode="json"),
            "risk_evaluation": risk_evaluation.model_dump(mode="json"),
            "execution": order_execution.model_dump(mode="json") if order_execution else None,
            "explanation": explanation,
            "broker": {
                "balance": round(self.broker.balance, 2),
                "equity": round(self.broker.equity, 2),
                "open_orders_count": len(self.broker.open_orders)
            },
            "calibration": global_calibration_validator.evaluate_out_of_sample_edge(),
            "alerts": global_alert_dispatcher.get_recent_alerts(5)
        }

    async def scan_cross_pairs(self) -> List[Dict[str, Any]]:
        return await self.cross_pair_scanner_agent.scan_market()

    async def close_position_and_audit(self, order_id: str, exit_price: float):
        closed_order = self.broker.close_order(order_id, exit_price)
        if closed_order:
            audit = await self.audit_feedback_agent.audit_closed_trade(closed_order, exit_price)
            await self.performance_attribution_agent.ingest_audit(audit)
            self.risk_manager_agent.update_equity(self.broker.equity)
            return audit
        return None
