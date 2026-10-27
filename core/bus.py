"""
Asynchronous Event Bus and Shared Blackboard State Store for Swarm Agents.
Expanded with Tier 0 data health, regime tracking, portfolio heat, and persistent event ledger.
"""
import os
import json
import asyncio
from typing import Dict, List, Callable, Any, Optional
from collections import defaultdict
from core.models import (
    MarketTick, Candle, NewsSentimentReport, MacroEventReport,
    MicrostructureReport, TechnicalPatternReport, QuantIndicatorReport,
    TradeProposal, RiskEvaluation, OrderExecutionReport, AuditRecord,
    DataHealthReport, RegimeReport, PortfolioExposure, EmergencyHaltStatus,
    BeliefSnapshot, utc_now
)

LEDGER_DIR = os.path.join(os.path.dirname(__file__), "..", "ledger")
os.makedirs(LEDGER_DIR, exist_ok=True)
LEDGER_FILE = os.path.join(LEDGER_DIR, "swarm_event_ledger.jsonl")

class SwarmBlackboard:
    """Shared state blackboard accessible by all agents for cross-referencing."""
    def __init__(self):
        self._lock = asyncio.Lock()
        self.market_ticks: Dict[str, MarketTick] = {}
        self.candles: Dict[str, List[Candle]] = defaultdict(list)
        
        # Tier 0 & 1 States
        self.data_health: Dict[str, DataHealthReport] = {}
        self.regime_reports: Dict[str, RegimeReport] = {}
        self.sentiment_reports: Dict[str, NewsSentimentReport] = {}
        self.macro_reports: Dict[str, MacroEventReport] = {}
        self.microstructure_reports: Dict[str, MicrostructureReport] = {}
        
        # Tier 2 & 3 States
        self.pattern_reports: Dict[str, TechnicalPatternReport] = {}
        self.quant_reports: Dict[str, QuantIndicatorReport] = {}
        self.active_proposals: Dict[str, TradeProposal] = {}
        self.portfolio_exposure: Optional[PortfolioExposure] = None
        self.approved_orders: Dict[str, RiskEvaluation] = {}
        
        # Tier 4 States
        self.open_positions: Dict[str, OrderExecutionReport] = {}
        self.completed_audits: List[AuditRecord] = []
        self.belief_snapshots: Dict[str, BeliefSnapshot] = {}
        
        # Emergency & Safety
        self.emergency_halt = EmergencyHaltStatus(is_halted=False)

    async def update_tick(self, tick: MarketTick):
        async with self._lock:
            self.market_ticks[tick.pair] = tick

    async def get_latest_tick(self, pair: str) -> Optional[MarketTick]:
        async with self._lock:
            return self.market_ticks.get(pair)

    async def set_data_health(self, report: DataHealthReport):
        async with self._lock:
            self.data_health[report.pair] = report

    async def set_regime(self, report: RegimeReport):
        async with self._lock:
            self.regime_reports[report.pair] = report

    async def set_sentiment(self, report: NewsSentimentReport):
        async with self._lock:
            self.sentiment_reports[report.currency] = report

    async def set_macro(self, report: MacroEventReport):
        async with self._lock:
            self.macro_reports[report.currency] = report

    async def set_microstructure(self, report: MicrostructureReport):
        async with self._lock:
            self.microstructure_reports[report.pair] = report

    async def set_pattern(self, report: TechnicalPatternReport):
        async with self._lock:
            self.pattern_reports[report.pair] = report

    async def set_quant(self, report: QuantIndicatorReport):
        async with self._lock:
            self.quant_reports[report.pair] = report

    async def set_portfolio_exposure(self, exp: PortfolioExposure):
        async with self._lock:
            self.portfolio_exposure = exp

    async def set_emergency_halt(self, halt: EmergencyHaltStatus):
        async with self._lock:
            self.emergency_halt = halt

    async def record_belief_snapshot(self, snap: BeliefSnapshot):
        async with self._lock:
            self.belief_snapshots[snap.snapshot_id] = snap

    async def get_state_summary(self, pair: str) -> Dict[str, Any]:
        async with self._lock:
            base, quote = pair.split("/")
            return {
                "pair": pair,
                "tick": self.market_ticks.get(pair),
                "data_health": self.data_health.get(pair),
                "regime": self.regime_reports.get(pair),
                "sentiment_base": self.sentiment_reports.get(base),
                "sentiment_quote": self.sentiment_reports.get(quote),
                "macro_base": self.macro_reports.get(base),
                "macro_quote": self.macro_reports.get(quote),
                "microstructure": self.microstructure_reports.get(pair),
                "pattern": self.pattern_reports.get(pair),
                "quant": self.quant_reports.get(pair),
                "portfolio_exposure": self.portfolio_exposure,
                "emergency_halt": self.emergency_halt,
            }


class SwarmEventBus:
    """Async Pub-Sub messaging bus connecting swarm agents with persistent append-only ledger."""
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Any], Any]]] = defaultdict(list)
        self.blackboard = SwarmBlackboard()

    def subscribe(self, topic: str, callback: Callable[[Any], Any]):
        self._subscribers[topic].append(callback)

    async def publish(self, topic: str, data: Any):
        if isinstance(data, MarketTick):
            await self.blackboard.update_tick(data)
        elif isinstance(data, DataHealthReport):
            await self.blackboard.set_data_health(data)
        elif isinstance(data, RegimeReport):
            await self.blackboard.set_regime(data)
        elif isinstance(data, NewsSentimentReport):
            await self.blackboard.set_sentiment(data)
        elif isinstance(data, MacroEventReport):
            await self.blackboard.set_macro(data)
        elif isinstance(data, MicrostructureReport):
            await self.blackboard.set_microstructure(data)
        elif isinstance(data, TechnicalPatternReport):
            await self.blackboard.set_pattern(data)
        elif isinstance(data, QuantIndicatorReport):
            await self.blackboard.set_quant(data)
        elif isinstance(data, PortfolioExposure):
            await self.blackboard.set_portfolio_exposure(data)
        elif isinstance(data, EmergencyHaltStatus):
            await self.blackboard.set_emergency_halt(data)
        elif isinstance(data, BeliefSnapshot):
            await self.blackboard.record_belief_snapshot(data)

        self._append_to_ledger(topic, data)

        handlers = self._subscribers.get(topic, [])
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                asyncio.create_task(handler(data))
            else:
                handler(data)

    def _append_to_ledger(self, topic: str, data: Any):
        try:
            entry = {
                "timestamp": utc_now().isoformat(),
                "topic": topic,
                "payload_type": type(data).__name__,
                "data": data.model_dump(mode="json") if hasattr(data, "model_dump") else str(data)
            }
            with open(LEDGER_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
