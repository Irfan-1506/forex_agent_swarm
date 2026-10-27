"""
Tier 0 Safety: Emergency Halt Agent.
Provides global automated circuit breakers and manual kill switches to immediately freeze trading.
"""
from agents.base_agent import BaseAgent
from core.models import EmergencyHaltStatus, utc_now
from core.alert_dispatcher import global_alert_dispatcher

class EmergencyHaltAgent(BaseAgent):
    def __init__(self, event_bus, config=None):
        super().__init__("Emergency Halt Agent", event_bus, config)
        self.consecutive_errors = 0
        self.is_halted = False
        self.halt_reason = None

    async def record_execution_error(self, error_msg: str):
        self.consecutive_errors += 1
        if self.consecutive_errors >= self.config.max_consecutive_execution_errors and not self.is_halted:
            await self.trigger_kill_switch(
                f"MAX_CONSECUTIVE_ERRORS_EXCEEDED ({self.consecutive_errors}): {error_msg}",
                triggered_by="SYSTEM_CIRCUIT_BREAKER"
            )

    async def record_successful_execution(self):
        self.consecutive_errors = 0

    async def trigger_kill_switch(self, reason: str, triggered_by: str = "MANUAL_OPERATOR"):
        self.is_halted = True
        self.halt_reason = reason
        status = EmergencyHaltStatus(
            is_halted=True,
            halt_reason=reason,
            kill_switch_triggered_by=triggered_by,
            consecutive_errors=self.consecutive_errors,
            timestamp=utc_now()
        )
        await self.bus.publish("emergency.halt", status)
        global_alert_dispatcher.dispatch_alert(
            title="EMERGENCY KILL SWITCH TRIGGERED",
            message=f"Swarm halted by {triggered_by}. Reason: {reason}",
            severity="CRITICAL"
        )

    async def reset_kill_switch(self, operator: str = "MANUAL_OPERATOR"):
        self.is_halted = False
        self.halt_reason = None
        self.consecutive_errors = 0
        status = EmergencyHaltStatus(
            is_halted=False,
            halt_reason=None,
            kill_switch_triggered_by=None,
            consecutive_errors=0,
            timestamp=utc_now()
        )
        await self.bus.publish("emergency.halt", status)
        global_alert_dispatcher.dispatch_alert(
            title="Emergency Halt Cleared",
            message=f"Trading unhalted by {operator}. Resuming operations.",
            severity="INFO"
        )

    def is_active_halt(self) -> bool:
        return self.is_halted
