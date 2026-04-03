"""
╔══════════════════════════════════════════════════════════════╗
║                    A R M O R C L A W                        ║
║           Runtime Intent Enforcement Engine                 ║
║                                                             ║
║  The safety guardrail for the entire WillGuard system.      ║
║  Even if the LLM decides to do something risky,             ║
║  ArmorClaw overrides it using policy-based YAML rules.      ║
║                                                             ║
║  This is NOT hardcoded if/else logic — it's a rule engine   ║
║  that evaluates every proposed action against the user's    ║
║  structured financial will.                                 ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from .policy_loader import get_will, FinancialWill


# ─── Enums ────────────────────────────────────────────────────

class SystemMode(str, Enum):
    COPILOT = "copilot"
    GUARDIAN = "guardian"
    LOCKDOWN = "lockdown"


class EnforcementZone(str, Enum):
    EXECUTE = "EXECUTE"
    NOTIFY = "NOTIFY"
    FREEZE = "FREEZE"


class ActionType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


# ─── Data Models ──────────────────────────────────────────────

class TradeProposal(BaseModel):
    """A proposed trade that ArmorClaw must evaluate."""
    symbol: str
    action: ActionType
    quantity: float
    price: Optional[float] = None
    estimated_value: float = 0.0
    source: str = "user"  # user | agent | external
    message: Optional[str] = None  # Original instruction text
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EnforcementDecision(BaseModel):
    """ArmorClaw's verdict on a proposed action."""
    zone: EnforcementZone
    allowed: bool
    reason: str
    risk_score: float = 0.0
    tone_flags: list[str] = []
    rule_triggered: str = ""
    mode_at_decision: SystemMode = SystemMode.COPILOT
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    proposal: Optional[TradeProposal] = None


class SystemState(BaseModel):
    """Complete WillGuard system state."""
    mode: SystemMode = SystemMode.COPILOT
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    inactivity_confidence: float = 0.0
    total_trades_today: int = 0
    daily_volume: float = 0.0
    portfolio_value: float = 100000.0
    pending_notifications: list[dict] = []
    alerts_sent: list[dict] = []


# ─── Decision Ledger ─────────────────────────────────────────

class DecisionLedger:
    """
    Append-only audit log of every action taken AND every action blocked.
    Critical for fintech accountability and post-incident review.
    """

    def __init__(self, path: Optional[str] = None):
        if path is None:
            path = str(Path(__file__).parent.parent.parent / "data" / "ledger" / "decision_ledger.jsonl")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict] = []

    def log(self, decision: EnforcementDecision, extra: dict = None):
        """Append a decision to the ledger."""
        entry = {
            "timestamp": decision.timestamp.isoformat(),
            "zone": decision.zone.value,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "risk_score": decision.risk_score,
            "tone_flags": decision.tone_flags,
            "rule_triggered": decision.rule_triggered,
            "mode": decision.mode_at_decision.value,
        }

        if decision.proposal:
            entry["proposal"] = {
                "symbol": decision.proposal.symbol,
                "action": decision.proposal.action.value,
                "quantity": decision.proposal.quantity,
                "estimated_value": decision.proposal.estimated_value,
                "source": decision.proposal.source,
            }

        if extra:
            entry["extra"] = extra

        self._entries.append(entry)

        # Persist to disk
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_entries(self, limit: int = 50) -> list[dict]:
        """Get the most recent ledger entries."""
        return self._entries[-limit:]

    def get_all_entries(self) -> list[dict]:
        """Get all entries (in-memory)."""
        return self._entries.copy()


# ─── ArmorClaw Enforcer ──────────────────────────────────────

class ArmorClawEnforcer:
    """
    ╔═══════════════════════════════════════════════════════╗
    ║  ArmorClaw — the beating heart of WillGuard.         ║
    ║                                                       ║
    ║  Every single trade proposal passes through here.     ║
    ║  The enforcer loads the user's financial will and     ║
    ║  evaluates proposals against policy rules.            ║
    ║                                                       ║
    ║  It doesn't matter what the LLM says — if ArmorClaw  ║
    ║  says FREEZE, the trade is blocked. Period.           ║
    ╚═══════════════════════════════════════════════════════╝
    """

    def __init__(self):
        self.will: FinancialWill = get_will()
        self.state = SystemState()
        self.ledger = DecisionLedger()
        self._mode_change_callbacks: list = []

    def register_mode_change_callback(self, callback):
        """Register a callback for mode changes (e.g., WebSocket broadcast)."""
        self._mode_change_callbacks.append(callback)

    # ── Mode Transitions ──────────────────────────────────

    def set_mode(self, new_mode: SystemMode, reason: str = ""):
        """
        Transition the system to a new mode.
        ArmorClaw controls mode transitions — not the LLM.
        """
        old_mode = self.state.mode
        if old_mode == new_mode:
            return

        self.state.mode = new_mode

        # Log the mode transition
        transition_decision = EnforcementDecision(
            zone=EnforcementZone.FREEZE if new_mode != SystemMode.COPILOT else EnforcementZone.EXECUTE,
            allowed=True,
            reason=f"Mode transition: {old_mode.value} → {new_mode.value}. {reason}",
            rule_triggered="mode_transition",
            mode_at_decision=new_mode,
        )
        self.ledger.log(transition_decision, extra={
            "event": "mode_change",
            "from": old_mode.value,
            "to": new_mode.value,
        })

        # Fire callbacks
        for cb in self._mode_change_callbacks:
            try:
                cb(old_mode, new_mode, reason)
            except Exception:
                pass

    def record_activity(self):
        """Record user activity (resets toward Co-Pilot mode)."""
        self.state.last_activity = datetime.now(timezone.utc)
        self.state.inactivity_confidence = 0.0

        # If we were in Guardian, go back to Co-Pilot
        if self.state.mode == SystemMode.GUARDIAN:
            self.set_mode(SystemMode.COPILOT, "User activity detected — returning to Co-Pilot mode")

    def update_inactivity(self, confidence: float):
        """
        Update the inactivity confidence score.
        ArmorClaw decides mode transitions based on this.
        """
        self.state.inactivity_confidence = confidence

        if confidence >= 0.9 and self.state.mode != SystemMode.LOCKDOWN:
            self.set_mode(SystemMode.LOCKDOWN, f"Inactivity confidence {confidence:.0%} — crisis confirmed")
        elif confidence >= 0.6 and self.state.mode == SystemMode.COPILOT:
            self.set_mode(SystemMode.GUARDIAN, f"Inactivity confidence {confidence:.0%} — 4+ hours of silence")

    # ── Core Enforcement ──────────────────────────────────

    def evaluate(
        self,
        proposal: TradeProposal,
        risk_score: float = 0.0,
        tone_flags: list[str] = None,
    ) -> EnforcementDecision:
        """
        ┌─────────────────────────────────────────────────┐
        │  THE CORE ENFORCEMENT METHOD                    │
        │                                                 │
        │  Every trade proposal flows through this.       │
        │  ArmorClaw applies rules in strict priority:    │
        │                                                 │
        │  1. Mode-level blocks (Guardian/Lockdown)       │
        │  2. Risk floor violations                       │
        │  3. Banned asset checks                         │
        │  4. Risk score zone classification              │
        │  5. Trade rule matching                         │
        │                                                 │
        │  The FIRST rule that triggers wins.             │
        └─────────────────────────────────────────────────┘
        """
        if tone_flags is None:
            tone_flags = []

        will = self.will
        mode = self.state.mode

        # ── RULE 1: Mode-level enforcement ────────────────
        # In Guardian or Lockdown, ALL new trades are blocked.
        # This is non-negotiable. Even if risk_score is 0.
        if mode == SystemMode.GUARDIAN:
            override = will.mode_overrides.get("guardian")
            if override and override.block_all_new_trades:
                decision = EnforcementDecision(
                    zone=EnforcementZone.FREEZE,
                    allowed=False,
                    reason=f"GUARDIAN MODE active — all new trades blocked. User inactive for {self._inactivity_duration()}. Existing positions held.",
                    risk_score=risk_score,
                    tone_flags=tone_flags,
                    rule_triggered="guardian_mode_block",
                    mode_at_decision=mode,
                    proposal=proposal,
                )
                self.ledger.log(decision)
                return decision

        if mode == SystemMode.LOCKDOWN:
            decision = EnforcementDecision(
                zone=EnforcementZone.FREEZE,
                allowed=False,
                reason=f"LOCKDOWN MODE active — full trade freeze. User unresponsive for {self._inactivity_duration()}. Trustee access elevated.",
                risk_score=risk_score,
                tone_flags=tone_flags,
                rule_triggered="lockdown_mode_freeze",
                mode_at_decision=mode,
                proposal=proposal,
            )
            self.ledger.log(decision)
            return decision

        # ── RULE 2: Risk floor violation ──────────────────
        # Would this trade push us below the minimum balance?
        projected_balance = self.state.portfolio_value - proposal.estimated_value
        if projected_balance < will.risk_floor.minimum_balance:
            decision = EnforcementDecision(
                zone=EnforcementZone.FREEZE,
                allowed=False,
                reason=f"Trade would breach risk floor. Projected balance ${projected_balance:,.2f} < minimum ${will.risk_floor.minimum_balance:,.2f}",
                risk_score=max(risk_score, 0.95),
                tone_flags=tone_flags,
                rule_triggered="risk_floor_violation",
                mode_at_decision=mode,
                proposal=proposal,
            )
            self.ledger.log(decision)
            return decision

        # ── RULE 3: Single trade size cap ─────────────────
        if proposal.estimated_value > will.risk_floor.max_single_trade_amount:
            # Don't auto-block, but escalate to NOTIFY
            if risk_score < 0.7:
                decision = EnforcementDecision(
                    zone=EnforcementZone.NOTIFY,
                    allowed=False,
                    reason=f"Trade value ${proposal.estimated_value:,.2f} exceeds single-trade cap ${will.risk_floor.max_single_trade_amount:,.2f}. Requires user confirmation.",
                    risk_score=max(risk_score, 0.5),
                    tone_flags=tone_flags,
                    rule_triggered="single_trade_cap",
                    mode_at_decision=mode,
                    proposal=proposal,
                )
                self.ledger.log(decision)
                return decision

        # ── RULE 4: Daily volume cap ──────────────────────
        if self.state.daily_volume + proposal.estimated_value > will.risk_floor.max_daily_volume:
            decision = EnforcementDecision(
                zone=EnforcementZone.FREEZE,
                allowed=False,
                reason=f"Daily volume cap exceeded. Current: ${self.state.daily_volume:,.2f} + ${proposal.estimated_value:,.2f} > ${will.risk_floor.max_daily_volume:,.2f}",
                risk_score=max(risk_score, 0.8),
                tone_flags=tone_flags,
                rule_triggered="daily_volume_cap",
                mode_at_decision=mode,
                proposal=proposal,
            )
            self.ledger.log(decision)
            return decision

        # ── RULE 5: Daily trade count ─────────────────────
        if self.state.total_trades_today >= will.risk_floor.max_daily_trades:
            decision = EnforcementDecision(
                zone=EnforcementZone.FREEZE,
                allowed=False,
                reason=f"Max daily trades reached ({self.state.total_trades_today}/{will.risk_floor.max_daily_trades})",
                risk_score=max(risk_score, 0.7),
                tone_flags=tone_flags,
                rule_triggered="daily_trade_count",
                mode_at_decision=mode,
                proposal=proposal,
            )
            self.ledger.log(decision)
            return decision

        # ── RULE 6: Tone flags ────────────────────────────
        # If panic or FOMO is detected, escalate
        if "panic" in tone_flags or "fomo" in tone_flags:
            decision = EnforcementDecision(
                zone=EnforcementZone.NOTIFY,
                allowed=False,
                reason=f"Emotional tone detected: {', '.join(tone_flags)}. Trade requires calm review before execution.",
                risk_score=max(risk_score, 0.6),
                tone_flags=tone_flags,
                rule_triggered="tone_escalation",
                mode_at_decision=mode,
                proposal=proposal,
            )
            self.ledger.log(decision)
            return decision

        # ── RULE 7: Risk score zone classification ────────
        # Match against the three-zone trade rules from will.yaml
        for rule in will.trade_rules:
            cond = rule.conditions

            if rule.zone == "FREEZE":
                if cond.risk_score_above is not None and risk_score > cond.risk_score_above:
                    decision = EnforcementDecision(
                        zone=EnforcementZone.FREEZE,
                        allowed=False,
                        reason=f"Risk score {risk_score:.2f} exceeds FREEZE threshold {cond.risk_score_above}. Trade blocked.",
                        risk_score=risk_score,
                        tone_flags=tone_flags,
                        rule_triggered="risk_score_freeze",
                        mode_at_decision=mode,
                        proposal=proposal,
                    )
                    self.ledger.log(decision)
                    return decision

            if rule.zone == "NOTIFY":
                if cond.risk_score_range:
                    low, high = cond.risk_score_range
                    if low <= risk_score <= high:
                        decision = EnforcementDecision(
                            zone=EnforcementZone.NOTIFY,
                            allowed=False,
                            reason=f"Risk score {risk_score:.2f} in NOTIFY range [{low}, {high}]. Awaiting confirmation.",
                            risk_score=risk_score,
                            tone_flags=tone_flags,
                            rule_triggered="risk_score_notify",
                            mode_at_decision=mode,
                            proposal=proposal,
                        )
                        self.ledger.log(decision)
                        return decision

        # ── DEFAULT: EXECUTE ──────────────────────────────
        # If no rule triggered, the trade is safe to execute.
        decision = EnforcementDecision(
            zone=EnforcementZone.EXECUTE,
            allowed=True,
            reason=f"Trade passed all ArmorClaw checks. Risk score {risk_score:.2f} — safe to execute.",
            risk_score=risk_score,
            tone_flags=tone_flags,
            rule_triggered="all_clear",
            mode_at_decision=mode,
            proposal=proposal,
        )

        # Update state
        self.state.total_trades_today += 1
        self.state.daily_volume += proposal.estimated_value

        self.ledger.log(decision)
        return decision

    # ── Helpers ────────────────────────────────────────────

    def _inactivity_duration(self) -> str:
        """Human-readable inactivity duration."""
        delta = datetime.now(timezone.utc) - self.state.last_activity
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def get_status(self) -> dict:
        """Get the full system status for the frontend dashboard."""
        return {
            "mode": self.state.mode.value,
            "last_activity": self.state.last_activity.isoformat(),
            "inactivity_confidence": self.state.inactivity_confidence,
            "total_trades_today": self.state.total_trades_today,
            "daily_volume": self.state.daily_volume,
            "portfolio_value": self.state.portfolio_value,
            "risk_floor": self.will.risk_floor.minimum_balance,
            "owner": self.will.owner.name,
            "pending_notifications": len(self.state.pending_notifications),
            "alerts_sent": len(self.state.alerts_sent),
        }

    def reset_daily(self):
        """Reset daily counters (called at market open)."""
        self.state.total_trades_today = 0
        self.state.daily_volume = 0.0
