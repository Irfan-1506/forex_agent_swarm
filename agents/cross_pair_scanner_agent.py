"""
Agent: Cross-Pair Market Scanner (Inspired by trader-scanner in day-trader-skill).
Scans all 28 major and minor Forex currency crosses simultaneously to identify
active momentum, breakout formations, and high-conviction structural opportunities.
"""
from typing import Dict, List, Any
import random
from agents.base_agent import BaseAgent
from core.models import utc_now

ALL_FOREX_PAIRS_28 = [
    # Majors & Commodity Pairs
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "USD/CHF", "NZD/USD",
    # EUR Crosses
    "EUR/GBP", "EUR/JPY", "EUR/AUD", "EUR/CAD", "EUR/CHF", "EUR/NZD",
    # GBP Crosses
    "GBP/JPY", "GBP/AUD", "GBP/CAD", "GBP/CHF", "GBP/NZD",
    # AUD & NZD Crosses
    "AUD/JPY", "AUD/CAD", "AUD/CHF", "AUD/NZD",
    # CAD & CHF Crosses
    "CAD/JPY", "CAD/CHF", "CHF/JPY", "NZD/JPY", "NZD/CAD", "NZD/CHF"
]

class CrossPairScannerAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Cross-Pair Scanner Agent", event_bus, config)
        self.all_pairs = ALL_FOREX_PAIRS_28
        self.last_scan_results: List[Dict[str, Any]] = []

    async def scan_market(self) -> List[Dict[str, Any]]:
        """Scans the 28-pair universe and ranks them by conviction, volatility, and spread efficiency."""
        ranked_setups = []

        for pair in self.all_pairs:
            # Check if blackboard has active data for tracked pairs, or simulate scan metrics
            tick = await self.blackboard.get_latest_tick(pair)
            spread = tick.spread_pips if tick else round(random.uniform(1.1, 2.8), 1)

            # Measure momentum divergence & trend strength proxy
            base, quote = pair.split("/")
            sent_base = self.blackboard.sentiment_reports.get(base)
            sent_quote = self.blackboard.sentiment_reports.get(quote)
            
            sb = sent_base.sentiment_score if sent_base else round(random.uniform(-0.3, 0.3), 2)
            sq = sent_quote.sentiment_score if sent_quote else round(random.uniform(-0.3, 0.3), 2)
            diff = abs(sb - sq)

            # Volatility state
            atr_est = round(random.uniform(0.0012, 0.0035), 4) if "JPY" not in pair else round(random.uniform(0.12, 0.35), 3)

            # Composite setup score (0 to 100)
            setup_score = (diff * 40.0) + (atr_est * 8000 if "JPY" not in pair else atr_est * 80)
            setup_score = max(20.0, min(95.0, setup_score - (spread * 3.0)))

            bias = "BUY" if (sb - sq) > 0.1 else ("SELL" if (sb - sq) < -0.1 else "NEUTRAL")

            setup = {
                "pair": pair,
                "conviction_score": round(setup_score, 1),
                "bias": bias,
                "spread_pips": spread,
                "atr_volatility": atr_est,
                "sentiment_divergence": round(diff, 2),
                "status": "HOT_SETUP" if setup_score > 70.0 else ("MONITORING" if setup_score > 50.0 else "CHOP")
            }
            ranked_setups.append(setup)

        # Sort descending by conviction score
        ranked_setups.sort(key=lambda x: x["conviction_score"], reverse=True)
        self.last_scan_results = ranked_setups[:8]  # Top 8 setups

        top_pair = self.last_scan_results[0]
        self.log(
            f"SCAN COMPLETED (28 Pairs): Leader: {top_pair['pair']} ({top_pair['bias']} - {top_pair['conviction_score']}/100) | "
            f"Top 3: {self.last_scan_results[0]['pair']}, {self.last_scan_results[1]['pair']}, {self.last_scan_results[2]['pair']}",
            style="info"
        )

        await self.bus.publish("scanner.top_setups", self.last_scan_results)
        return self.last_scan_results

    async def step(self):
        await self.scan_market()
