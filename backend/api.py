"""
WillGuard API Server - FastAPI + SQLite + Twilio + WebSocket
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Full production-grade API with:
- SQLite database for persistent storage
- Twilio SMS for emergency notifications  
- WebSocket for real-time dashboard updates
- Reply-to-restore: emergency contacts SMS "SAFE" to unlock
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ.setdefault('PYTHONUTF8', '1')

from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    env_example = Path(__file__).parent / ".env.example"
    if env_example.exists():
        load_dotenv(env_example)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

from src.openclaw.agent import OpenClawAgent
from src.alpaca.executor import AlpacaExecutor
from src.delegation.trustee_agent import TrusteeAgent
from src.intelligence.inactivity_detector import ActivitySignal
from src.database import (
    init_db, create_user, authenticate_user, get_user_by_id, get_user_by_email,
    add_emergency_contact, get_emergency_contacts, get_contact_by_phone,
    get_will, update_will, add_trade, get_trades,
    add_ledger_entry, get_ledger,
    log_notification, get_notifications,
    get_system_state, update_system_state,
    update_position, get_portfolio,
)
from src.notifications.notifier import EmailNotifier


# ─── Global State ─────────────────────────────────────────

agent: Optional[OpenClawAgent] = None
executor: Optional[AlpacaExecutor] = None
trustee: Optional[TrusteeAgent] = None
notifier: Optional[EmailNotifier] = None
connected_websockets: list[WebSocket] = []


# ─── WebSocket Broadcast ─────────────────────────────────

async def broadcast_event(event: dict):
    dead = []
    for ws in connected_websockets:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_websockets.remove(ws)


def sync_broadcast(event: dict):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(broadcast_event(event))
        else:
            loop.run_until_complete(broadcast_event(event))
    except Exception:
        pass


# ─── App Lifecycle ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent, executor, trustee, notifier

    # Initialize SQLite database
    await init_db()

    # Initialize notification service
    notifier = EmailNotifier()

    # Initialize trading components
    executor = AlpacaExecutor()
    agent = OpenClawAgent()
    trustee = TrusteeAgent(agent.enforcer, executor)
    agent.subscribe(sync_broadcast)
    await agent.start()

    account = executor.get_account()
    if account.get("connected"):
        agent.enforcer.state.portfolio_value = account.get("portfolio_value", 100000.0)

    print("=" * 50)
    print("  WillGuard API Server Started")
    print(f"  Alpaca: {'Connected' if executor.is_connected else 'Mock Mode'}")
    print(f"  EmailJS: {'Configured' if notifier.is_configured else 'Simulation Mode'}")
    print(f"  Database: SQLite (willguard.db)")
    print(f"  Mode: {agent.enforcer.state.mode.value}")
    print("=" * 50)

    yield
    await agent.stop()


app = FastAPI(
    title="WillGuard API",
    description="AI-Driven Financial Safety System with SQLite + Twilio",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Models ──────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    full_name: str
    password: str
    phone: Optional[str] = None
    emergency_contacts: Optional[list[dict]] = []
    will: Optional[dict] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TradeRequest(BaseModel):
    symbol: str
    action: str
    quantity: float
    price: Optional[float] = None
    message: Optional[str] = None
    user_id: Optional[int] = None


class UpdateWillRequest(BaseModel):
    riskTolerance: str = "Moderate"
    dailyTradeLimit: float = 50000
    perOrderLimit: float = 10000
    approvedTickers: list[str] = []


class SimulateInactivityRequest(BaseModel):
    seconds: int = 14400
    user_id: Optional[int] = None


# ─── Auth Endpoints ──────────────────────────────────────

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    """Register a new user with emergency contacts and financial will."""
    existing = await get_user_by_email(req.email)
    if existing:
        raise HTTPException(400, "Email already registered")

    user = await create_user(req.email, req.full_name, req.password, req.phone)
    user_id = user["id"]

    # Add emergency contacts
    contacts = []
    for ec in (req.emergency_contacts or []):
        if ec.get("name") and ec.get("email") and ec.get("phone"):
            cid = await add_emergency_contact(
                user_id, ec["name"], ec["email"], ec["phone"],
                ec.get("role", "emergency_contact")
            )
            contacts.append({**ec, "id": cid})

    # Set up financial will
    if req.will:
        await update_will(
            user_id,
            req.will.get("riskTolerance", "Moderate"),
            req.will.get("dailyTradeLimit", 50000),
            req.will.get("perOrderLimit", 10000),
            req.will.get("approvedTickers", ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "SPY", "QQQ", "NVDA"]),
        )

    will_data = await get_will(user_id)

    # Log to ledger
    await add_ledger_entry(user_id, "SYSTEM", "User Registered", None, "copilot",
                           f"New user registered: {req.full_name}")

    return {
        "user": user,
        "emergencyContacts": contacts,
        "will": will_data,
    }


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    """Authenticate user and return profile."""
    user = await authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(401, "Invalid email or password")

    contacts = await get_emergency_contacts(user["id"])
    will_data = await get_will(user["id"])
    state = await get_system_state(user["id"])
    portfolio = await get_portfolio(user["id"])

    return {
        "user": user,
        "emergencyContacts": contacts,
        "will": will_data,
        "systemState": state,
        "portfolio": portfolio,
    }


# ─── System Status ───────────────────────────────────────

@app.get("/api/status")
async def get_status(user_id: Optional[int] = None):
    """Get full system status."""
    status = agent.get_full_status()
    status["alpaca"] = executor.get_account()
    status["notifications"] = notifier.get_status()
    if user_id:
        status["db_state"] = await get_system_state(user_id)
        status["portfolio"] = await get_portfolio(user_id)
    return status


@app.get("/api/portfolio/{user_id}")
async def get_user_portfolio(user_id: int):
    """Get user's portfolio from database."""
    portfolio = await get_portfolio(user_id)
    return portfolio


# ─── Trade Execution ─────────────────────────────────────

@app.post("/api/trade")
async def submit_trade(req: TradeRequest):
    """
    Full trade pipeline:
    1. AI Risk scoring (Gemini)
    2. ArmorClaw enforcement
    3. Portfolio update in SQLite (if allowed)
    4. Notification broadcast
    """
    price = req.price
    if not price:
        quote = executor.get_quote(req.symbol.upper())
        price = quote.get("ask_price", 150.0) if req.action == "buy" else quote.get("bid_price", 150.0)

    # Run through the agent pipeline (AI risk scoring + ArmorClaw)
    result = await agent.process_trade(
        symbol=req.symbol.upper(),
        action=req.action.lower(),
        quantity=req.quantity,
        price=price,
        message=req.message,
        source="user",
    )

    user_id = req.user_id
    zone = result["decision"]["zone"]
    allowed = result["decision"]["allowed"]
    risk_score = result.get("risk_score", {}).get("total", 0)
    risk_method = result.get("risk_score", {}).get("method", "heuristic")
    estimated_value = req.quantity * price

    # Save trade to database
    if user_id:
        await add_trade(
            user_id, req.symbol.upper(), req.action, req.quantity, price,
            estimated_value, zone, allowed,
            result["decision"]["reason"], risk_score, risk_method,
            result.get("system_mode", "copilot")
        )

        # Update portfolio if trade was allowed (EXECUTE zone)
        if allowed:
            portfolio = await update_position(user_id, req.symbol.upper(), req.quantity, price, req.action)
            result["portfolio"] = portfolio

            # Also execute on Alpaca if connected
            order = executor.submit_order(
                symbol=req.symbol.upper(),
                quantity=req.quantity,
                side=req.action.lower(),
            )
            result["execution"] = order
        else:
            result["execution"] = {"blocked": True, "reason": result["decision"]["reason"]}
            # Still return current portfolio
            result["portfolio"] = await get_portfolio(user_id)

        # Log to decision ledger in DB
        await add_ledger_entry(
            user_id, zone,
            f"{req.action.upper()} {req.quantity} {req.symbol.upper()} @${price:.2f}",
            risk_score, result.get("system_mode", "copilot"),
            result["decision"]["reason"],
            result["decision"].get("rule_triggered", ""),
        )
    else:
        if allowed:
            order = executor.submit_order(
                symbol=req.symbol.upper(),
                quantity=req.quantity,
                side=req.action.lower(),
            )
            result["execution"] = order
        else:
            result["execution"] = {"blocked": True, "reason": result["decision"]["reason"]}

    # Broadcast via WebSocket
    await broadcast_event({
        "type": "trade_result",
        "data": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return result


# ─── Financial Will ──────────────────────────────────────

@app.get("/api/will/{user_id}")
async def get_user_will(user_id: int):
    """Get user's financial will."""
    will_data = await get_will(user_id)
    if not will_data:
        raise HTTPException(404, "Will not found")
    return will_data


@app.put("/api/will/{user_id}")
async def update_user_will(user_id: int, req: UpdateWillRequest):
    """Update user's financial will."""
    result = await update_will(
        user_id, req.riskTolerance, req.dailyTradeLimit,
        req.perOrderLimit, req.approvedTickers,
    )
    await add_ledger_entry(user_id, "SYSTEM", "Financial Will Updated", None, "copilot",
                           f"Will updated: tolerance={req.riskTolerance}, limit=${req.dailyTradeLimit}")
    return result


# ─── Emergency Contacts ─────────────────────────────────

@app.get("/api/contacts/{user_id}")
async def get_contacts(user_id: int):
    """Get user's emergency contacts."""
    return await get_emergency_contacts(user_id)


# ─── Decision Ledger ─────────────────────────────────────

@app.get("/api/ledger")
async def get_ledger_entries(user_id: Optional[int] = None, limit: int = 50):
    """Get decision ledger from database."""
    entries = await get_ledger(user_id, limit)
    return {"entries": entries, "total": len(entries)}


# ─── Notifications ───────────────────────────────────────

@app.post("/api/notifications/test/{user_id}/{contact_id}")
async def send_test_notification(user_id: int, contact_id: int):
    """Send a test SMS to an emergency contact."""
    user = await get_user_by_id(user_id)
    contacts = await get_emergency_contacts(user_id)
    contact = next((c for c in contacts if c["id"] == contact_id), None)
    if not contact:
        raise HTTPException(404, "Contact not found")

    result = notifier.send_test_alert(contact["email"], contact["name"], user["full_name"])

    await log_notification(
        user_id, contact_id,
        result.get("channel", "simulated"),
        result.get("body", ""),
        result.get("sid"),
        "outbound",
        result.get("status", "sent"),
    )

    return {"message": "Test alert sent", "result": result}


@app.post("/api/notifications/guardian/{user_id}")
async def send_guardian_notifications(user_id: int):
    """Send Guardian mode alerts to all emergency contacts."""
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    contacts = await get_emergency_contacts(user_id)
    results = []

    for contact in contacts:
        magic_link = f"http://localhost:5173/?restore=true&user={user_id}&contact={contact['id']}"
        result = notifier.send_guardian_alert(contact["email"], contact["name"], user["full_name"], magic_link)
        await log_notification(
            user_id, contact["id"],
            result.get("channel", "simulated"),
            result.get("body", ""),
            result.get("sid"),
            "outbound",
            result.get("status", "sent"),
        )
        results.append(result)

    return {"message": f"Guardian alerts sent to {len(contacts)} contacts", "results": results}


@app.post("/api/notifications/lockdown/{user_id}")
async def send_lockdown_notifications(user_id: int):
    """Send Lockdown mode alerts to all emergency contacts."""
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    contacts = await get_emergency_contacts(user_id)
    results = []

    for contact in contacts:
        magic_link = f"http://localhost:8000/api/notifications/magic_restore/{user_id}?contact_id={contact['id']}"
        result = notifier.send_lockdown_alert(contact["email"], contact["name"], user["full_name"], magic_link=magic_link)
        await log_notification(
            user_id, contact["id"],
            result.get("channel", "simulated"),
            result.get("body", ""),
            result.get("sid"),
            "outbound",
            result.get("status", "sent"),
        )
        results.append(result)

    return {"message": f"Lockdown alerts sent to {len(contacts)} contacts", "results": results}


@app.get("/api/notifications/{user_id}")
async def get_notification_history(user_id: int):
    """Get notification history from database."""
    return await get_notifications(user_id)


@app.get("/api/notifications/status")
async def get_notification_status():
    """Get Email notification system status."""
    return notifier.get_status()


# ─── Magic Link Restore ──────────────────────────────

@app.get("/api/notifications/magic_restore/{user_id}")
async def magic_link_restore(user_id: int, contact_id: Optional[int] = None):
    """
    Magic Link logic for EmailJS.
    
    When an emergency contact clicks the link in their email,
    this transitions the system back to Co-Pilot mode.
    """
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    contact_name = "Unknown Contact"
    if contact_id:
        contacts = await get_emergency_contacts(user_id)
        contact = next((c for c in contacts if c["id"] == contact_id), None)
        if contact:
            contact_name = contact["name"]

            # Log the incoming restore
            await log_notification(
                user_id, contact["id"], "email_link", "Clicked Magic Link",
                direction="inbound", status="received",
            )

    # Transition back to Co-Pilot mode
    agent.record_activity("manual_override")

    await update_system_state(user_id, mode="copilot", inactivity_confidence=0)
    await add_ledger_entry(
        user_id, "MODE_CHANGE", "→ COPILOT", None, "copilot",
        f"Emergency contact {contact_name} confirmed safety via MAGIC LINK",
        "email_magic_link",
    )

    # Broadcast mode change to dashboard
    await broadcast_event({
        "type": "mode_change",
        "data": {
            "mode": "copilot",
            "reason": f"Emergency contact {contact_name} confirmed safety via Magic Link",
            "restored_by": contact_name,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    html_content = f"""
    <html>
        <head>
            <title>WillGuard Restored</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b1121; color: white; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                .container {{ text-align: center; border-radius: 12px; background: rgba(255, 255, 255, 0.05); padding: 40px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1); border: 1px solid rgba(255, 255, 255, 0.1); }}
                h1 {{ color: #10b981; }}
                p {{ color: #94a3b8; font-size: 1.1rem; }}
                .icon {{ font-size: 64px; margin-bottom: 16px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">✅</div>
                <h1>System Restored</h1>
                <p>Thank you, {contact_name}.</p>
                <p>{user['full_name']}'s WillGuard system has been successfully restored to <b>Co-Pilot</b> mode.</p>
                <p style="font-size: 0.9rem; margin-top: 32px">You may now close this window.</p>
            </div>
        </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")


# ─── Demo Controls ────────────────────────────────────────

@app.post("/api/simulate/inactivity")
async def simulate_inactivity(req: SimulateInactivityRequest):
    """Simulate user inactivity for demo."""
    agent.simulate_inactivity(req.seconds)
    status = agent.get_full_status()

    # Send notifications if mode changed
    mode = status["enforcer"]["mode"]
    if req.user_id:
        await update_system_state(req.user_id, mode=mode)
        if mode == "guardian":
            await send_guardian_notifications(req.user_id)
        elif mode == "lockdown":
            await send_lockdown_notifications(req.user_id)

    await broadcast_event({
        "type": "inactivity_simulated",
        "data": {
            "seconds": req.seconds,
            "new_mode": mode,
            "confidence": status["heartbeat"]["inactivity"]["confidence"],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {"message": f"Simulated {req.seconds}s of inactivity", "status": status}


@app.post("/api/simulate/activity")
async def simulate_activity(user_id: Optional[int] = None):
    """Simulate user returning."""
    agent.record_activity("trade_action")
    status = agent.get_full_status()

    if user_id:
        await update_system_state(user_id, mode="copilot", inactivity_confidence=0)

    await broadcast_event({
        "type": "activity_detected",
        "data": {"new_mode": status["enforcer"]["mode"]},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {"message": "User activity recorded", "status": status}


@app.post("/api/reset")
async def reset_system(user_id: Optional[int] = None):
    """Reset system to initial state."""
    agent.reset()

    if user_id:
        await update_system_state(
            user_id, mode="copilot", inactivity_confidence=0,
            portfolio_value=100000, cash_balance=100000,
            daily_volume=0, total_trades_today=0,
        )

    await broadcast_event({
        "type": "system_reset",
        "data": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {"message": "System reset to initial state", "status": agent.get_full_status()}


# ─── System Info ──────────────────────────────────────────

@app.get("/api/system/info")
async def get_system_info():
    import platform
    return {
        "status": "online",
        "engine": "Python FastAPI",
        "version": sys.version.split()[0],
        "os": platform.system(),
        "arch": platform.machine(),
        "pid": os.getpid(),
        "sqlite_path": str(Path(__file__).parent / "data" / "willguard.db"),
        "alpaca": "Connected" if executor.is_connected else "Mock Mode",
        "emailjs": "Configured" if notifier.is_configured else "Simulation Mode",
        "uptime": datetime.now(timezone.utc).isoformat(),
    }


# ─── Quote ────────────────────────────────────────────────

@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    return executor.get_quote(symbol.upper())


# ─── WebSocket ────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_websockets.append(ws)

    try:
        await ws.send_json({
            "type": "connected",
            "data": agent.get_full_status(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        while True:
            data = await ws.receive_text()
            if data == "ping":
                agent.record_activity("dashboard_view")
                await ws.send_json({
                    "type": "pong",
                    "data": agent.get_full_status(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
    except WebSocketDisconnect:
        if ws in connected_websockets:
            connected_websockets.remove(ws)
    except Exception:
        if ws in connected_websockets:
            connected_websockets.remove(ws)


# ─── Run ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
