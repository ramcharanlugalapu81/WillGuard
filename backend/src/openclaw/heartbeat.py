"""
OpenClaw Heartbeat
━━━━━━━━━━━━━━━━━━
User activity tracker and heartbeat loop.
Runs every N seconds, pinging for user presence.
Feeds signals into the Inactivity Detector.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Callable, Optional

from ..intelligence.inactivity_detector import InactivityDetector, ActivitySignal


class HeartbeatMonitor:
    """
    Continuous heartbeat loop that:
    1. Tracks all user activity signals
    2. Periodically checks inactivity confidence
    3. Triggers mode transitions via callbacks
    """

    def __init__(
        self,
        inactivity_detector: InactivityDetector,
        interval_seconds: int = 30,  # Check every 30s for demo (normally 1800)
        on_guardian_trigger: Optional[Callable] = None,
        on_lockdown_trigger: Optional[Callable] = None,
        on_activity_detected: Optional[Callable] = None,
    ):
        self.detector = inactivity_detector
        self.interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_guardian_trigger = on_guardian_trigger
        self.on_lockdown_trigger = on_lockdown_trigger
        self.on_activity_detected = on_activity_detected

        # State
        self._guardian_triggered = False
        self._lockdown_triggered = False

    def record_activity(self, signal: ActivitySignal = ActivitySignal.API_CALL):
        """Record user activity — resets inactivity tracking."""
        self.detector.record_activity(signal)
        self._guardian_triggered = False
        self._lockdown_triggered = False

        if self.on_activity_detected:
            try:
                self.on_activity_detected()
            except Exception:
                pass

    async def start(self):
        """Start the heartbeat loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        """Stop the heartbeat loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        """Main heartbeat loop — Perceive → Check → Act."""
        while self._running:
            try:
                result = self.detector.get_confidence()
                confidence = result["confidence"]

                # Check for Guardian Mode trigger
                if result["should_trigger_guardian"] and not self._guardian_triggered:
                    self._guardian_triggered = True
                    if self.on_guardian_trigger:
                        self.on_guardian_trigger(confidence, result["reasoning"])

                # Check for Lockdown Mode trigger
                if result["should_trigger_lockdown"] and not self._lockdown_triggered:
                    self._lockdown_triggered = True
                    if self.on_lockdown_trigger:
                        self.on_lockdown_trigger(confidence, result["reasoning"])

                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Heartbeat] Error in loop: {e}")
                await asyncio.sleep(self.interval)

    def get_status(self) -> dict:
        """Get current heartbeat status."""
        result = self.detector.get_confidence()
        return {
            "running": self._running,
            "interval_seconds": self.interval,
            "inactivity": result,
            "guardian_triggered": self._guardian_triggered,
            "lockdown_triggered": self._lockdown_triggered,
        }
