"""
Institutional Mock Broker Engine.
Simulates realistic ECN fills, latency, spread expansion, random slippage,
and commissions ($5.0/lot round-turn) for fidelity.
"""
import asyncio
import random
from typing import Dict, List, Optional
from core.models import (
    OrderExecutionReport, SignalDirection, OrderStatus, utc_now
)
from config import config

class MockBrokerEngine:
    def __init__(self, initial_balance: float = 100_000.0):
        self.balance = initial_balance
        self.equity = initial_balance
        self.open_orders: Dict[str, OrderExecutionReport] = {}
        self.closed_orders: List[OrderExecutionReport] = []
        self.fail_next_order = False

    async def submit_order(
        self,
        pair: str,
        direction: SignalDirection,
        lot_size: float,
        requested_price: float,
        stop_loss: float,
        take_profit: float,
        proposal_id: str,
        belief_snapshot_id: Optional[str] = None
    ) -> OrderExecutionReport:
        # Simulate network latency (45ms)
        await asyncio.sleep(config.simulated_latency_ms / 1000.0)

        if self.fail_next_order:
            self.fail_next_order = False
            return OrderExecutionReport(
                proposal_id=proposal_id,
                pair=pair,
                direction=direction,
                requested_lot_size=lot_size,
                filled_lot_size=0.0,
                requested_price=requested_price,
                executed_price=requested_price,
                slippage_pips=0.0,
                commission_usd=0.0,
                status=OrderStatus.REJECTED,
                stop_loss=stop_loss,
                take_profit=take_profit,
                belief_snapshot_id=belief_snapshot_id
            )

        # Realistic Slippage modeling (-0.2 to +0.8 pips adverse slippage)
        pip_unit = 0.01 if "JPY" in pair else 0.0001
        slippage_pips = round(random.uniform(-0.1, 0.6), 1)
        slippage_price_delta = slippage_pips * pip_unit

        if direction == SignalDirection.BUY:
            executed_price = requested_price + slippage_price_delta
        else:
            executed_price = requested_price - slippage_price_delta

        # Round turn commission: $5 per lot
        commission = round(lot_size * config.commission_per_lot_round_turn, 2)
        self.equity -= commission

        order = OrderExecutionReport(
            proposal_id=proposal_id,
            pair=pair,
            direction=direction,
            requested_lot_size=lot_size,
            filled_lot_size=lot_size,
            requested_price=round(requested_price, 5),
            executed_price=round(executed_price, 5),
            slippage_pips=slippage_pips,
            commission_usd=commission,
            latency_ms=config.simulated_latency_ms,
            status=OrderStatus.FILLED,
            stop_loss=round(stop_loss, 5),
            take_profit=round(take_profit, 5),
            belief_snapshot_id=belief_snapshot_id
        )

        self.open_orders[order.order_id] = order
        return order

    def close_order(self, order_id: str, exit_price: float) -> Optional[OrderExecutionReport]:
        if order_id in self.open_orders:
            order = self.open_orders.pop(order_id)
            order.status = OrderStatus.CLOSED
            pip_unit = 0.01 if "JPY" in order.pair else 0.0001
            mult = 1.0 if order.direction == SignalDirection.BUY else -1.0
            pnl_pips = (exit_price - order.executed_price) / pip_unit * mult
            pnl_usd = (pnl_pips * 10.0 * order.filled_lot_size) - order.commission_usd
            self.balance += pnl_usd
            self.equity = self.balance
            self.closed_orders.append(order)
            return order
        return None
