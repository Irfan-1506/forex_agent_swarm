"""
Tier 0/1: Regime Classifier Agent.
Classifies market state (Trending, Range, Squeeze, Volatility Expansion, Unstable)
using ADX, ATR percentiles, and trend persistence so strategies adapt dynamically.
"""
from typing import List
import numpy as np
from agents.base_agent import BaseAgent
from core.models import Candle, MarketRegime, RegimeReport, utc_now

class RegimeClassifierAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Regime Classifier Agent", event_bus, config)

    async def classify_regime(self, pair: str, candles: List[Candle]) -> RegimeReport:
        if not candles or len(candles) < 20:
            return RegimeReport(
                pair=pair,
                regime=MarketRegime.RANGE_BOUND,
                adx=20.0,
                atr_percentile=50.0,
                trend_persistence_score=0.5,
                is_trending=False,
                is_squeezed=False,
                confidence=0.5,
                rationale="Insufficient bar history (<20). Defaulting to Range-Bound."
            )

        closes = np.array([c.close for c in candles])
        highs = np.array([c.high for c in candles])
        lows = np.array([c.low for c in candles])

        # ADX Approximation via directional movement
        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        tr = np.maximum(highs[1:] - lows[1:], np.maximum(abs(highs[1:] - closes[:-1]), abs(lows[1:] - closes[:-1])))
        tr_sum = np.sum(tr[-14:]) if len(tr) >= 14 else np.sum(tr)
        plus_di = 100 * (np.sum(plus_dm[-14:]) / (tr_sum + 1e-9))
        minus_di = 100 * (np.sum(minus_dm[-14:]) / (tr_sum + 1e-9))
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))
        adx = float(np.clip(dx, 5.0, 75.0))

        # ATR percentile vs 50-bar rolling ATR
        atr_window = tr[-min(50, len(tr)):]
        current_atr = tr[-1]
        atr_percentile = float(np.mean(atr_window <= current_atr) * 100.0)

        # Trend slope & persistence
        slope = (closes[-1] - closes[-14]) / closes[-14] if len(closes) >= 14 else 0.0
        consecutive_direction = np.diff(closes[-5:])
        trend_persistence = float(np.mean(consecutive_direction > 0) if slope > 0 else np.mean(consecutive_direction < 0))

        # Regime determination
        is_trending = adx >= self.config.adx_trending_threshold
        is_squeezed = atr_percentile < 25.0 and adx < 20.0
        is_volatile = atr_percentile > 80.0

        if is_squeezed:
            regime = MarketRegime.COMPRESSION_SQUEEZE
            rationale = f"Low ATR ({atr_percentile:.1f} percentile) and low ADX ({adx:.1f}) indicate volatility compression / coil."
        elif is_volatile and not is_trending:
            regime = MarketRegime.VOLATILITY_EXPANSION
            rationale = f"High ATR expansion ({atr_percentile:.1f} percentile) without sustained direction."
        elif is_trending:
            if slope > 0:
                regime = MarketRegime.TRENDING_BULL
                rationale = f"Strong Bullish Trend confirmed: ADX {adx:.1f} > {self.config.adx_trending_threshold}, positive slope."
            else:
                regime = MarketRegime.TRENDING_BEAR
                rationale = f"Strong Bearish Trend confirmed: ADX {adx:.1f} > {self.config.adx_trending_threshold}, negative slope."
        else:
            regime = MarketRegime.RANGE_BOUND
            rationale = f"Mean-reverting consolidation corridor. ADX {adx:.1f} is below trending threshold."

        confidence = round(float(np.clip(adx / 40.0, 0.4, 0.95)), 2)

        report = RegimeReport(
            pair=pair,
            regime=regime,
            adx=round(adx, 1),
            atr_percentile=round(atr_percentile, 1),
            trend_persistence_score=round(trend_persistence, 2),
            is_trending=is_trending,
            is_squeezed=is_squeezed,
            confidence=confidence,
            rationale=rationale
        )

        await self.bus.publish(f"regime.{pair}", report)
        return report
