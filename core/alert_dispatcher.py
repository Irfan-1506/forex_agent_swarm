"""
Alert & Notification Dispatcher (Inspired by trader-alerts in day-trader-skill).
Dispatches high-priority trading alerts, kill switch triggers, and structural breakout alarms.
"""
from typing import Dict, List, Any
from datetime import datetime
from core.models import utc_now

class AlertDispatcher:
    def __init__(self):
        self.alert_history: List[Dict[str, Any]] = []

    def dispatch_alert(self, title: str, message: str, severity: str = "INFO", pair: str = "ALL") -> Dict[str, Any]:
        alert = {
            "timestamp": utc_now().strftime("%H:%M:%S"),
            "severity": severity,  # "INFO", "WARNING", "CRITICAL", "TRADE"
            "pair": pair,
            "title": title,
            "message": message
        }
        self.alert_history.append(alert)
        if len(self.alert_history) > 100:
            self.alert_history.pop(0)
        return alert

    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        return list(reversed(self.alert_history[-limit:]))

global_alert_dispatcher = AlertDispatcher()
