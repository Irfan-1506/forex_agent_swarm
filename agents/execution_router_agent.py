"""
Tier 4: Execution Router Agent.
Manages the order execution lifecycle:
CREATED -> SUBMITTED -> ACKNOWLEDGED -> FILLED / REJECTED
- Integrates Sequential Entry Timer for micro-pullback limit execution
- Freezes instantaneous Belief Snapshot at moment of trade entry for post-trade attribution
- Interacts with Broker Engine, reconciles positions, and models slippage & commission
"""
from agents.base_agent import BaseAgent
from core.models import (
    RiskEvaluation, OrderExecutionReport, OrderStatus,
    BeliefSnapshot, utc_now
)
from engine.micro_entry_timer import SequentialEntryTimer
from core.alert_dispatcher import global_alert_dispatcher

class ExecutionRouterAgent(BaseAgent):
    def __init__(self, event_bus, broker, config=None):
        super().__init__("Execution Router Agent", event_bus, config)
        self.broker = broker
        self.entry_timer = SequentialEntryTimer()

    async def execute_approved_trade(self, risk_approval: RiskEvaluation) -> OrderExecutionReport:
        if not risk_approval.approved:
            report = OrderExecutionReport(
                proposal_id=risk_approval.proposal_id,
                pair=risk_approval.pair,
                direction=risk_approval.direction,
                requested_lot_size=0.0,
                filled_lot_size=0.0,
                requested_price=risk_approval.entry_price,
                executed_price=risk_approval.entry_price,
                slippage_pips=0.0,
                status=OrderStatus.REJECTED,
                stop_loss=risk_approval.stop_loss,
                take_profit=risk_approval.take_profit
            )
            return report

        pair = risk_approval.pair
        direction = risk_approval.direction
        quant = self.blackboard.quant_reports.get(pair)
        micro = self.blackboard.microstructure_reports.get(pair)
        atr = quant.atr if quant else 0.0015
        spread = micro.spread_pips if micro else 1.2
        is_jpy = "JPY" in pair

        # Sequential micro-pullback entry calculation
        entry_timing = self.entry_timer.calculate_optimized_entry(
            raw_price=risk_approval.entry_price,
            direction=direction,
            atr=atr,
            spread_pips=spread,
            is_jpy=is_jpy
        )
        target_entry_price = entry_timing["optimized_entry_price"]

        # 1. Take snapshot of current agent beliefs for attribution
        pattern = self.blackboard.pattern_reports.get(pair)
        regime = self.blackboard.regime_reports.get(pair)
        sent = self.blackboard.sentiment_reports.get(pair.split("/")[0])
        macro = self.blackboard.macro_reports.get(pair.split("/")[0])

        belief = BeliefSnapshot(
            proposal_id=risk_approval.proposal_id,
            pair=pair,
            direction=direction,
            regime=regime.regime if regime else "RANGE_BOUND",
            pattern_signal=pattern.confidence if pattern else 0.5,
            quant_signal=quant.confidence if quant else 0.5,
            sentiment_signal=sent.sentiment_score if sent else 0.0,
            macro_state=macro.state.value if macro else "CLEAR",
            decision_confidence=pattern.confidence if pattern else 0.5,
            risk_approved=True
        )
        await self.blackboard.record_belief_snapshot(belief)

        # 2. Dispatch Order to Broker
        fill_result = await self.broker.submit_order(
            pair=pair,
            direction=direction,
            lot_size=risk_approval.calculated_lot_size,
            requested_price=target_entry_price,
            stop_loss=risk_approval.stop_loss,
            take_profit=risk_approval.take_profit,
            proposal_id=risk_approval.proposal_id,
            belief_snapshot_id=belief.snapshot_id
        )

        # 3. Store in blackboard active positions
        self.blackboard.open_positions[fill_result.order_id] = fill_result
        await self.bus.publish(f"execution.fill.{pair}", fill_result)

        global_alert_dispatcher.dispatch_alert(
            title=f"Order Filled: {pair} {direction.value}",
            message=f"Filled {fill_result.filled_lot_size} lots @ {fill_result.executed_price:.5f}. Slippage: {fill_result.slippage_pips:+.1f} pips. Status: {fill_result.status.value}",
            severity="TRADE",
            pair=pair
        )
        return fill_result
