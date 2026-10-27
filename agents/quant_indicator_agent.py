"""
Tier 2: Quant & Indicator Agent.
Computes mathematical indicators: ATR (volatility stop baseline), RSI (mean-reversion),
Bollinger Bands & Z-score, ADX (trend strength), and Currency Strength Meter (CSM).
"""
from typing import List
import numpy as np
from agents.base_agent import BaseAgent
from core.models import Candle, QuantIndicatorReport, SignalDirection, utc_now

class QuantIndicatorAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Quant & Indicator Agent", event_bus, config)

    async def calculate_indicators(self, pair: str, candles: List[Candle]) -> QuantIndicatorReport:
        if not candles or len(candles) < 20:
            return QuantIndicatorReport(
                pair=pair,
                atr=0.0015,
                adx=20.0,
                rsi=50.0,
                bollinger_upper=1.0900,
                bollinger_lower=1.0700,
                z_score=0.0,
                csm_strength=0.0,
                realized_volatility_percentile=50.0,
                volatility_state="NORMAL",
                bias=SignalDirection.NEUTRAL,
                confidence=0.5,
                rationale="Insufficient candles for quant calculations. Defaulting to neutral."
            )

        closes = np.array([c.close for c in candles])
        highs = np.array([c.high for c in candles])
        lows = np.array([c.low for c in candles])

        # 1. ATR (14 period)
        tr = np.maximum(highs[1:] - lows[1:], np.maximum(abs(highs[1:] - closes[:-1]), abs(lows[1:] - closes[:-1])))
        atr = float(np.mean(tr[-14:]) if len(tr) >= 14 else np.mean(tr))

        # 2. RSI (14 period)
        diff = np.diff(closes)
        gains = np.where(diff > 0, diff, 0.0)
        losses = np.where(diff < 0, -diff, 0.0)
        avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 1e-6
        avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 1e-6
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = float(100.0 - (100.0 / (1.0 + rs)))

        # 3. Bollinger Bands & Z-score (20 period)
        window_closes = closes[-20:] if len(closes) >= 20 else closes
        mean_price = np.mean(window_closes)
        std_price = np.std(window_closes) + 1e-9
        bb_upper = float(mean_price + (2.0 * std_price))
        bb_lower = float(mean_price - (2.0 * std_price))
        z_score = float((closes[-1] - mean_price) / std_price)

        # 4. ADX proxy
        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        tr_sum = np.sum(tr[-14:]) if len(tr) >= 14 else np.sum(tr)
        plus_di = 100 * (np.sum(plus_dm[-14:]) / (tr_sum + 1e-9))
        minus_di = 100 * (np.sum(minus_dm[-14:]) / (tr_sum + 1e-9))
        adx = float(np.clip(100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)), 5.0, 75.0))

        # 5. Currency Strength Meter proxy (based on recent ROC)
        csm = float(np.clip((closes[-1] - closes[-20]) / (closes[-20] + 1e-9) * 100.0, -5.0, 5.0))

        # 6. Realized Volatility Percentile
        vol_window = tr[-min(50, len(tr)):]
        vol_pct = float(np.mean(vol_window <= tr[-1]) * 100.0)
        vol_state = "EXPANSION" if vol_pct > 80 else ("COMPRESSION" if vol_pct < 25 else "NORMAL")

        # Bias computation
        bias = SignalDirection.NEUTRAL
        confidence = 0.50

        # Mean-reversion vs Trend conditions
        if rsi < 32 and z_score < -1.8:
            bias = SignalDirection.BUY
            confidence = 0.65
        elif rsi > 68 and z_score > 1.8:
            bias = SignalDirection.SELL
            confidence = 0.65
        elif adx > 25:
            # Trend following
            if closes[-1] > mean_price and rsi > 52:
                bias = SignalDirection.BUY
                confidence = 0.60
            elif closes[-1] < mean_price and rsi < 48:
                bias = SignalDirection.SELL
                confidence = 0.60

        rationale = (
            f"ATR: {atr:.5f}, RSI: {rsi:.1f}, Z-Score: {z_score:.2f}, ADX: {adx:.1f}, "
            f"CSM: {csm:+.2f}, Volatility: {vol_state} ({vol_pct:.0f}%). Bias: {bias.value}."
        )

        report = QuantIndicatorReport(
            pair=pair,
            atr=round(atr, 5),
            adx=round(adx, 1),
            rsi=round(rsi, 1),
            bollinger_upper=round(bb_upper, 5),
            bollinger_lower=round(bb_lower, 5),
            z_score=round(z_score, 2),
            csm_strength=round(csm, 2),
            realized_volatility_percentile=round(vol_pct, 1),
            volatility_state=vol_state,
            bias=bias,
            confidence=round(confidence, 2),
            rationale=rationale
        )

        await self.bus.publish(f"quant.{pair}", report)
        return report
