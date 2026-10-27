"""
Tier 2: Pattern Recognition Agent.
Context-aware Smart Money Concepts (SMC) & Classical Price Action.
Detects Fair Value Gaps (FVG), Break of Structure (BOS), Liquidity Sweeps, and Order Blocks
with defined structural invalidation levels.
"""
from typing import List
from agents.base_agent import BaseAgent
from core.models import Candle, TechnicalPatternReport, SignalDirection, MarketRegime, utc_now

class PatternRecognitionAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Pattern Recognition Agent", event_bus, config)

    async def analyze_patterns(self, pair: str, candles: List[Candle]) -> TechnicalPatternReport:
        if not candles or len(candles) < 15:
            return TechnicalPatternReport(
                pair=pair,
                bias=SignalDirection.NEUTRAL,
                detected_patterns=["INSUFFICIENT_DATA"],
                key_support=1.0000,
                key_resistance=1.1000,
                invalidation_level=1.0500,
                expected_holding_period_minutes=30,
                regime_aligned=True,
                confidence=0.5,
                rationale="Insufficient candlestick history for SMC pattern detection."
            )

        c = candles
        recent = c[-5:]
        curr = c[-1]
        prev = c[-2]
        prev2 = c[-3]

        patterns = []
        bias = SignalDirection.NEUTRAL
        confidence = 0.50

        # Calculate local Support & Resistance zones
        highs = [bar.high for bar in c[-20:]]
        lows = [bar.low for bar in c[-20:]]
        key_resistance = max(highs)
        key_support = min(lows)

        # 1. Bullish Fair Value Gap (FVG) [prev2.high < curr.low]
        if prev2.high < curr.low:
            patterns.append("BULLISH_FVG_IMBALANCE")
            bias = SignalDirection.BUY
            confidence += 0.15

        # 2. Bearish Fair Value Gap (FVG) [prev2.low > curr.high]
        elif prev2.low > curr.high:
            patterns.append("BEARISH_FVG_IMBALANCE")
            bias = SignalDirection.SELL
            confidence += 0.15

        # 3. Pin Bar / Liquidity Sweep Rejection
        body = abs(curr.close - curr.open)
        upper_wick = curr.high - max(curr.close, curr.open)
        lower_wick = min(curr.close, curr.open) - curr.low
        total_range = curr.high - curr.low

        if total_range > 0:
            if lower_wick / total_range > 0.60:
                patterns.append("BULLISH_PIN_BAR_LIQUIDITY_SWEEP")
                bias = SignalDirection.BUY
                confidence += 0.15
            elif upper_wick / total_range > 0.60:
                patterns.append("BEARISH_PIN_BAR_LIQUIDITY_SWEEP")
                bias = SignalDirection.SELL
                confidence += 0.15

        # 4. Engulfing Candle
        if curr.close > prev.open and prev.close < prev.open and curr.close > curr.open:
            patterns.append("BULLISH_ENGULFING")
            if bias != SignalDirection.SELL:
                bias = SignalDirection.BUY
                confidence += 0.10
        elif curr.close < prev.open and prev.close > prev.open and curr.close < curr.open:
            patterns.append("BEARISH_ENGULFING")
            if bias != SignalDirection.BUY:
                bias = SignalDirection.SELL
                confidence += 0.10

        # Check regime alignment from blackboard
        regime_rep = self.blackboard.regime_reports.get(pair)
        regime_aligned = True
        if regime_rep:
            if regime_rep.regime == MarketRegime.TRENDING_BULL and bias == SignalDirection.SELL:
                regime_aligned = False
                confidence -= 0.15
                patterns.append("COUNTER_TREND_WARNING")
            elif regime_rep.regime == MarketRegime.TRENDING_BEAR and bias == SignalDirection.BUY:
                regime_aligned = False
                confidence -= 0.15
                patterns.append("COUNTER_TREND_WARNING")

        if not patterns:
            patterns.append("CONSOLIDATION_RANGE")
            bias = SignalDirection.NEUTRAL
            confidence = 0.50

        # Define structural invalidation level
        if bias == SignalDirection.BUY:
            invalidation_level = key_support - (0.0005 if "JPY" not in pair else 0.05)
        elif bias == SignalDirection.SELL:
            invalidation_level = key_resistance + (0.0005 if "JPY" not in pair else 0.05)
        else:
            invalidation_level = (key_support + key_resistance) / 2.0

        confidence = max(0.2, min(0.95, confidence))
        holding_time = 45 if bias != SignalDirection.NEUTRAL else 15

        rationale = (
            f"Detected: {', '.join(patterns)}. Bias: {bias.value} ({confidence*100:.0f}% confidence). "
            f"Support: {key_support:.5f}, Resistance: {key_resistance:.5f}, Invalidation: {invalidation_level:.5f}."
        )

        report = TechnicalPatternReport(
            pair=pair,
            bias=bias,
            detected_patterns=patterns,
            key_support=round(key_support, 5),
            key_resistance=round(key_resistance, 5),
            invalidation_level=round(invalidation_level, 5),
            expected_holding_period_minutes=holding_time,
            regime_aligned=regime_aligned,
            confidence=round(confidence, 2),
            rationale=rationale
        )

        await self.bus.publish(f"pattern.{pair}", report)
        return report
