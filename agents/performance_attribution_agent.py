"""
Tier 4: Performance Attribution Agent.
Dissects trading performance by agent component, market regime, and setup type.
Calculates factor attribution to verify which sub-agents delivered real alpha.
"""
from typing import Dict, List, Any
from collections import defaultdict
from agents.base_agent import BaseAgent
from core.models import AuditRecord

class PerformanceAttributionAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Performance Attribution Agent", event_bus, config)
        self.regime_performance: Dict[str, List[float]] = defaultdict(list)
        self.agent_alpha_scores: Dict[str, float] = {
            "pattern": 0.0,
            "quant": 0.0,
            "sentiment": 0.0,
            "macro": 0.0
        }

    async def ingest_audit(self, audit: AuditRecord):
        # Attribute by regime
        regime_name = audit.belief_snapshot.regime.value if (audit.belief_snapshot and hasattr(audit.belief_snapshot.regime, "value")) else "UNKNOWN"
        self.regime_performance[regime_name].append(audit.r_multiple)

        # Attribute to agents based on alignment with final outcome
        if audit.belief_snapshot:
            r = audit.r_multiple
            if audit.belief_snapshot.pattern_signal > 0.5:
                self.agent_alpha_scores["pattern"] += r * 0.4
            if audit.belief_snapshot.quant_signal > 0.5:
                self.agent_alpha_scores["quant"] += r * 0.3
            if abs(audit.belief_snapshot.sentiment_signal) > 0.2:
                self.agent_alpha_scores["sentiment"] += r * 0.2

    def get_attribution_summary(self) -> Dict[str, Any]:
        audits = self.blackboard.completed_audits
        total_trades = len(audits)
        if total_trades == 0:
            return {
                "total_audited_trades": 0,
                "overall_win_rate_pct": 0.0,
                "cumulative_r": 0.0,
                "expectancy_r": 0.0,
                "regime_breakdown": {},
                "agent_alpha_attribution": self.agent_alpha_scores
            }

        wins = [a for a in audits if a.r_multiple > 0]
        cumulative_r = sum(a.r_multiple for a in audits)
        win_rate = (len(wins) / total_trades) * 100.0
        expectancy = cumulative_r / total_trades

        regime_stats = {}
        for reg, r_list in self.regime_performance.items():
            regime_stats[reg] = {
                "trades": len(r_list),
                "avg_r": round(sum(r_list) / len(r_list), 2) if r_list else 0.0,
                "win_rate_pct": round(len([r for r in r_list if r > 0]) / len(r_list) * 100.0, 1) if r_list else 0.0
            }

        return {
            "total_audited_trades": total_trades,
            "overall_win_rate_pct": round(win_rate, 1),
            "cumulative_r": round(cumulative_r, 2),
            "expectancy_r": round(expectancy, 2),
            "regime_breakdown": regime_stats,
            "agent_alpha_attribution": {k: round(v, 2) for k, v in self.agent_alpha_scores.items()}
        }
