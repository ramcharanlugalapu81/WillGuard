"""
OpenClaw Agent
━━━━━━━━━━━━━━
The main autonomous multi-step reasoning agent.
Runs the continuous loop: Perceive → Reason → Act → Loop.

This is the orchestrator that ties together:
- ArmorClaw (enforcement)
- Intelligence Layer (risk scoring, inactivity, tone)
- Alpaca Executor (trade execution)
- Memory (markdown-based persistence)
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from ..armorclaw.enforcer import (
    ArmorClawEnforcer, TradeProposal, EnforcementDecision,
    SystemMode, EnforcementZone, ActionType,
)
from ..armorclaw.policy_loader import get_will
from ..intelligence.risk_scorer import RiskScorer
from ..intelligence.inactivity_detector import InactivityDetector, ActivitySignal
from ..intelligence.tone_classifier import ToneClassifier
from ..openclaw.heartbeat import HeartbeatMonitor
from ..openclaw.memory import MarkdownMemory


class OpenClawAgent:
    """
    The main WillGuard agent.

    Architecture:
    ┌──────────────────────────────────────────┐
    │  OpenClaw Agent (this class)             │
    │  ┌────────────────────────────────────┐  │
    │  │  Perceive: Heartbeat + Signals     │  │
    │  │  Reason:   Risk Score + Tone       │  │
    │  │  Act:      Execute or Block        │  │
    │  │  Enforce:  ArmorClaw (always)      │  │
    │  └────────────────────────────────────┘  │
    └──────────────────────────────────────────┘
    """

    def __init__(self):
        # Core components
        self.enforcer = ArmorClawEnforcer()
        self.risk_scorer = RiskScorer()
        self.inactivity_detector = InactivityDetector(
            guardian_threshold_seconds=int(get_will().inactivity.guardian_mode_seconds),
            lockdown_threshold_seconds=int(get_will().inactivity.lockdown_mode_seconds),
        )
        self.tone_classifier = ToneClassifier()
        self.memory = MarkdownMemory()

        # Heartbeat with callbacks
        self.heartbeat = HeartbeatMonitor(
            inactivity_detector=self.inactivity_detector,
            interval_seconds=10,  # Fast for demo
            on_guardian_trigger=self._on_guardian,
            on_lockdown_trigger=self._on_lockdown,
            on_activity_detected=self._on_activity,
        )

        # Event subscribers (for WebSocket broadcast)
        self._event_subscribers: list = []

    def subscribe(self, callback):
        """Subscribe to agent events (for WebSocket)."""
        self._event_subscribers.append(callback)

    def _broadcast(self, event_type: str, data: dict):
        """Broadcast event to all subscribers."""
        event = {"type": event_type, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()}
        for cb in self._event_subscribers:
            try:
                cb(event)
            except Exception:
                pass

    # ── Mode Transition Callbacks ─────────────────────────

    def _on_guardian(self, confidence: float, reasoning: str):
        """Called when inactivity triggers Guardian Mode."""
        self.enforcer.set_mode(
            SystemMode.GUARDIAN,
            f"Inactivity confidence {confidence:.0%}: {reasoning}"
        )

        # Save to memory
        self.memory.save(
            "alerts",
            "Guardian Mode Activated",
            f"System entered Guardian Mode.\n\n"
            f"**Confidence:** {confidence:.0%}\n"
            f"**Reason:** {reasoning}\n\n"
            f"All new trades are now blocked. Existing positions held.",
            metadata={"mode": "guardian", "confidence": str(confidence)},
        )

        self._broadcast("mode_change", {
            "mode": "guardian",
            "confidence": confidence,
            "reasoning": reasoning,
        })

    def _on_lockdown(self, confidence: float, reasoning: str):
        """Called when extended inactivity triggers Lockdown Mode."""
        self.enforcer.set_mode(
            SystemMode.LOCKDOWN,
            f"Inactivity confidence {confidence:.0%}: {reasoning}"
        )

        self.memory.save(
            "alerts",
            "LOCKDOWN Mode Activated",
            f"⚠️ System entered LOCKDOWN Mode.\n\n"
            f"**Confidence:** {confidence:.0%}\n"
            f"**Reason:** {reasoning}\n\n"
            f"Full trade freeze active. Trustee access elevated.",
            metadata={"mode": "lockdown", "confidence": str(confidence)},
        )

        self._broadcast("mode_change", {
            "mode": "lockdown",
            "confidence": confidence,
            "reasoning": reasoning,
        })

    def _on_activity(self):
        """Called when user activity is detected."""
        if self.enforcer.state.mode != SystemMode.COPILOT:
            self.enforcer.set_mode(SystemMode.COPILOT, "User activity detected")
            self._broadcast("mode_change", {
                "mode": "copilot",
                "confidence": 0.0,
                "reasoning": "User activity detected — returning to Co-Pilot mode",
            })

    # ── Trade Processing Pipeline ─────────────────────────

    async def process_trade(
        self,
        symbol: str,
        action: str,
        quantity: float,
        price: float = None,
        message: str = None,
        source: str = "user",
    ) -> dict:
        """
        The main trade processing pipeline.

        Flow:
        1. Record activity (user is present)
        2. Build trade proposal
        3. Score risk (LLM + fallback)
        4. Classify tone (if message provided)
        5. ArmorClaw enforcement
        6. Execute or block
        7. Log everything
        """
        # Step 1: Record activity
        if source == "user":
            self.heartbeat.record_activity(ActivitySignal.TRADE_ACTION)

        # Step 2: Build proposal
        estimated_value = quantity * (price or 150.0)  # Default price estimate
        proposal = TradeProposal(
            symbol=symbol,
            action=ActionType(action.lower()),
            quantity=quantity,
            price=price,
            estimated_value=estimated_value,
            source=source,
            message=message,
        )

        # Step 3: Risk scoring
        will = get_will()
        risk_result = self.risk_scorer.score(
            symbol=symbol,
            action=action,
            value=estimated_value,
            goals=[g.model_dump() for g in will.goals],
            risk_floor=will.risk_floor.model_dump(),
        )

        # Step 4: Tone classification
        tone_result = {"flags": [], "severity": "low", "reasoning": "No message"}
        if message:
            tone_result = self.tone_classifier.classify(message)

        # Step 5: ArmorClaw enforcement (THE KEY STEP)
        decision = self.enforcer.evaluate(
            proposal=proposal,
            risk_score=risk_result["total"],
            tone_flags=tone_result.get("flags", []),
        )

        # Step 6: Build response
        result = {
            "decision": {
                "zone": decision.zone.value,
                "allowed": decision.allowed,
                "reason": decision.reason,
                "rule_triggered": decision.rule_triggered,
            },
            "risk_score": risk_result,
            "tone_analysis": tone_result,
            "proposal": {
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "price": price,
                "estimated_value": estimated_value,
            },
            "system_mode": self.enforcer.state.mode.value,
        }

        # Step 7: Save to memory
        zone_emoji = {"EXECUTE": "✅", "NOTIFY": "⚠️", "FREEZE": "🛑"}.get(decision.zone.value, "❓")
        self.memory.save(
            "decisions",
            f"{zone_emoji} {decision.zone.value}: {symbol} {action}",
            f"**Trade:** {action} {quantity} {symbol} @ ${price or 'market'}\n"
            f"**Value:** ${estimated_value:,.2f}\n"
            f"**Risk Score:** {risk_result['total']:.3f} ({risk_result['method']})\n"
            f"**Zone:** {decision.zone.value}\n"
            f"**Allowed:** {decision.allowed}\n"
            f"**Reason:** {decision.reason}\n"
            f"**Rule:** {decision.rule_triggered}\n",
            metadata={"zone": decision.zone.value, "risk": str(risk_result["total"])},
        )

        # Record trade in history (for future risk scoring baselines)
        if decision.allowed:
            self.risk_scorer.record_trade(symbol, estimated_value)

        # Broadcast to WebSocket
        self._broadcast("trade_decision", result)

        return result

    # ── System Controls ───────────────────────────────────

    async def start(self):
        """Start the agent (begins heartbeat loop)."""
        await self.heartbeat.start()
        self.memory.save("system", "Agent Started", "OpenClaw agent started. Heartbeat loop active.")
        self._broadcast("system", {"event": "agent_started"})

    async def stop(self):
        """Stop the agent."""
        await self.heartbeat.stop()
        self.memory.save("system", "Agent Stopped", "OpenClaw agent stopped.")

    def record_activity(self, signal: str = "api_call"):
        """Record user activity from external source."""
        sig = ActivitySignal(signal)
        self.heartbeat.record_activity(sig)

    def simulate_inactivity(self, seconds: int):
        """Simulate inactivity for demo purposes."""
        self.inactivity_detector.simulate_inactivity(seconds)
        # Force a check
        result = self.inactivity_detector.get_confidence()
        self.enforcer.update_inactivity(result["confidence"])
        self._broadcast("inactivity_update", result)

    def get_full_status(self) -> dict:
        """Get complete system status."""
        return {
            "enforcer": self.enforcer.get_status(),
            "heartbeat": self.heartbeat.get_status(),
            "memory": self.memory.recall_all_categories(),
            "ledger_entries": self.enforcer.ledger.get_entries(limit=20),
        }

    def reset(self):
        """Reset the agent to initial state (for demo reruns)."""
        self.enforcer.state.mode = SystemMode.COPILOT
        self.enforcer.state.inactivity_confidence = 0.0
        self.enforcer.state.total_trades_today = 0
        self.enforcer.state.daily_volume = 0.0
        self.enforcer.state.portfolio_value = 100000.0
        self.enforcer.state.pending_notifications = []
        self.enforcer.state.alerts_sent = []
        self.inactivity_detector.reset()
        self.heartbeat._guardian_triggered = False
        self.heartbeat._lockdown_triggered = False
        self.memory.clear()
        self.enforcer.ledger._entries.clear()
        self._broadcast("system", {"event": "agent_reset"})
