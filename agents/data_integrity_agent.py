"""
Tier 0 Safety: Data Integrity Agent.
Guards the swarm against bad data, stale ticks, gap anomalies, and feed disconnections.
"""
from typing import Dict, Optional
from datetime import datetime
from agents.base_agent import BaseAgent
from core.models import MarketTick, DataHealthReport, utc_now
from core.alert_dispatcher import global_alert_dispatcher

class DataIntegrityAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Data Integrity Agent", event_bus, config)
        self.last_tick_times: Dict[str, datetime] = {}
        self.last_tick_prices: Dict[str, float] = {}

    async def validate_tick(self, tick: MarketTick) -> DataHealthReport:
        now = utc_now()
        anomalies = []
        is_fresh = True
        price_continuity_valid = True
        feed_healthy = True

        staleness = (now - tick.timestamp).total_seconds()
        if staleness > self.config.max_tick_staleness_seconds:
            is_fresh = False
            anomalies.append(f"STALE_TICK: Age {staleness:.1f}s exceeds limit {self.config.max_tick_staleness_seconds}s")

        if tick.pair in self.last_tick_prices:
            prev_price = self.last_tick_prices[tick.pair]
            mid = (tick.bid + tick.ask) / 2.0
            pct_change = abs(mid - prev_price) / prev_price if prev_price > 0 else 0
            if pct_change > self.config.max_price_jump_spike_pct:
                price_continuity_valid = False
                anomalies.append(f"PRICE_SPIKE_ANOMALY: Sudden jump {pct_change*100:.2f}% exceeds threshold {self.config.max_price_jump_spike_pct*100:.2f}%")

        if tick.bid <= 0 or tick.ask <= 0 or tick.ask < tick.bid:
            feed_healthy = False
            anomalies.append("CORRUPT_QUOTE: Negative price or inverted spread (Ask < Bid)")

        if anomalies:
            rationale = "CRITICAL DATA ISSUES: " + "; ".join(anomalies)
            global_alert_dispatcher.dispatch_alert("Data Integrity Warning", rationale, severity="WARNING", pair=tick.pair)
        else:
            rationale = f"Tick valid. Freshness {staleness:.2f}s, spread {tick.spread_pips:.1f} pips."

        self.last_tick_times[tick.pair] = tick.timestamp
        self.last_tick_prices[tick.pair] = (tick.bid + tick.ask) / 2.0

        report = DataHealthReport(
            pair=tick.pair,
            is_fresh=is_fresh,
            staleness_seconds=round(staleness, 2),
            price_continuity_valid=price_continuity_valid,
            feed_healthy=feed_healthy and is_fresh and price_continuity_valid,
            detected_anomalies=anomalies,
            rationale=rationale
        )

        await self.bus.publish(f"data_health.{tick.pair}", report)
        return report
