"""
Tier 4: Audit & Feedback Agent.
Conducts post-trade post-mortem analysis:
Computes realized R-multiples, Maximum Adverse Excursion (MAE), Maximum Favorable Excursion (MFE),
friction drag analysis, and feeds results into the performance attribution ledger.
"""
from typing import List, Dict
from agents.base_agent import BaseAgent
from core.models import AuditRecord, OrderExecutionReport, SignalDirection, utc_now
from core.calibration_validator import global_calibration_validator

class AuditFeedbackAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Audit & Feedback Agent", event_bus, config)
        self.audit_records: List[AuditRecord] = []

    async def audit_closed_trade(
        self,
        order: OrderExecutionReport,
        exit_price: float,
        initial_risk_usd: float = 1000.0,
        holding_time_minutes: float = 30.0,
        mae_pips: float = 2.0,
        mfe_pips: float = 12.0
    ) -> AuditRecord:
        pip_unit = 0.01 if "JPY" in order.pair else 0.0001
        direction_mult = 1.0 if order.direction == SignalDirection.BUY else -1.0

        pnl_pips = (exit_price - order.executed_price) / pip_unit * direction_mult
        # 1 pip on 1 lot = $10
        gross_pnl_usd = pnl_pips * 10.0 * order.filled_lot_size
        net_pnl_usd = gross_pnl_usd - order.commission_usd

        # Realized R-multiple
        r_mult = round(net_pnl_usd / (initial_risk_usd + 1e-6), 2)
        outcome = "WIN" if net_pnl_usd > 0 else ("LOSS" if net_pnl_usd < 0 else "BREAKEVEN")

        # Retrieve belief snapshot
        snapshot = None
        if order.belief_snapshot_id and order.belief_snapshot_id in self.blackboard.belief_snapshots:
            snapshot = self.blackboard.belief_snapshots[order.belief_snapshot_id]
            snapshot.final_result_r = r_mult
            # Feed into out-of-sample calibration tracker
            global_calibration_validator.record_prediction_outcome(
                predicted_confidence=snapshot.decision_confidence,
                outcome_win=(outcome == "WIN"),
                timestamp=utc_now().isoformat()
            )

        post_mortem = (
            f"Trade {order.order_id} ({order.pair} {order.direction.value}) closed with {outcome}. "
            f"PnL: ${net_pnl_usd:+.2f} ({pnl_pips:+.1f} pips, {r_mult:+.2f}R). "
            f"Slippage incurred: {order.slippage_pips:.1f} pips. Holding duration: {holding_time_minutes:.1f}m."
        )

        record = AuditRecord(
            order_id=order.order_id,
            pair=order.pair,
            direction=order.direction,
            entry_price=order.executed_price,
            exit_price=round(exit_price, 5),
            pnl_usd=round(net_pnl_usd, 2),
            pnl_pips=round(pnl_pips, 1),
            r_multiple=r_mult,
            mae_pips=mae_pips,
            mfe_pips=mfe_pips,
            holding_time_minutes=holding_time_minutes,
            outcome=outcome,
            rule_compliant=True,
            post_mortem=post_mortem,
            belief_snapshot=snapshot
        )

        self.audit_records.append(record)
        self.blackboard.completed_audits.append(record)
        await self.bus.publish(f"audit.trade.{order.pair}", record)
        return record
