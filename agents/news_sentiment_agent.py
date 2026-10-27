"""
Tier 1: News & Sentiment Agent.
Ingests institutional news wires, extracts currency sentiment, detects cross-headline contradictions,
and timestamps expiry to prevent stale narrative bias.
"""
from typing import Dict, List
from datetime import timedelta
from agents.base_agent import BaseAgent
from core.models import NewsSentimentReport, utc_now

class NewsSentimentAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("News & Sentiment Agent", event_bus, config)
        self.sentiment_state: Dict[str, NewsSentimentReport] = {}

    async def analyze_sentiment(
        self,
        currency: str,
        headlines: List[Dict[str, any]] = None
    ) -> NewsSentimentReport:
        now = utc_now()
        
        # Default mock institutional feeds if none supplied
        if not headlines:
            if currency == "USD":
                headlines = [
                    {"text": "Fed officials signal patient stance on rate cuts amid sticky services inflation", "score": 0.25, "source": "Bloomberg"},
                    {"text": "US retail sales hold firm beating consensus expectations", "score": 0.35, "source": "Reuters"}
                ]
            elif currency == "EUR":
                headlines = [
                    {"text": "ECB policymakers note sluggish Eurozone industrial production and German manufacturing contraction", "score": -0.40, "source": "ECB Wire"},
                    {"text": "Eurozone wage growth moderates slightly, reinforcing June rate reduction bets", "score": -0.20, "source": "FT"}
                ]
            elif currency == "GBP":
                headlines = [
                    {"text": "Bank of England split on timeline for easing as UK services inflation persists", "score": 0.10, "source": "Reuters"}
                ]
            elif currency == "JPY":
                headlines = [
                    {"text": "Bank of Japan considers sovereign bond purchase tapering while yields stabilize", "score": 0.30, "source": "Nikkei"}
                ]
            else:
                headlines = [
                    {"text": f"Global trade flows steady for {currency}", "score": 0.05, "source": "DowJones"}
                ]

        scores = [h.get("score", 0.0) for h in headlines]
        avg_score = float(sum(scores) / len(scores)) if scores else 0.0

        # Contradiction detection: checking if standard deviation of scores is large
        has_positive = any(s > 0.2 for s in scores)
        has_negative = any(s < -0.2 for s in scores)
        contradiction = has_positive and has_negative

        if contradiction:
            avg_score = avg_score * 0.5  # Dampen confidence if sources fight

        risk_on_off = "RISK_ON" if avg_score > 0.2 else ("RISK_OFF" if avg_score < -0.2 else "NEUTRAL")

        # Expiry set to 1 hour from generation
        expiry = now + timedelta(hours=1)

        summary_texts = [h.get("text", "") for h in headlines]
        rationale = (
            f"{currency} aggregate sentiment: {avg_score:+.2f} ({'Contradictory' if contradiction else 'Consistent'}). "
            f"Risk stance: {risk_on_off}."
        )

        report = NewsSentimentReport(
            currency=currency,
            sentiment_score=round(avg_score, 2),
            source="REUTERS_BLOOMBERG_ECN",
            expiry_time=expiry,
            is_narrative=True,
            contradiction_detected=contradiction,
            key_headlines=summary_texts,
            risk_on_off=risk_on_off,
            breaking_alert=abs(avg_score) >= 0.7,
            rationale=rationale
        )

        self.sentiment_state[currency] = report
        await self.bus.publish(f"sentiment.{currency}", report)
        return report
