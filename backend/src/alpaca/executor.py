"""
Alpaca Paper Trading Executor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Real stock order execution on Alpaca's Paper Trading API.
Supports buy/sell/hold orders, market data, and portfolio info.
No real money — simulated funds for demo purposes.
"""

import os
from datetime import datetime, timezone
from typing import Optional

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
    HAS_ALPACA = True
except ImportError:
    HAS_ALPACA = False


class AlpacaExecutor:
    """
    Connects to the real Alpaca Paper Trading API.

    This executor handles:
    - Submitting market orders (buy/sell)
    - Fetching current portfolio
    - Getting real-time quotes
    - Listing positions

    All trades go through ArmorClaw BEFORE reaching this executor.
    If ArmorClaw says FREEZE, this code never runs.
    """

    def __init__(self):
        self._api_key = os.getenv("ALPACA_API_KEY", "")
        self._secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        self._base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

        self._trading_client = None
        self._data_client = None
        self._initialized = False

        if HAS_ALPACA and self._api_key and self._secret_key:
            try:
                self._trading_client = TradingClient(
                    api_key=self._api_key,
                    secret_key=self._secret_key,
                    paper=True,
                )
                self._data_client = StockHistoricalDataClient(
                    api_key=self._api_key,
                    secret_key=self._secret_key,
                )
                self._initialized = True
            except Exception as e:
                print(f"[AlpacaExecutor] Failed to initialize: {e}")

    @property
    def is_connected(self) -> bool:
        return self._initialized

    # ── Order Execution ───────────────────────────────────

    def submit_order(
        self,
        symbol: str,
        quantity: float,
        side: str,  # "buy" or "sell"
    ) -> dict:
        """
        Submit a market order to Alpaca Paper Trading.

        Returns order details or error info.
        """
        if not self._initialized:
            return self._mock_order(symbol, quantity, side)

        try:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=order_side,
                time_in_force=TimeInForce.DAY,
            )

            order = self._trading_client.submit_order(order_request)

            return {
                "success": True,
                "order_id": str(order.id),
                "symbol": order.symbol,
                "side": order.side.value,
                "quantity": str(order.qty),
                "status": order.status.value,
                "submitted_at": str(order.submitted_at),
                "type": "live_paper",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "type": "live_paper",
            }

    # ── Portfolio & Positions ─────────────────────────────

    def get_account(self) -> dict:
        """Get current account information."""
        if not self._initialized:
            return self._mock_account()

        try:
            account = self._trading_client.get_account()
            return {
                "connected": True,
                "account_id": str(account.id),
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value or account.equity),
                "status": account.status.value if hasattr(account.status, 'value') else str(account.status),
                "currency": str(account.currency),
                "type": "live_paper",
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "type": "live_paper",
            }

    def get_positions(self) -> list[dict]:
        """Get all current positions."""
        if not self._initialized:
            return self._mock_positions()

        try:
            positions = self._trading_client.get_all_positions()
            return [
                {
                    "symbol": p.symbol,
                    "quantity": float(p.qty),
                    "market_value": float(p.market_value) if p.market_value else 0,
                    "cost_basis": float(p.cost_basis) if p.cost_basis else 0,
                    "unrealized_pl": float(p.unrealized_pl) if p.unrealized_pl else 0,
                    "unrealized_plpc": float(p.unrealized_plpc) if p.unrealized_plpc else 0,
                    "current_price": float(p.current_price) if p.current_price else 0,
                    "side": p.side.value if hasattr(p.side, 'value') else str(p.side),
                }
                for p in positions
            ]
        except Exception as e:
            print(f"[AlpacaExecutor] Error fetching positions: {e}")
            return self._mock_positions()

    def get_quote(self, symbol: str) -> dict:
        """Get latest quote for a symbol."""
        if not self._initialized or not self._data_client:
            return self._mock_quote(symbol)

        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self._data_client.get_stock_latest_quote(request)
            quote = quotes.get(symbol)
            if quote:
                return {
                    "symbol": symbol,
                    "ask_price": float(quote.ask_price) if quote.ask_price else 0.0,
                    "bid_price": float(quote.bid_price) if quote.bid_price else 0.0,
                    "ask_size": float(quote.ask_size) if quote.ask_size else 0,
                    "bid_size": float(quote.bid_size) if quote.bid_size else 0,
                    "type": "live",
                }
            return self._mock_quote(symbol)
        except Exception:
            return self._mock_quote(symbol)

    def get_orders(self, limit: int = 10) -> list[dict]:
        """Get recent orders."""
        if not self._initialized:
            return []

        try:
            from alpaca.trading.requests import GetOrdersRequest
            request = GetOrdersRequest(limit=limit)
            orders = self._trading_client.get_orders(request)
            return [
                {
                    "order_id": str(o.id),
                    "symbol": o.symbol,
                    "side": o.side.value,
                    "quantity": str(o.qty),
                    "status": o.status.value,
                    "submitted_at": str(o.submitted_at),
                    "filled_at": str(o.filled_at) if o.filled_at else None,
                    "filled_avg_price": str(o.filled_avg_price) if o.filled_avg_price else None,
                }
                for o in orders
            ]
        except Exception:
            return []

    # ── Mock Fallbacks (when API keys not configured) ─────

    def _mock_order(self, symbol: str, quantity: float, side: str) -> dict:
        return {
            "success": True,
            "order_id": f"mock-{int(datetime.now(timezone.utc).timestamp())}",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "status": "filled",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "type": "mock",
        }

    def _mock_account(self) -> dict:
        return {
            "connected": True,
            "account_id": "mock-account",
            "equity": 100000.0,
            "cash": 50000.0,
            "buying_power": 100000.0,
            "portfolio_value": 100000.0,
            "status": "ACTIVE",
            "currency": "USD",
            "type": "mock",
        }

    def _mock_positions(self) -> list[dict]:
        return [
            {
                "symbol": "AAPL",
                "quantity": 50.0,
                "market_value": 8750.0,
                "cost_basis": 8000.0,
                "unrealized_pl": 750.0,
                "unrealized_plpc": 0.094,
                "current_price": 175.0,
                "side": "long",
            },
            {
                "symbol": "GOOGL",
                "quantity": 20.0,
                "market_value": 3400.0,
                "cost_basis": 3000.0,
                "unrealized_pl": 400.0,
                "unrealized_plpc": 0.133,
                "current_price": 170.0,
                "side": "long",
            },
            {
                "symbol": "MSFT",
                "quantity": 30.0,
                "market_value": 12000.0,
                "cost_basis": 11000.0,
                "unrealized_pl": 1000.0,
                "unrealized_plpc": 0.091,
                "current_price": 400.0,
                "side": "long",
            },
        ]

    def _mock_quote(self, symbol: str) -> dict:
        default_prices = {"AAPL": 175.0, "GOOGL": 170.0, "MSFT": 400.0, "TSLA": 250.0, "AMZN": 185.0}
        price = default_prices.get(symbol, 150.0)
        return {
            "symbol": symbol,
            "ask_price": price * 1.001,
            "bid_price": price * 0.999,
            "ask_size": 100,
            "bid_size": 100,
            "type": "mock",
        }
