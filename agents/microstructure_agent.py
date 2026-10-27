"""
Tier 1: Microstructure & Order Flow Agent.
Analyzes bid-ask spread expansion, liquidity health, quote stability, and friction drag.
"""
from typing import Dict, List
from agents.base_agent import BaseAgent
from core.models import MarketTick, MicrostructureReport, utc_now

class MicrostructureAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Microstructure Agent", event_bus, config)
        self.spread_history: Dict[str, List[float]] = {}
        self.quote_times: Dict[str, List[float]] = {}

    async def analyze_tick(self, tick: MarketTick) -> MicrostructureReport:
        pair = tick.pair
        spread = tick.spread_pips

        if pair not in self.spread_history:
            self.spread_history[pair] = []
        self.spread_history[pair].append(spread)
        if len(self.spread_history[pair]) > 50:
            self.spread_history[pair].pop(0)

        avg_spread = sum(self.spread_history[pair]) / len(self.spread_history[pair])
        spread_ratio = round(spread / (avg_spread + 1e-6), 2)

        # Friction cost approximation: 1 pip on 1 standard lot = $10 USD
        friction_usd = round(spread * 10.0, 2)
        
        # Quote flicker detection (rapid oscillations)
        quote_flicker = False
        if len(self.spread_history[pair]) >= 5:
            last_5 = self.spread_history[pair][-5:]
            volatility = max(last_5) - min(last_5)
            if volatility > 1.5:
                quote_flicker = True

        # Tradability checks
        is_tradable = True
        anomalies = []
        if spread > self.config.max_spread_pips_allowed:
            is_tradable = False
            anomalies.append(f"SPREAD_BLOWN: {spread:.1f} pips exceeds ceiling of {self.config.max_spread_pips_allowed} pips")
        if spread_ratio > 2.5:
            is_tradable = False
            anomalies.append(f"SPREAD_ANOMALY: Spread is {spread_ratio}x historical baseline")
        if quote_flicker:
            anomalies.append("QUOTE_FLICKER: Rapid spread volatility detected")

        # Liquidity score (0-100)
        liquidity_score = max(10.0, min(100.0, 100.0 - (spread * 18.0) - (spread_ratio * 10.0)))

        # Friction penalty for decision weighting
        penalty = round(min(0.35, max(0.0, (spread - 1.0) * 0.1)), 2)

        rationale = (
            f"Spread: {spread:.1f} pips ({spread_ratio}x avg). Liquidity: {liquidity_score:.0f}/100. "
            f"Friction Drag: ${friction_usd}/lot. {'TRADABLE' if is_tradable else 'UNTRADABLE: ' + '; '.join(anomalies)}"
        )

        report = MicrostructureReport(
            pair=pair,
            spread_pips=round(spread, 1),
            spread_ratio=spread_ratio,
            liquidity_score=round(liquidity_score, 1),
            friction_cost_usd=friction_usd,
            friction_penalty=penalty,
            is_tradable=is_tradable,
            quote_flicker_detected=quote_flicker,
            rationale=rationale
        )

        await self.bus.publish(f"microstructure.{pair}", report)
        return report
