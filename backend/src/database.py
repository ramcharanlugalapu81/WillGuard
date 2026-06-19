"""
WillGuard Database Layer
━━━━━━━━━━━━━━━━━━━━━━━━
SQLite-backed persistent storage for all system data.
Replaces in-memory state and localStorage with a real database.
"""

import aiosqlite
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DB_PATH = str(Path(__file__).parent.parent / "data" / "willguard.db")


def hash_password(password: str) -> str:
    """Hash a password with SHA-256 + salt."""
    salt = "willguard_salt_2024"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Create all tables if they don't exist."""
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS emergency_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                role TEXT DEFAULT 'emergency_contact',
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS financial_wills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                risk_tolerance TEXT DEFAULT 'Moderate',
                daily_trade_limit REAL DEFAULT 50000,
                per_order_limit REAL DEFAULT 10000,
                approved_tickers TEXT DEFAULT 'AAPL,MSFT,GOOGL,AMZN,TSLA,SPY,QQQ,NVDA',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL,
                estimated_value REAL,
                zone TEXT NOT NULL,
                allowed INTEGER NOT NULL,
                reason TEXT,
                risk_score REAL,
                risk_method TEXT,
                system_mode TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS ledger_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                zone TEXT NOT NULL,
                action TEXT NOT NULL,
                risk_score REAL,
                mode TEXT NOT NULL,
                reason TEXT,
                rule_triggered TEXT,
                extra_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                contact_id INTEGER,
                channel TEXT NOT NULL,
                message_body TEXT NOT NULL,
                twilio_sid TEXT,
                direction TEXT DEFAULT 'outbound',
                status TEXT DEFAULT 'sent',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (contact_id) REFERENCES emergency_contacts(id)
            );

            CREATE TABLE IF NOT EXISTS system_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                mode TEXT DEFAULT 'copilot',
                inactivity_confidence REAL DEFAULT 0,
                portfolio_value REAL DEFAULT 100000,
                cash_balance REAL DEFAULT 100000,
                daily_volume REAL DEFAULT 0,
                total_trades_today INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL,
                avg_price REAL NOT NULL,
                current_value REAL DEFAULT 0,
                pnl REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, symbol)
            );
        """)
        await db.commit()
        print("[DB] ✅ SQLite database initialized successfully")
    finally:
        await db.close()


# ─── User Operations ─────────────────────────────────────

async def create_user(email: str, full_name: str, password: str, phone: str = None) -> dict:
    """Register a new user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO users (email, full_name, password_hash, phone) VALUES (?, ?, ?, ?)",
            (email, full_name, hash_password(password), phone)
        )
        user_id = cursor.lastrowid

        # Create default financial will
        await db.execute(
            "INSERT INTO financial_wills (user_id) VALUES (?)", (user_id,)
        )

        # Create default system state
        await db.execute(
            "INSERT INTO system_states (user_id) VALUES (?)", (user_id,)
        )

        await db.commit()
        return {"id": user_id, "email": email, "full_name": full_name, "phone": phone}
    finally:
        await db.close()


async def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate and return user or None."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, email, full_name, phone FROM users WHERE email = ? AND password_hash = ?",
            (email, hash_password(password))
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        await db.close()


async def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, email, full_name, phone FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, email, full_name, phone FROM users WHERE email = ?", (email,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ─── Emergency Contacts ──────────────────────────────────

async def add_emergency_contact(user_id: int, name: str, email: str, phone: str, role: str = "emergency_contact") -> int:
    """Add an emergency contact for a user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO emergency_contacts (user_id, name, email, phone, role) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, email, phone, role)
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_emergency_contacts(user_id: int) -> list[dict]:
    """Get all emergency contacts for a user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, name, email, phone, role FROM emergency_contacts WHERE user_id = ?",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_contact_by_phone(phone: str) -> Optional[dict]:
    """Find an emergency contact by phone number (for Twilio webhook)."""
    db = await get_db()
    try:
        # Normalize phone: try exact match and with/without country code
        cursor = await db.execute(
            "SELECT ec.id, ec.user_id, ec.name, ec.email, ec.phone, ec.role "
            "FROM emergency_contacts ec WHERE ec.phone = ? OR ec.phone LIKE ?",
            (phone, f"%{phone[-10:]}")
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ─── Financial Will ───────────────────────────────────────

async def get_will(user_id: int) -> Optional[dict]:
    """Get financial will for a user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM financial_wills WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            d = dict(row)
            d["approvedTickers"] = d.pop("approved_tickers", "").split(",")
            d["riskTolerance"] = d.pop("risk_tolerance", "Moderate")
            d["dailyTradeLimit"] = d.pop("daily_trade_limit", 50000)
            d["perOrderLimit"] = d.pop("per_order_limit", 10000)
            return d
        return None
    finally:
        await db.close()


async def update_will(user_id: int, risk_tolerance: str, daily_trade_limit: float,
                      per_order_limit: float, approved_tickers: list[str]) -> dict:
    """Update the financial will."""
    db = await get_db()
    try:
        tickers_str = ",".join(approved_tickers)
        await db.execute(
            "UPDATE financial_wills SET risk_tolerance=?, daily_trade_limit=?, "
            "per_order_limit=?, approved_tickers=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (risk_tolerance, daily_trade_limit, per_order_limit, tickers_str, user_id)
        )
        await db.commit()
        return await get_will(user_id)
    finally:
        await db.close()


# ─── Trades ───────────────────────────────────────────────

async def add_trade(user_id: int, symbol: str, action: str, quantity: float,
                    price: float, estimated_value: float, zone: str, allowed: bool,
                    reason: str, risk_score: float, risk_method: str, system_mode: str) -> int:
    """Record a trade in the database."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO trades (user_id, symbol, action, quantity, price, estimated_value, "
            "zone, allowed, reason, risk_score, risk_method, system_mode) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, symbol, action, quantity, price, estimated_value,
             zone, int(allowed), reason, risk_score, risk_method, system_mode)
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_trades(user_id: int, limit: int = 50) -> list[dict]:
    """Get recent trades for a user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM trades WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ─── Ledger ───────────────────────────────────────────────

async def add_ledger_entry(user_id: int, zone: str, action: str, risk_score: float,
                           mode: str, reason: str, rule_triggered: str = "", extra_data: dict = None) -> int:
    """Add an entry to the decision ledger."""
    db = await get_db()
    try:
        extra = json.dumps(extra_data) if extra_data else None
        cursor = await db.execute(
            "INSERT INTO ledger_entries (user_id, zone, action, risk_score, mode, reason, rule_triggered, extra_data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, zone, action, risk_score, mode, reason, rule_triggered, extra)
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_ledger(user_id: int = None, limit: int = 50) -> list[dict]:
    """Get recent ledger entries."""
    db = await get_db()
    try:
        if user_id:
            cursor = await db.execute(
                "SELECT * FROM ledger_entries WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM ledger_entries ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ─── Notifications ────────────────────────────────────────

async def log_notification(user_id: int, contact_id: int, channel: str,
                           message_body: str, twilio_sid: str = None,
                           direction: str = "outbound", status: str = "sent") -> int:
    """Log a notification (SMS, email, or simulated)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO notifications (user_id, contact_id, channel, message_body, twilio_sid, direction, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, contact_id, channel, message_body, twilio_sid, direction, status)
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_notifications(user_id: int, limit: int = 20) -> list[dict]:
    """Get notification history for a user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT n.*, ec.name as contact_name FROM notifications n "
            "LEFT JOIN emergency_contacts ec ON n.contact_id = ec.id "
            "WHERE n.user_id = ? ORDER BY n.created_at DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ─── System State ─────────────────────────────────────────

async def get_system_state(user_id: int) -> Optional[dict]:
    """Get the current system state for a user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM system_states WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_system_state(user_id: int, **kwargs) -> dict:
    """Update system state fields."""
    db = await get_db()
    try:
        valid_fields = {"mode", "inactivity_confidence", "portfolio_value",
                        "cash_balance", "daily_volume", "total_trades_today"}
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        if not updates:
            return await get_system_state(user_id)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        await db.execute(
            f"UPDATE system_states SET {set_clause}, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            values
        )
        await db.commit()
        return await get_system_state(user_id)
    finally:
        await db.close()


# ─── Positions ────────────────────────────────────────────

async def update_position(user_id: int, symbol: str, quantity_change: float,
                          price: float, side: str) -> dict:
    """Update or create a position after a trade."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM positions WHERE user_id = ? AND symbol = ?",
            (user_id, symbol)
        )
        existing = await cursor.fetchone()

        if existing:
            existing = dict(existing)
            if side == "buy":
                new_qty = existing["quantity"] + quantity_change
                # Weighted average price
                total_cost = (existing["quantity"] * existing["avg_price"]) + (quantity_change * price)
                new_avg = total_cost / new_qty if new_qty > 0 else price
            else:
                new_qty = existing["quantity"] - quantity_change
                new_avg = existing["avg_price"]

            if new_qty <= 0:
                await db.execute(
                    "DELETE FROM positions WHERE user_id = ? AND symbol = ?",
                    (user_id, symbol)
                )
            else:
                pnl = (price - new_avg) * new_qty
                await db.execute(
                    "UPDATE positions SET quantity=?, avg_price=?, current_value=?, pnl=?, updated_at=CURRENT_TIMESTAMP "
                    "WHERE user_id=? AND symbol=?",
                    (new_qty, new_avg, new_qty * price, pnl, user_id, symbol)
                )
        elif side == "buy":
            await db.execute(
                "INSERT INTO positions (user_id, symbol, quantity, avg_price, current_value, pnl) "
                "VALUES (?, ?, ?, ?, ?, 0)",
                (user_id, symbol, quantity_change, price, quantity_change * price)
            )

        await db.commit()

        # Return updated state
        state = await get_system_state(user_id)
        if state:
            order_value = quantity_change * price
            if side == "buy":
                new_cash = state["cash_balance"] - order_value
            else:
                new_cash = state["cash_balance"] + order_value

            # Calculate total portfolio value
            pos_cursor = await db.execute(
                "SELECT SUM(current_value) as total FROM positions WHERE user_id = ?",
                (user_id,)
            )
            pos_row = await pos_cursor.fetchone()
            positions_value = dict(pos_row)["total"] or 0
            new_portfolio = new_cash + positions_value

            await db.execute(
                "UPDATE system_states SET cash_balance=?, portfolio_value=?, "
                "daily_volume=daily_volume+?, total_trades_today=total_trades_today+1, "
                "updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                (new_cash, new_portfolio, order_value, user_id)
            )
            await db.commit()

        return await get_portfolio(user_id)
    finally:
        await db.close()


async def get_portfolio(user_id: int) -> dict:
    """Get full portfolio for a user."""
    db = await get_db()
    try:
        state = await get_system_state(user_id)
        cursor = await db.execute(
            "SELECT * FROM positions WHERE user_id = ? ORDER BY symbol",
            (user_id,)
        )
        rows = await cursor.fetchall()
        positions = [dict(r) for r in rows]

        return {
            "totalValue": state["portfolio_value"] if state else 100000,
            "cash": state["cash_balance"] if state else 100000,
            "positions": positions,
            "dailyVolume": state["daily_volume"] if state else 0,
            "totalTradesToday": state["total_trades_today"] if state else 0,
        }
    finally:
        await db.close()
