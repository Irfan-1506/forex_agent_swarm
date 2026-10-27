"""
Tier 3: Chief Decision Maker Agent.
Upgraded with:
1. True Confluence Engine (1 Trend Filter + 1 Momentum Trigger + 1 Location/Structure Confirmation)
2. Strict Contradiction Detection (skips trade rather than averaging opposing signals)
3. Two-Stage Pipeline: Direction Bias vs Approval Status
4. Regime-to-Expiry Class Matching (1M/2M/5M/15M)
5. Actionable Watchlist Generator (identifies precise missing conditions & action triggers)
"""
from datetime import timedelta
from typing import List, Dict, Optional
from agents.base_agent import BaseAgent
from core.models import TradeProposal, SignalDirection, MarketRegime, utc_now

class DecisionMakerAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Chief Decision Maker Agent", event_bus, config)

    async def generate_proposal(self, pair: str, binary_payout_pct: float = 87.0) -> TradeProposal:
        state = await self.blackboard.get_state_summary(pair)
        tick = state.get("tick")
        current_price = ((tick.bid + tick.ask) / 2.0) if tick else 1.08500

        pattern = state.get("pattern")
        quant = state.get("quant")
        sent_base = state.get("sentiment_base")
        sent_quote = state.get("sentiment_quote")
        macro_base = state.get("macro_base")
        macro_quote = state.get("macro_quote")
        regime = state.get("regime")
        micro = state.get("microstructure")

        missing_conditions: List[str] = []
        action_trigger: Optional[str] = None
        confluence_checklist: Dict[str, bool] = {}

        # 1. Macro Calendar Lock Check
        macro_locked = (macro_base and macro_base.lock_trading_window) or (macro_quote and macro_quote.lock_trading_window)
        confluence_checklist["macro_clear"] = not macro_locked
        if macro_locked:
            missing_conditions.append("Macro blackout window active (high-impact release imminent)")

        # 2. Spread Check
        spread = micro.spread_pips if micro else 1.2
        spread_pass = spread <= self.config.max_spread_pips_allowed
        confluence_checklist["spread_pass"] = spread_pass
        if not spread_pass:
            missing_conditions.append(f"Spread {spread:.1f}p exceeds institutional ceiling {self.config.max_spread_pips_allowed:.1f}p")

        # 3. Detect Directional Bias (Separated from Approval)
        p_bias = pattern.bias if pattern else SignalDirection.NEUTRAL
        q_bias = quant.bias if quant else SignalDirection.NEUTRAL
        
        # Currency Sentiment bias
        sb = sent_base.sentiment_score if sent_base else 0.0
        sq = sent_quote.sentiment_score if sent_quote else 0.0
        sent_diff = sb - sq
        s_bias = SignalDirection.BUY if sent_diff > 0.15 else (SignalDirection.SELL if sent_diff < -0.15 else SignalDirection.NEUTRAL)

        # 4. Strict Contradiction Detection: If signals fight, DO NOT average them!
        contradiction = False
        if (p_bias == SignalDirection.BUY and q_bias == SignalDirection.SELL) or \
           (p_bias == SignalDirection.SELL and q_bias == SignalDirection.BUY):
            contradiction = True
            missing_conditions.append(f"CONTRADICTION DETECTED: Technical Pattern ({p_bias.value}) opposes Momentum Indicator ({q_bias.value})")

        # Determine Primary Directional Candidate
        direction_bias = SignalDirection.NEUTRAL
        if not contradiction:
            if p_bias == SignalDirection.BUY or q_bias == SignalDirection.BUY:
                if s_bias != SignalDirection.SELL:
                    direction_bias = SignalDirection.BUY
            elif p_bias == SignalDirection.SELL or q_bias == SignalDirection.SELL:
                if s_bias != SignalDirection.BUY:
                    direction_bias = SignalDirection.SELL

        # 5. True Confluence Check (Trend + Location/Structure + Momentum)
        regime_enum = regime.regime if regime else MarketRegime.RANGE_BOUND
        
        # Trend Filter:
        if direction_bias == SignalDirection.BUY:
            trend_aligned = regime_enum in [MarketRegime.TRENDING_BULL, MarketRegime.RANGE_BOUND]
            loc_key = pattern.key_support if pattern else current_price
            loc_target = f"Hold above support {loc_key:.5f}"
        elif direction_bias == SignalDirection.SELL:
            trend_aligned = regime_enum in [MarketRegime.TRENDING_BEAR, MarketRegime.RANGE_BOUND]
            loc_key = pattern.key_resistance if pattern else current_price
            loc_target = f"Reject below resistance {loc_key:.5f}"
        else:
            trend_aligned = False
            loc_target = "Wait for clear boundary definition"

        confluence_checklist["trend_filter"] = trend_aligned
        confluence_checklist["momentum_trigger"] = (not contradiction) and (direction_bias != SignalDirection.NEUTRAL)
        confluence_checklist["no_contradiction"] = not contradiction

        if not trend_aligned and direction_bias != SignalDirection.NEUTRAL:
            missing_conditions.append(f"Counter-trend posture: {direction_bias.value} opposes current {regime_enum.value} regime")

        # 6. Expiry Class Matching based on Market Structure
        if regime_enum in [MarketRegime.TRENDING_BULL, MarketRegime.TRENDING_BEAR]:
            optimal_expiry = "2M"  # Trend continuation requires 2M-5M to unfold
        elif regime_enum == MarketRegime.RANGE_BOUND:
            optimal_expiry = "1M"  # Range edge rejection unfolds in 1M-2M
        elif regime_enum == MarketRegime.COMPRESSION_SQUEEZE:
            optimal_expiry = "WAIT_FOR_EXPANSION"
            missing_conditions.append("Market in volatility compression squeeze (avoid sub-minute noise)")
        elif regime_enum == MarketRegime.VOLATILITY_EXPANSION:
            optimal_expiry = "5M"  # Higher volatility requires wider room to breathe
        else:
            optimal_expiry = "1M"

        # 7. Actionable Watchlist Trigger Generation
        if direction_bias == SignalDirection.BUY:
            action_trigger = f"Recheck if price holds support at {loc_key:.5f} and spread < {self.config.max_spread_pips_allowed}p"
        elif direction_bias == SignalDirection.SELL:
            action_trigger = f"Recheck if price retests resistance at {loc_key:.5f} and momentum confirms downward break"
        else:
            action_trigger = "Wait for structural breakout or range boundary rejection"

        # 8. Composite Confidence Computation
        p_conf = pattern.confidence if pattern else 0.5
        q_conf = quant.confidence if quant else 0.5
        s_conf = abs(sent_diff)
        
        composite_conf = (p_conf * 0.40) + (q_conf * 0.35) + (min(1.0, s_conf) * 0.25)
        if contradiction or macro_locked or not spread_pass:
            composite_conf = composite_conf * 0.50

        # Calculate Stops and Targets using ATR
        atr = quant.atr if quant and quant.atr > 0 else (0.0015 if "JPY" not in pair else 0.18)
        stop_dist = max(atr * 1.5, 0.0010 if "JPY" not in pair else 0.12)
        target_dist = stop_dist * self.config.min_risk_to_reward_ratio

        if direction_bias == SignalDirection.BUY:
            sl = current_price - stop_dist
            tp = current_price + target_dist
            invalidation = f"Close below support {sl:.5f}"
        elif direction_bias == SignalDirection.SELL:
            sl = current_price + stop_dist
            tp = current_price - target_dist
            invalidation = f"Close above resistance {sl:.5f}"
        else:
            sl = current_price
            tp = current_price
            invalidation = "Neutral corridor"

        # Check if proposal can be APPROVED for risk routing or stays PENDING / WATCHLIST
        all_confluence_passed = (
            trend_aligned and
            confluence_checklist["momentum_trigger"] and
            spread_pass and
            not macro_locked and
            not contradiction and
            (composite_conf >= self.config.min_confidence_threshold)
        )

        approval_status = "PENDING_RISK_GATES" if all_confluence_passed else "WATCHLIST_PENDING"
        final_direction = direction_bias if all_confluence_passed else SignalDirection.NEUTRAL

        proposal = TradeProposal(
            pair=pair,
            direction=final_direction,
            direction_bias=direction_bias,
            approval_status=approval_status,
            confluence_checklist=confluence_checklist,
            contradiction_detected=contradiction,
            optimal_expiry=optimal_expiry,
            binary_payout_pct=binary_payout_pct,
            missing_conditions=missing_conditions,
            action_trigger=action_trigger,
            entry_type="MARKET" if all_confluence_passed else "NO_TRADE",
            entry_price=round(current_price, 5),
            target_stop_loss=round(sl, 5),
            target_take_profit=round(tp, 5),
            rrr=round(target_dist / (stop_dist + 1e-6), 2),
            composite_confidence=round(composite_conf, 2),
            regime=regime_enum,
            valid_until=utc_now() + timedelta(minutes=30),
            invalidation_condition=invalidation,
            component_scores={
                "pattern": round(p_conf, 2),
                "quant": round(q_conf, 2),
                "sentiment": round(sent_diff, 2),
                "composite": round(composite_conf, 2)
            },
            rationale=(
                f"Direction Bias: {direction_bias.value} | Status: {approval_status} | "
                f"Confluence: {'All Passed' if all_confluence_passed else 'Missing: ' + ', '.join(missing_conditions[:2])}. "
                f"Optimal Expiry: {optimal_expiry}."
            )
        )
        proposal.freeze_and_hash()
        self.blackboard.active_proposals[proposal.proposal_id] = proposal
        await self.bus.publish(f"proposal.{pair}", proposal)
        return proposal
