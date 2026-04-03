"""
ArmorClaw Policy Loader
━━━━━━━━━━━━━━━━━━━━━━
Loads and validates the user's YAML financial will.
Provides structured access to policy rules for the enforcer.
"""

import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional


class Goal(BaseModel):
    id: str
    type: str
    description: str
    priority: str
    protected_amount: float


class RiskFloor(BaseModel):
    minimum_balance: float
    max_single_trade_amount: float
    max_daily_trades: int
    max_daily_volume: float
    allowed_asset_classes: list[str]
    banned_asset_classes: list[str]


class TrustedContact(BaseModel):
    name: str
    phone: str
    email: str
    role: str
    access_level: str


class InactivityConfig(BaseModel):
    guardian_mode_seconds: int
    lockdown_mode_seconds: int
    grace_check_enabled: bool
    grace_check_channels: list[str]


class TradeRuleConditions(BaseModel):
    max_amount: Optional[float] = None
    risk_score_below: Optional[float] = None
    risk_score_range: Optional[list[float]] = None
    risk_score_above: Optional[float] = None
    allowed_in_modes: Optional[list[str]] = None
    applies_in_modes: Optional[list[str]] = None


class TradeRule(BaseModel):
    zone: str  # EXECUTE | NOTIFY | FREEZE
    conditions: TradeRuleConditions
    action: Optional[str] = None


class ModeOverride(BaseModel):
    block_all_new_trades: Optional[bool] = False
    hold_existing_positions: Optional[bool] = False
    alert_trusted_contacts: Optional[bool] = False
    full_trade_freeze: Optional[bool] = False
    elevate_trustee_access: Optional[bool] = False
    trustee_can_liquidate: Optional[bool] = False
    alert_message: Optional[str] = ""


class Owner(BaseModel):
    name: str
    account_id: str


class FinancialWill(BaseModel):
    """The complete structured intent model loaded from will.yaml"""
    owner: Owner
    goals: list[Goal]
    risk_floor: RiskFloor
    trusted_contacts: list[TrustedContact]
    inactivity: InactivityConfig
    trade_rules: list[TradeRule]
    mode_overrides: dict[str, ModeOverride]


_cached_will: Optional[FinancialWill] = None


def load_will(path: Optional[str] = None) -> FinancialWill:
    """
    Load and validate the financial will from YAML.
    Caches the result for performance.
    """
    global _cached_will
    if _cached_will is not None:
        return _cached_will

    if path is None:
        path = str(Path(__file__).parent.parent.parent / "data" / "policy" / "will.yaml")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    _cached_will = FinancialWill(**raw)
    return _cached_will


def reload_will(path: Optional[str] = None) -> FinancialWill:
    """Force reload the financial will (e.g., after edits)."""
    global _cached_will
    _cached_will = None
    return load_will(path)


def get_will() -> FinancialWill:
    """Get the cached will or load it."""
    return load_will()
