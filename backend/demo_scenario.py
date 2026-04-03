"""
WillGuard Demo Scenario
━━━━━━━━━━━━━━━━━━━━━━━
Runs the exact hackathon demo flow:

1. Normal trading (Co-Pilot Mode)
2. User goes inactive → Guardian Mode triggers
3. Risky trade attempted → ArmorClaw blocks it
4. Extended inactivity → Lockdown Mode
5. Trustee gets read-only access
6. User returns → Co-Pilot restored

Run with: python demo_scenario.py
"""

import asyncio
import time
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from src.openclaw.agent import OpenClawAgent
from src.alpaca.executor import AlpacaExecutor
from src.delegation.trustee_agent import TrusteeAgent


def print_header(text: str):
    print(f"\n{'═' * 60}")
    print(f"  {text}")
    print(f"{'═' * 60}\n")


def print_result(result: dict, indent: int = 2):
    spacing = " " * indent
    decision = result["decision"]
    risk = result["risk_score"]

    zone_colors = {"EXECUTE": "✅", "NOTIFY": "⚠️ ", "FREEZE": "🛑"}
    zone = decision["zone"]
    emoji = zone_colors.get(zone, "❓")

    print(f"{spacing}{emoji} Zone: {zone}")
    print(f"{spacing}   Allowed: {decision['allowed']}")
    print(f"{spacing}   Reason: {decision['reason']}")
    print(f"{spacing}   Rule: {decision['rule_triggered']}")
    print(f"{spacing}   Risk Score: {risk['total']:.3f} (method: {risk['method']})")
    print(f"{spacing}     Size Shock: {risk['size_shock']:.3f}")
    print(f"{spacing}     Suddenness: {risk['suddenness']:.3f}")
    print(f"{spacing}     Goal Align: {risk['goal_alignment']:.3f}")
    print(f"{spacing}   Mode: {result['system_mode']}")


async def run_demo():
    """Run the complete demo scenario."""

    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   ██╗    ██╗██╗██╗     ██╗      ██████╗ ██╗   ██╗██████╗ ║
    ║   ██║    ██║██║██║     ██║     ██╔════╝ ██║   ██║██╔══██╗║
    ║   ██║ █╗ ██║██║██║     ██║     ██║  ███╗██║   ██║██████╔╝║
    ║   ██║███╗██║██║██║     ██║     ██║   ██║██║   ██║██╔══██╗║
    ║   ╚███╔███╔╝██║███████╗███████╗╚██████╔╝╚██████╔╝██║  ██║║
    ║    ╚══╝╚══╝ ╚═╝╚══════╝╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝║
    ║                                                           ║
    ║   ArmorClaw Enforcement Demo                              ║
    ║   Team: BUG SMASHERS | Track: CLAW & SHIELD              ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    # Initialize
    agent = OpenClawAgent()
    executor = AlpacaExecutor()
    trustee = TrusteeAgent(agent.enforcer, executor)

    await agent.start()
    time.sleep(0.5)

    # ── SCENE 1: Normal Trading (Co-Pilot) ────────────────
    print_header("SCENE 1: CO-PILOT MODE — Normal Trading")
    print("  User is active. Small, safe trades execute automatically.\n")

    # Safe trade: Buy 10 AAPL at ~$175 = $1,750
    print("  → Submitting: Buy 10 AAPL ($1,750)")
    result = await agent.process_trade("AAPL", "buy", 10, 175.0)
    print_result(result)

    # Another safe trade
    print("\n  → Submitting: Buy 5 GOOGL ($850)")
    result = await agent.process_trade("GOOGL", "buy", 5, 170.0)
    print_result(result)

    time.sleep(1)

    # ── SCENE 2: Risky Trade in Co-Pilot ──────────────────
    print_header("SCENE 2: CO-PILOT MODE — Risky Trade Detected")
    print("  A large trade comes in that exceeds the single-trade cap.\n")

    # Risky trade: $15,000 (exceeds $10K cap)
    print("  → Submitting: Buy 100 TSLA ($25,000) — EXCEEDS CAP")
    result = await agent.process_trade("TSLA", "buy", 100, 250.0)
    print_result(result)

    time.sleep(1)

    # ── SCENE 3: Panic Tone Detection ─────────────────────
    print_header("SCENE 3: CO-PILOT MODE — Panic Trade Blocked")
    print("  User sends a panicked instruction. Tone classifier catches it.\n")

    print('  → Submitting: "SELL EVERYTHING NOW!!! Market is crashing!!!"')
    result = await agent.process_trade(
        "AAPL", "sell", 50, 170.0,
        message="SELL EVERYTHING NOW!!! Market is crashing!!!"
    )
    print_result(result)

    time.sleep(1)

    # ── SCENE 4: Inactivity → Guardian Mode ───────────────
    print_header("SCENE 4: GUARDIAN MODE — User Goes Inactive")
    print("  Simulating 4+ hours of user inactivity...")
    print("  ArmorClaw transitions to Guardian Mode.\n")

    agent.simulate_inactivity(15000)  # ~4.2 hours

    print(f"  System Mode: {agent.enforcer.state.mode.value.upper()}")
    print(f"  Inactivity Confidence: {agent.enforcer.state.inactivity_confidence:.0%}\n")

    # Try a trade in Guardian Mode
    print("  → Submitting: Buy 10 MSFT (in Guardian Mode)")
    result = await agent.process_trade("MSFT", "buy", 10, 400.0)
    print_result(result)

    time.sleep(1)

    # ── SCENE 5: Extended Inactivity → Lockdown ──────────
    print_header("SCENE 5: LOCKDOWN MODE — Crisis Confirmed")
    print("  Simulating 24+ hours of inactivity...")
    print("  ArmorClaw escalates to full Lockdown.\n")

    agent.simulate_inactivity(90000)  # ~25 hours total

    print(f"  System Mode: {agent.enforcer.state.mode.value.upper()}")
    print(f"  Inactivity Confidence: {agent.enforcer.state.inactivity_confidence:.0%}\n")

    # Trustee dashboard
    print("  → Trustee Dashboard:")
    dashboard = trustee.get_dashboard()
    print(f"     Access Granted: {dashboard['access']}")
    if dashboard["access"]:
        print(f"     Message: {dashboard['message'][:100]}...")
        print(f"     Portfolio Value: ${dashboard['portfolio']['value']:,.2f}")
        print(f"     Positions: {len(dashboard['portfolio']['positions'])}")
        print(f"     Recent Decisions: {len(dashboard['recent_decisions'])}")

    time.sleep(1)

    # ── SCENE 6: User Returns ─────────────────────────────
    print_header("SCENE 6: CO-PILOT RESTORED — User Returns")
    print("  User activity detected. System returns to normal.\n")

    agent.record_activity("trade_action")

    print(f"  System Mode: {agent.enforcer.state.mode.value.upper()}")
    print(f"  Inactivity Confidence: {agent.enforcer.state.inactivity_confidence:.0%}\n")

    # Safe trade works again
    print("  → Submitting: Buy 5 AAPL ($875)")
    result = await agent.process_trade("AAPL", "buy", 5, 175.0)
    print_result(result)

    # ── FINAL: Decision Ledger ────────────────────────────
    print_header("DECISION LEDGER — Full Audit Trail")
    entries = agent.enforcer.ledger.get_all_entries()
    print(f"  Total entries logged: {len(entries)}\n")
    for i, entry in enumerate(entries):
        zone = entry.get("zone", "?")
        emoji = {"EXECUTE": "✅", "NOTIFY": "⚠️ ", "FREEZE": "🛑"}.get(zone, "❓")
        proposal = entry.get("proposal", {})
        symbol = proposal.get("symbol", "-")
        action = proposal.get("action", "-")
        event = entry.get("extra", {}).get("event", "")

        if event:
            print(f"  {i+1}. {emoji} [{zone}] {event}: {entry.get('reason', '')[:70]}")
        else:
            print(f"  {i+1}. {emoji} [{zone}] {action.upper()} {symbol} — {entry.get('reason', '')[:60]}")

    await agent.stop()

    print(f"\n{'═' * 60}")
    print("  Demo Complete! ArmorClaw protected the family's assets.")
    print(f"{'═' * 60}\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
