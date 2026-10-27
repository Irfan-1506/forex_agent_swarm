"""
Gemini Explainer Module.
Strictly non-authoritative narrative generation:
Produces human-readable executive summaries, rationale breakdowns, and Quotex call-to-actions.
Never alters stops, sizing, entries, or risk veto decisions.
"""
import os
from typing import Dict, Any, Optional

class GeminiExplainer:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    def generate_explanation(
        self,
        pair: str,
        proposal: Dict[str, Any],
        risk_eval: Dict[str, Any],
        regime_report: Dict[str, Any],
        timeframe: str = "1M"
    ) -> Dict[str, Any]:
        """
        Synthesizes a structured briefing matching the institutional template:
        - Direction recommendation (CALL / PUT / WAIT) with confidence percentage
        - Market Snapshot & Metrics
        - Structural Breakdown
        - Strategic Framework & Rationale
        """
        direction = proposal.get("direction", "NEUTRAL")
        direction_bias = proposal.get("direction_bias", "NEUTRAL")
        optimal_expiry = proposal.get("optimal_expiry", "1M")
        confidence = proposal.get("composite_confidence", 0.5)
        conf_pct = int(confidence * 100)
        approved = risk_eval.get("approved", False)
        veto_reason = risk_eval.get("veto_reason")
        missing_conditions = risk_eval.get("missing_conditions", [])
        action_trigger = risk_eval.get("action_trigger")
        stake_usd = risk_eval.get("stake_amount_usd", 500.0)
        stake_pct = risk_eval.get("stake_pct", 0.5)
        regime = regime_report.get("regime", "RANGE_BOUND")
        entry = proposal.get("entry_price", 1.08500)
        sl = proposal.get("target_stop_loss", 1.08350)
        tp = proposal.get("target_take_profit", 1.08750)
        rrr = proposal.get("rrr", 1.6)

        # Quotex two-stage direct action
        if approved and direction == "BUY":
            quotex_action = "BUY / HIGHER (CALL)"
            action_badge = "CALL"
            theme_color = "#10b981"
        elif approved and direction == "SELL":
            quotex_action = "SELL / LOWER (PUT)"
            action_badge = "PUT"
            theme_color = "#ef4444"
        else:
            quotex_action = "WAIT / NO TRADE"
            action_badge = "WAIT"
            theme_color = "#f59e0b"

        # Deterministic structured narrative
        narrative_header = (
            f"**{pair}** ({timeframe}) — **Direction Bias: {direction_bias}** (Status: **{'APPROVED' if approved else 'WATCHLIST'}**). "
            f"Market is in **{regime.replace('_', ' ')}** at **{entry:.5f}**. "
            f"Edge score: **{conf_pct}%** → Instruction: **{quotex_action}** (Stake: {stake_pct}% / ${stake_usd:.2f})."
        )

        tm_metrics = risk_eval.get("timemachine_metrics")
        tm_text = ""
        quotex_asymmetry_text = ""
        if tm_metrics:
            p_win = tm_metrics.get("p_target_hit_pct", 50)
            ci_low = tm_metrics.get("ci_target_hit_95_lower", 48)
            ci_hi = tm_metrics.get("ci_target_hit_95_upper", 52)
            exp_r = tm_metrics.get("expected_payoff_r", 0)
            ci_r_low = tm_metrics.get("ci_expected_r_95_lower", -0.1)
            ci_r_hi = tm_metrics.get("ci_expected_r_95_upper", 0.1)
            model_name = tm_metrics.get("simulation_model", "Fat-Tailed Monte Carlo")
            session_name = tm_metrics.get("session_profile", {}).get("session", "MARKET_HOURS")
            
            tm_text = (
                f"• **{model_name} ({session_name})**: "
                f"Win Odds: {p_win}% [95% CI: {ci_low}% – {ci_hi}%] | "
                f"Expected Value: {exp_r:+.2f}R [95% CI: {ci_r_low:+.2f}R to {ci_r_hi:+.2f}R]."
            )
            
            be_rate = tm_metrics.get("quotex_breakeven_win_rate_pct", 54.05)
            bin_ci_low = tm_metrics.get("binary_ci_95_lower", 50.0)
            hurdle = tm_metrics.get("binary_hurdle_rate_pct", 56.05)
            cleared = tm_metrics.get("binary_odds_cleared", False)
            quotex_asymmetry_text = (
                f"• **Quotex Asymmetry & Break-Even Check**: "
                f"Break-Even hurdle is {be_rate:.1f}% (for 85% payout). 95% CI Lower Bound: {bin_ci_low:.1f}% vs Hurdle {hurdle:.1f}% → "
                f"{'EDGE VERIFIED' if cleared else 'VETOED: Edge does not clear break-even threshold after friction'}."
            )

        strategic_rationale = [
            f"• **Direction Bias & Expiry**: Candidate direction is **{direction_bias}** (Recommended Expiry: **{optimal_expiry}**).",
            f"• **Regime Context**: Asset is operating under {regime}. Volatility clustering & session liquidity modeled.",
            f"• **Risk Governance**: {'DIRECT INSTRUCTION: Approved with fixed ' + str(stake_pct) + '% stake ($' + str(round(stake_usd, 2)) + ')' if approved else 'WATCHLIST / VETO: ' + str(veto_reason)}.",
        ]
        if tm_text:
            strategic_rationale.insert(2, tm_text)
        if quotex_asymmetry_text:
            strategic_rationale.insert(3, quotex_asymmetry_text)

        # Append Action Trigger if in Watchlist state
        if not approved and action_trigger:
            strategic_rationale.append(f"• **Action Trigger**: {action_trigger}")
        if missing_conditions:
            conditions_summary = "; ".join(missing_conditions[:2])
            strategic_rationale.append(f"• **Pending Checklist Items**: {conditions_summary}")

        # Append Quotex Regulatory & Simulation Warning
        strategic_rationale.append(
            "• **Quotex Safety Warning**: Simulation mode strictly enforced. Binary options feature 100% loss vs ~85% win asymmetry; live execution blocked pending out-of-sample edge proof."
        )

        # If live Gemini client is available, ask it to polish explanation without modifying values
        if self.client:
            try:
                prompt = (
                    f"You are the Explainer for an algorithmic Forex trading swarm. Summarize this trade state for a trader on Quotex:\n"
                    f"Pair: {pair}, Timeframe: {timeframe}, Action: {quotex_action}, Confidence: {conf_pct}%, Price: {entry}, SL: {sl}, TP: {tp}, RRR: {rrr}, Approved: {approved}, Reason: {veto_reason}.\n"
                    f"Keep it concise, professional, and clear. Do not alter prices, stops, or decisions."
                )
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                if response.text:
                    polished_text = response.text
                else:
                    polished_text = narrative_header
            except Exception:
                polished_text = narrative_header
        else:
            polished_text = narrative_header

        return {
            "quotex_action": quotex_action,
            "action_badge": action_badge,
            "direction_bias": direction_bias,
            "approval_status": "APPROVED" if approved else "WATCHLIST",
            "optimal_expiry": optimal_expiry,
            "missing_conditions": missing_conditions,
            "action_trigger": action_trigger,
            "stake_amount_usd": round(stake_usd, 2),
            "stake_pct": stake_pct,
            "theme_color": theme_color,
            "confidence_pct": conf_pct,
            "narrative_summary": polished_text,
            "strategic_rationale": strategic_rationale,
            "approved": approved,
            "veto_reason": veto_reason
        }
