"""
LLM-Powered Risk Scorer
━━━━━━━━━━━━━━━━━━━━━━━
Scores each trade on 3 weighted signals:
  • Size Shock   (40%) — Is this trade much bigger than normal?
  • Suddenness   (30%) — Is this happening too fast?
  • Goal Align.  (30%) — Does this contradict the financial will?

Uses live LLM inference with deterministic fallback.
"""

import os
import json
import time
from typing import Optional
from datetime import datetime, timezone

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


# ─── Trade History for Baseline Calculations ──────────────────

class TradeHistory:
    """Rolling window of recent trades to compute baselines."""

    def __init__(self):
        self._trades: list[dict] = []

    def record(self, symbol: str, value: float, timestamp: datetime = None):
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        self._trades.append({
            "symbol": symbol,
            "value": value,
            "timestamp": timestamp.isoformat(),
            "ts": timestamp.timestamp(),
        })
        # Keep last 100 trades
        if len(self._trades) > 100:
            self._trades = self._trades[-100:]

    def average_trade_value(self) -> float:
        if not self._trades:
            return 5000.0  # Default baseline
        return sum(t["value"] for t in self._trades) / len(self._trades)

    def trades_in_last_n_minutes(self, minutes: int = 5) -> int:
        cutoff = time.time() - (minutes * 60)
        return sum(1 for t in self._trades if t["ts"] > cutoff)

    def max_trade_value(self) -> float:
        if not self._trades:
            return 10000.0
        return max(t["value"] for t in self._trades)


# ─── Risk Scorer ──────────────────────────────────────────────

class RiskScorer:
    """
    Scores trade risk using 3 weighted signals.
    Uses LLM inference when available, falls back to deterministic logic.
    """

    WEIGHT_SIZE_SHOCK = 0.40
    WEIGHT_SUDDENNESS = 0.30
    WEIGHT_GOAL_ALIGNMENT = 0.30

    def __init__(self):
        self.history = TradeHistory()
        self._llm_client = None
        self._llm_model = os.getenv("LLM_MODEL", "gemini-2.5-flash")

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/" if os.getenv("GEMINI_API_KEY") else None

        if HAS_OPENAI and api_key:
            try:
                self._llm_client = OpenAI(api_key=api_key, base_url=base_url)
            except Exception:
                self._llm_client = None

    def score(
        self,
        symbol: str,
        action: str,
        value: float,
        goals: list[dict] = None,
        risk_floor: dict = None,
    ) -> dict:
        """
        Compute the composite risk score for a proposed trade.

        Returns:
            {
                "total": 0.0-1.0,
                "size_shock": 0.0-1.0,
                "suddenness": 0.0-1.0,
                "goal_alignment": 0.0-1.0,
                "method": "llm" | "deterministic",
                "reasoning": "..."
            }
        """
        # Try LLM first, fall back to deterministic
        try:
            if self._llm_client:
                return self._score_with_llm(symbol, action, value, goals, risk_floor)
        except Exception as e:
            print(f"[RiskScorer] LLM inference failed, falling back to deterministic: {e}")

        return self._score_deterministic(symbol, action, value, goals, risk_floor)

    def _score_deterministic(
        self, symbol: str, action: str, value: float,
        goals: list[dict] = None, risk_floor: dict = None,
    ) -> dict:
        """Deterministic fallback scoring — always works, no API needed."""

        # ── Size Shock (40%) ──
        avg = self.history.average_trade_value()
        if avg > 0:
            ratio = value / avg
            if ratio <= 1.5:
                size_shock = 0.1
            elif ratio <= 3.0:
                size_shock = 0.3 + (ratio - 1.5) * 0.2
            elif ratio <= 5.0:
                size_shock = 0.6 + (ratio - 3.0) * 0.1
            else:
                size_shock = min(1.0, 0.8 + (ratio - 5.0) * 0.05)
        else:
            size_shock = 0.5  # Unknown baseline

        # ── Suddenness (30%) ──
        recent_count = self.history.trades_in_last_n_minutes(5)
        if recent_count <= 1:
            suddenness = 0.1
        elif recent_count <= 3:
            suddenness = 0.3
        elif recent_count <= 5:
            suddenness = 0.6
        else:
            suddenness = min(1.0, 0.7 + recent_count * 0.05)

        # ── Goal Alignment (30%) ──
        goal_alignment = 0.1  # Default: aligned
        if goals and risk_floor:
            min_balance = risk_floor.get("minimum_balance", 50000)
            max_single = risk_floor.get("max_single_trade_amount", 10000)

            if value > max_single:
                goal_alignment = max(goal_alignment, 0.5)
            if value > max_single * 2:
                goal_alignment = max(goal_alignment, 0.8)

            # Check if selling contradicts education/critical goals
            if action == "sell":
                critical_goals = [g for g in goals if g.get("priority") == "critical"]
                if critical_goals:
                    total_protected = sum(g.get("protected_amount", 0) for g in critical_goals)
                    if value > total_protected * 0.1:
                        goal_alignment = max(goal_alignment, 0.6)

        # ── Composite Score ──
        total = (
            self.WEIGHT_SIZE_SHOCK * size_shock
            + self.WEIGHT_SUDDENNESS * suddenness
            + self.WEIGHT_GOAL_ALIGNMENT * goal_alignment
        )

        reasoning = (
            f"Size Shock: {size_shock:.2f} (avg trade ${avg:,.0f}, this ${value:,.0f}). "
            f"Suddenness: {suddenness:.2f} ({self.history.trades_in_last_n_minutes(5)} trades in 5min). "
            f"Goal Alignment: {goal_alignment:.2f}."
        )

        return {
            "total": round(min(total, 1.0), 3),
            "size_shock": round(size_shock, 3),
            "suddenness": round(suddenness, 3),
            "goal_alignment": round(goal_alignment, 3),
            "method": "deterministic",
            "reasoning": reasoning,
        }

    def _score_with_llm(
        self, symbol: str, action: str, value: float,
        goals: list[dict] = None, risk_floor: dict = None,
    ) -> dict:
        """Score using LLM inference for nuanced reasoning."""

        avg_trade = self.history.average_trade_value()
        recent_count = self.history.trades_in_last_n_minutes(5)

        prompt = f"""You are a financial risk scoring system for WillGuard.
Score this proposed trade on 3 signals (each 0.0 to 1.0):

TRADE PROPOSAL:
- Symbol: {symbol}
- Action: {action}
- Value: ${value:,.2f}

CONTEXT:
- Average recent trade size: ${avg_trade:,.2f}
- Trades in last 5 minutes: {recent_count}
- User goals: {json.dumps(goals or [], indent=2)}
- Risk floor rules: {json.dumps(risk_floor or {{}}, indent=2)}

Score these 3 signals:
1. size_shock (0-1): How abnormal is this trade size vs the user's history?
2. suddenness (0-1): Is the trading frequency suspicious?
3. goal_alignment (0-1): Does this trade contradict the user's stated financial goals? (0=aligned, 1=contradicts)

Respond ONLY with valid JSON:
{{"size_shock": 0.0, "suddenness": 0.0, "goal_alignment": 0.0, "reasoning": "brief explanation"}}"""

        response = self._llm_client.chat.completions.create(
            model=self._llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
        )

        content = response.choices[0].message.content.strip()
        # Extract JSON from response
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content)

        size_shock = float(result.get("size_shock", 0.5))
        suddenness = float(result.get("suddenness", 0.5))
        goal_alignment = float(result.get("goal_alignment", 0.5))

        total = (
            self.WEIGHT_SIZE_SHOCK * size_shock
            + self.WEIGHT_SUDDENNESS * suddenness
            + self.WEIGHT_GOAL_ALIGNMENT * goal_alignment
        )

        return {
            "total": round(min(total, 1.0), 3),
            "size_shock": round(size_shock, 3),
            "suddenness": round(suddenness, 3),
            "goal_alignment": round(goal_alignment, 3),
            "method": "llm",
            "reasoning": result.get("reasoning", "LLM-scored"),
        }

    def record_trade(self, symbol: str, value: float):
        """Record a completed trade for future baseline calculations."""
        self.history.record(symbol, value)
