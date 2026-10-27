"""
Tier 1: Macro & Calendar Agent.
Monitors high-impact macroeconomic releases, enforces hard trading blackout windows,
and models release surprise magnitude against forecasts.
"""
from datetime import datetime, timezone
from typing import Optional, Dict
from agents.base_agent import BaseAgent
from core.models import MacroEventReport, EventImpact, MacroState, utc_now
from core.alert_dispatcher import global_alert_dispatcher

class MacroCalendarAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Macro & Calendar Agent", event_bus, config)
        self.active_events: Dict[str, MacroEventReport] = {}

    async def evaluate_economic_schedule(
        self,
        currency: str,
        upcoming_event: Optional[Dict[str, any]] = None
    ) -> MacroEventReport:
        now = utc_now()
        
        # Default calendar state if not provided
        if not upcoming_event:
            # Clean schedule scenario
            return MacroEventReport(
                event_name="No Imminent Tier-1 Release",
                currency=currency,
                impact=EventImpact.LOW,
                state=MacroState.CLEAR,
                surprise_magnitude_std=0.0,
                lock_trading_window=False,
                size_reduction_pct=0.0,
                rationale=f"Calendar clear for {currency}. No high-impact releases scheduled within 60 minutes."
            )

        name = upcoming_event.get("name", "High Impact Release")
        impact_level = upcoming_event.get("impact", EventImpact.HIGH)
        event_time: datetime = upcoming_event.get("time", now)
        minutes_until = (event_time - now).total_seconds() / 60.0

        # State determination
        if minutes_until > 0 and minutes_until <= self.config.hard_blackout_minutes:
            state = MacroState.PRE_EVENT
            lock_trading = (impact_level == EventImpact.HIGH)
            size_reduction = 0.5 if impact_level == EventImpact.MEDIUM else 1.0
            rationale = f"PRE-EVENT HARD BLACKOUT: '{name}' in {minutes_until:.1f}m. Trading locked to prevent slippage gaps."
        elif minutes_until <= 0 and abs(minutes_until) <= 5.0:
            state = MacroState.RELEASE
            lock_trading = True
            size_reduction = 1.0
            rationale = f"RELEASE EVENT LIVE: '{name}' is currently broadcasting. Spreads widened, execution disabled."
        elif minutes_until < 0 and abs(minutes_until) <= self.config.soft_blackout_minutes:
            state = MacroState.POST_EVENT
            lock_trading = False
            size_reduction = 0.5
            rationale = f"POST-EVENT COOLDOWN: '{name}' released {abs(minutes_until):.1f}m ago. Position size halved."
        else:
            state = MacroState.CLEAR
            lock_trading = False
            size_reduction = 0.0
            rationale = f"Calendar calm for {currency}. Next event in {minutes_until:.1f}m."

        # Surprise calculation if actual numbers exist
        actual = upcoming_event.get("actual")
        forecast = upcoming_event.get("forecast")
        previous = upcoming_event.get("previous")
        surprise_std = 0.0

        if actual is not None and forecast is not None:
            # Normalized surprise proxy
            diff = actual - forecast
            surprise_std = round(diff / (abs(forecast) * 0.1 + 1e-4), 2)

        if lock_trading:
            global_alert_dispatcher.dispatch_alert(
                title=f"Macro Blackout Active ({currency})",
                message=f"Event: {name}. Trading locked for {currency}.",
                severity="WARNING"
            )

        report = MacroEventReport(
            event_name=name,
            currency=currency,
            impact=impact_level,
            state=state,
            actual=actual,
            forecast=forecast,
            previous=previous,
            surprise_magnitude_std=surprise_std,
            lock_trading_window=lock_trading,
            size_reduction_pct=size_reduction,
            rationale=rationale
        )

        self.active_events[currency] = report
        await self.bus.publish(f"macro.{currency}", report)
        return report
