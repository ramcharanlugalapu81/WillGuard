"""
WillGuard API Server - FastAPI + WebSocket
REST endpoints for the React dashboard
WebSocket for real-time updates
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ.setdefault('PYTHONUTF8', '1')

from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    env_example = Path(__file__).parent / ".env.example"
    if env_example.exists():
        load_dotenv(env_example)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.openclaw.agent import OpenClawAgent
from src.alpaca.executor import AlpacaExecutor
from src.delegation.trustee_agent import TrusteeAgent
from src.intelligence.inactivity_detector import ActivitySignal


# ─── Global State ─────────────────────────────────────────────

agent: Optional[OpenClawAgent] = None
executor: Optional[AlpacaExecutor] = None
trustee: Optional[TrusteeAgent] = None
connected_websockets: list[WebSocket] = []


# ─── WebSocket Broadcast ─────────────────────────────────────

async def broadcast_event(event: dict):
    """Broadcast an event to all connected WebSocket clients."""
    dead = []
    for ws in connected_websockets:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_websockets.remove(ws)


def sync_broadcast(event: dict):
    """Sync wrapper for broadcasting (called from agent callbacks)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(broadcast_event(event))
        else:
            loop.run_until_complete(broadcast_event(event))
    except Exception:
        pass


# ─── App Lifecycle ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the agent and executor on startup."""
    global agent, executor, trustee

    executor = AlpacaExecutor()
    agent = OpenClawAgent()
    trustee = TrusteeAgent(agent.enforcer, executor)

    # Subscribe to agent events for WebSocket broadcast
    agent.subscribe(sync_broadcast)

    # Start the heartbeat loop
    await agent.start()

    # Update portfolio value from Alpaca if connected
    account = executor.get_account()
    if account.get("connected"):
        agent.enforcer.state.portfolio_value = account.get("portfolio_value", 100000.0)

    print("=======================================")
    print("  WillGuard API Server Started")
    print(f"  Alpaca: {'Connected' if executor.is_connected else 'Mock Mode'}")
    print(f"  Mode: {agent.enforcer.state.mode.value}")
    print("=======================================")

    yield

    await agent.stop()


app = FastAPI(
    title="WillGuard API",
    description="AI-Driven Financial Safety System - ArmorClaw Enforcement Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Models ──────────────────────────────────────────

class TradeRequest(BaseModel):
    symbol: str
    action: str  # buy | sell
    quantity: float
    price: Optional[float] = None
    message: Optional[str] = None


class SimulateInactivityRequest(BaseModel):
    seconds: int = 14400  # Default: 4 hours


# ─── REST Endpoints ──────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """Get the full system status (mode, portfolio, heartbeat, etc.)."""
    status = agent.get_full_status()
    status["alpaca"] = executor.get_account()
    return status


@app.get("/api/portfolio")
async def get_portfolio():
    """Get current portfolio from Alpaca."""
    return {
        "account": executor.get_account(),
        "positions": executor.get_positions(),
        "orders": executor.get_orders(),
    }


@app.get("/api/ledger")
async def get_ledger(limit: int = 50):
    """Get the decision ledger entries."""
    return {
        "entries": agent.enforcer.ledger.get_entries(limit=limit),
        "total": len(agent.enforcer.ledger.get_all_entries()),
    }


@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    """Get latest quote for a symbol."""
    return executor.get_quote(symbol.upper())


@app.get("/api/will")
async def get_will():
    """Get the configured financial will."""
    from src.armorclaw.policy_loader import get_will as load_will
    will = load_will()
    return will.model_dump()


@app.get("/api/trustee")
async def get_trustee_dashboard():
    """Get the trustee's read-only dashboard."""
    return trustee.get_dashboard()


# ─── Trade Execution ─────────────────────────────────────────

@app.post("/api/trade")
async def submit_trade(req: TradeRequest):
    """
    Submit a trade through the full WillGuard pipeline:
    1. Risk scoring
    2. Tone classification
    3. ArmorClaw enforcement
    4. Execute (if allowed) via Alpaca
    """
    # Get quote for price
    price = req.price
    if not price:
        quote = executor.get_quote(req.symbol.upper())
        price = quote.get("ask_price", 150.0) if req.action == "buy" else quote.get("bid_price", 150.0)

    # Run through the agent pipeline
    result = await agent.process_trade(
        symbol=req.symbol.upper(),
        action=req.action.lower(),
        quantity=req.quantity,
        price=price,
        message=req.message,
        source="user",
    )

    # If ArmorClaw allows, execute on Alpaca
    if result["decision"]["allowed"]:
        order = executor.submit_order(
            symbol=req.symbol.upper(),
            quantity=req.quantity,
            side=req.action.lower(),
        )
        result["execution"] = order
    else:
        result["execution"] = {"blocked": True, "reason": result["decision"]["reason"]}

    # Broadcast update
    await broadcast_event({
        "type": "trade_result",
        "data": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return result


# ─── Demo Controls ────────────────────────────────────────────

@app.post("/api/simulate/inactivity")
async def simulate_inactivity(req: SimulateInactivityRequest):
    """
    Simulate user inactivity for N seconds.
    Used for demo: triggers Guardian/Lockdown mode transitions.
    """
    agent.simulate_inactivity(req.seconds)
    status = agent.get_full_status()

    await broadcast_event({
        "type": "inactivity_simulated",
        "data": {
            "seconds": req.seconds,
            "new_mode": status["enforcer"]["mode"],
            "confidence": status["heartbeat"]["inactivity"]["confidence"],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "message": f"Simulated {req.seconds}s of inactivity",
        "status": status,
    }


@app.post("/api/simulate/activity")
async def simulate_activity():
    """Simulate user returning (activity detected)."""
    agent.record_activity("trade_action")
    status = agent.get_full_status()

    await broadcast_event({
        "type": "activity_detected",
        "data": {"new_mode": status["enforcer"]["mode"]},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "message": "User activity recorded - system returning to Co-Pilot mode",
        "status": status,
    }


@app.post("/api/reset")
async def reset_system():
    """Reset the system to initial state (for demo reruns)."""
    agent.reset()

    await broadcast_event({
        "type": "system_reset",
        "data": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {"message": "System reset to initial state", "status": agent.get_full_status()}


# ─── WebSocket ────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket for real-time dashboard updates."""
    await ws.accept()
    connected_websockets.append(ws)

    try:
        # Send initial status
        await ws.send_json({
            "type": "connected",
            "data": agent.get_full_status(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep connection alive and listen for pings
        while True:
            data = await ws.receive_text()

            # Handle ping
            if data == "ping":
                # Record dashboard view as activity
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


# ─── Run ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
