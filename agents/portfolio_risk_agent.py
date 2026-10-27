"""
Tier 3: Portfolio Risk Agent.
Enforces institutional multi-pair risk controls:
1. MAX_OPEN_TRADES = 1 (Only 1 open trade permitted at any time)
2. MAX_CORRELATED_TRADES = 1 (Only 1 USD-directional position across EUR/USD, GBP/USD, USD/JPY, etc.)
3. Total portfolio heat capped at 1.0%
"""
from typing import Dict, Optional
from collections import defaultdict
from agents.base_agent import BaseAgent
from core.models import PortfolioExposure, SignalDirection, utc_now

class PortfolioRiskAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Portfolio Risk Agent", event_bus, config)

    async def evaluate_portfolio_heat(self, proposed_pair: str = None, proposed_direction: SignalDirection = None) -> PortfolioExposure:
        positions = self.blackboard.open_positions
        net_exposures = defaultdict(int)
        total_heat_pct = 0.0

        for pos in positions.values():
            base, quote = pos.pair.split("/")
            if pos.direction == SignalDirection.BUY:
                net_exposures[base] += 1
                net_exposures[quote] -= 1
            elif pos.direction == SignalDirection.SELL:
                net_exposures[base] -= 1
                net_exposures[quote] += 1
            total_heat_pct += self.config.max_stake_per_trade_pct

        can_open = True
        blocking_reason = None

        # 1. Correlated Exposure Breach Check
        if proposed_pair and proposed_direction and proposed_direction != SignalDirection.NEUTRAL:
            base, quote = proposed_pair.split("/")
            temp_base = net_exposures[base] + (1 if proposed_direction == SignalDirection.BUY else -1)
            temp_quote = net_exposures[quote] + (-1 if proposed_direction == SignalDirection.BUY else 1)
            if abs(temp_base) > self.config.max_single_currency_net_exposure:
                can_open = False
                blocking_reason = f"CORRELATED_EXPOSURE_BREACH: Net {base} exposure would be {temp_base} (max {self.config.max_single_currency_net_exposure})"
            elif abs(temp_quote) > self.config.max_single_currency_net_exposure:
                can_open = False
                blocking_reason = f"CORRELATED_EXPOSURE_BREACH: Net {quote} exposure would be {temp_quote} (max {self.config.max_single_currency_net_exposure})"

        # 2. Hard Open Trade Limit
        if can_open and len(positions) >= self.config.max_open_trades:
            can_open = False
            blocking_reason = f"MAX_OPEN_TRADES_LIMIT: {len(positions)} trade already open (max allowed: {self.config.max_open_trades})"

        # 3. Portfolio Heat Limit
        elif can_open and total_heat_pct >= self.config.max_portfolio_heat_pct:
            can_open = False
            blocking_reason = f"MAX_PORTFOLIO_HEAT_REACHED: Heat {total_heat_pct*100:.1f}% >= limit {self.config.max_portfolio_heat_pct*100:.1f}%"

        exposure = PortfolioExposure(
            net_currency_exposures=dict(net_exposures),
            total_portfolio_heat_pct=round(total_heat_pct, 4),
            open_position_count=len(positions),
            can_open_trade=can_open,
            blocking_reason=blocking_reason
        )

        await self.bus.publish("portfolio.exposure", exposure)
        return exposure
