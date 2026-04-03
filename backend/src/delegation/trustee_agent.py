"""
Trustee Agent
━━━━━━━━━━━━━
Read-only agent for the trusted family contact.
In Lockdown Mode, the trustee gets elevated access to VIEW
the portfolio and decision ledger, but CANNOT execute trades.
"""

from datetime import datetime, timezone
from typing import Optional


class TrusteeAgent:
    """
    Provides a read-only view for the trusted family contact.

    Capabilities:
    - View portfolio status
    - View decision ledger
    - View ArmorClaw enforcement status
    - View alert history

    Cannot:
    - Execute trades
    - Modify policies
    - Change system mode
    """

    def __init__(self, enforcer, executor):
        self.enforcer = enforcer
        self.executor = executor
        self._access_granted = False
        self._access_granted_at: Optional[datetime] = None

    @property
    def has_access(self) -> bool:
        """Trustee only has access in Lockdown mode."""
        from ..armorclaw.enforcer import SystemMode
        return self.enforcer.state.mode == SystemMode.LOCKDOWN

    def get_dashboard(self) -> dict:
        """
        Get the trustee dashboard view.
        Only accessible in Lockdown mode.
        """
        if not self.has_access:
            return {
                "access": False,
                "message": "Trustee access is only available in Lockdown Mode. "
                           "The account holder is currently active.",
                "current_mode": self.enforcer.state.mode.value,
            }

        # Compile the read-only dashboard
        will = self.enforcer.will
        trustee_info = None
        for contact in will.trusted_contacts:
            if contact.role == "primary_trustee":
                trustee_info = {
                    "name": contact.name,
                    "role": contact.role,
                    "access_level": "read_only (elevated)",
                }
                break

        return {
            "access": True,
            "trustee": trustee_info,
            "account_holder": will.owner.name,
            "current_mode": "LOCKDOWN",
            "system_status": self.enforcer.get_status(),
            "portfolio": {
                "value": self.enforcer.state.portfolio_value,
                "positions": self.executor.get_positions(),
            },
            "recent_decisions": self.enforcer.ledger.get_entries(limit=20),
            "active_protections": {
                "trade_freeze": True,
                "positions_held": True,
                "risk_floor_enforced": True,
                "minimum_balance": will.risk_floor.minimum_balance,
            },
            "message": (
                f"⚠️ LOCKDOWN MODE ACTIVE\n\n"
                f"The account holder ({will.owner.name}) has been unresponsive. "
                f"All trades are frozen. Existing positions are being held. "
                f"The minimum balance of ${will.risk_floor.minimum_balance:,.2f} is protected.\n\n"
                f"You have READ-ONLY access to monitor the portfolio. "
                f"No trades can be executed until the account holder returns."
            ),
        }
