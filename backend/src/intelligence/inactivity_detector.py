"""
Inactivity Detector
━━━━━━━━━━━━━━━━━━━
Multi-signal confidence scoring system for detecting genuine user absence.
Combines: login timestamps, API call frequency, heartbeat responses.
NOT just a timer — computes a confidence score before triggering Guardian Mode.
Has a grace check before activation to prevent false triggers.
"""

import time
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


class ActivitySignal(str, Enum):
    LOGIN = "login"
    API_CALL = "api_call"
    HEARTBEAT_RESPONSE = "heartbeat_response"
    TRADE_ACTION = "trade_action"
    DASHBOARD_VIEW = "dashboard_view"
    MANUAL_OVERRIDE = "manual_override"


class InactivityDetector:
    """
    Multi-signal inactivity detector.

    Unlike a simple timer, this system tracks MULTIPLE activity signals
    and computes a confidence score that the user is genuinely absent.

    Signals weighted by reliability:
    - Trade actions:       0.35 (strongest signal of presence)
    - Heartbeat responses: 0.25 (explicit liveness check)
    - API calls:           0.20 (programmatic activity)
    - Dashboard views:     0.15 (passive viewing)
    - Login events:        0.05 (single event)
    """

    SIGNAL_WEIGHTS = {
        ActivitySignal.TRADE_ACTION: 0.35,
        ActivitySignal.HEARTBEAT_RESPONSE: 0.25,
        ActivitySignal.API_CALL: 0.20,
        ActivitySignal.DASHBOARD_VIEW: 0.15,
        ActivitySignal.LOGIN: 0.05,
    }

    def __init__(
        self,
        guardian_threshold_seconds: int = 14400,   # 4 hours
        lockdown_threshold_seconds: int = 86400,   # 24 hours
    ):
        self.guardian_threshold = guardian_threshold_seconds
        self.lockdown_threshold = lockdown_threshold_seconds

        # Track last activity per signal type
        self._last_signals: dict[ActivitySignal, float] = {}
        self._grace_check_pending = False
        self._grace_check_sent_at: Optional[float] = None
        self._grace_check_timeout = 300  # 5 minutes to respond

        # Initialize with current time
        now = time.time()
        for signal in ActivitySignal:
            self._last_signals[signal] = now

    def record_activity(self, signal: ActivitySignal):
        """Record an activity signal from the user."""
        self._last_signals[signal] = time.time()
        self._grace_check_pending = False
        self._grace_check_sent_at = None

    def get_confidence(self) -> dict:
        """
        Calculate inactivity confidence (0.0 = definitely active, 1.0 = definitely absent).

        Returns a detailed breakdown:
        {
            "confidence": 0.0-1.0,
            "signals": { signal_name: seconds_since_last },
            "should_trigger_guardian": bool,
            "should_trigger_lockdown": bool,
            "grace_check_pending": bool,
            "reasoning": "..."
        }
        """
        now = time.time()
        signal_ages = {}
        weighted_score = 0.0

        for signal, weight in self.SIGNAL_WEIGHTS.items():
            last = self._last_signals.get(signal, 0)
            age_seconds = now - last
            signal_ages[signal.value] = round(age_seconds, 1)

            # Normalize age against guardian threshold
            # 0 = just happened, 1 = threshold reached
            normalized = min(age_seconds / self.guardian_threshold, 1.0)
            weighted_score += weight * normalized

        # Apply non-linear scaling (accelerate near threshold)
        # This makes the confidence ramp up faster as we approach thresholds
        confidence = min(weighted_score ** 1.3, 1.0)

        # Grace check logic
        should_guardian = confidence >= 0.6
        should_lockdown = confidence >= 0.9

        # If approaching guardian but no grace check sent yet
        if confidence >= 0.5 and not self._grace_check_pending:
            self._grace_check_pending = True
            self._grace_check_sent_at = now

        # If grace check was sent and timed out, confidence is confirmed
        if self._grace_check_pending and self._grace_check_sent_at:
            grace_elapsed = now - self._grace_check_sent_at
            if grace_elapsed < self._grace_check_timeout:
                # Still within grace period — reduce confidence slightly
                confidence = min(confidence, 0.55)
                should_guardian = False

        # Build reasoning
        most_recent_signal = min(signal_ages, key=signal_ages.get)
        oldest_signal = max(signal_ages, key=signal_ages.get)
        reasoning = (
            f"Most recent activity: {most_recent_signal} ({signal_ages[most_recent_signal]:.0f}s ago). "
            f"Oldest signal: {oldest_signal} ({signal_ages[oldest_signal]:.0f}s ago). "
            f"Weighted inactivity confidence: {confidence:.1%}."
        )

        return {
            "confidence": round(confidence, 3),
            "signals": signal_ages,
            "should_trigger_guardian": should_guardian,
            "should_trigger_lockdown": should_lockdown,
            "grace_check_pending": self._grace_check_pending,
            "reasoning": reasoning,
        }

    def simulate_inactivity(self, seconds: int):
        """
        Simulate user being inactive for N seconds.
        Used for demo purposes — pushes all signal timestamps back.
        """
        for signal in self._last_signals:
            self._last_signals[signal] -= seconds

    def reset(self):
        """Reset all signals to now (user is definitely active)."""
        now = time.time()
        for signal in ActivitySignal:
            self._last_signals[signal] = now
        self._grace_check_pending = False
        self._grace_check_sent_at = None
