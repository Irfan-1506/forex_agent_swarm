"""
Base Agent Class for all Swarm Agents.
"""
from typing import Optional, Any
from core.bus import SwarmEventBus, SwarmBlackboard
from config import config as global_config

class BaseAgent:
    def __init__(self, name: str, event_bus: Any, config=None):
        self.name = name
        self.event_bus = event_bus
        self.bus = event_bus
        if hasattr(event_bus, "blackboard"):
            self.blackboard: SwarmBlackboard = event_bus.blackboard
        else:
            self.blackboard: SwarmBlackboard = event_bus
        self.config = config or global_config

    def log(self, message: str, style: str = "info"):
        # Can be hooked into console or logger
        pass

    async def log_activity(self, message: str):
        pass
