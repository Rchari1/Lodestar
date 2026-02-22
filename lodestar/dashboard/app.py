"""FastAPI web dashboard for Lodestar."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lodestar.config import Settings

_HERE = Path(__file__).parent
_TEMPLATES = _HERE / "templates"
_STATIC = _HERE / "static"

# Shared state — the bot instance is injected at startup
_bot_ref: dict[str, Any] = {"bot": None}


def create_app(settings: Settings, bot: Any | None = None) -> FastAPI:
    app = FastAPI(title="Lodestar Dashboard", version="0.1.0")
    _bot_ref["bot"] = bot

    if _STATIC.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    templates = Jinja2Templates(directory=str(_TEMPLATES))

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        bot = _bot_ref.get("bot")
        snapshot = None
        trades: list = []
        signals: list = []
        if bot:
            snapshot = bot.portfolio.snapshot()
            trades = bot.trade_log[-50:]
            signals = bot.signal_log[-50:]
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "snapshot": snapshot,
                "trades": trades,
                "signals": signals,
                "settings": settings,
            },
        )

    # ------------------------------------------------------------------
    # API endpoints
    # ------------------------------------------------------------------

    @app.get("/api/status")
    async def api_status() -> dict:
        bot = _bot_ref.get("bot")
        if not bot:
            return {"status": "not running"}
        snap = bot.portfolio.snapshot()
        return {
            "status": "running" if bot._running else "stopped",
            "mode": settings.trading.mode,
            "equity": snap.total_equity,
            "cash": snap.cash,
            "positions": len(snap.positions),
            "trades_today": len(bot.portfolio.trades_today),
            "total_signals": len(bot.signal_log),
            "total_trades": len(bot.trade_log),
        }

    @app.get("/api/positions")
    async def api_positions() -> list[dict]:
        bot = _bot_ref.get("bot")
        if not bot:
            return []
        snap = bot.portfolio.snapshot()
        return [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_cost": p.average_cost,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "pnl": p.unrealized_pnl,
                "pnl_pct": p.unrealized_pnl_pct,
            }
            for p in snap.positions
        ]

    @app.get("/api/trades")
    async def api_trades() -> list[dict]:
        bot = _bot_ref.get("bot")
        if not bot:
            return []
        return [
            {
                "timestamp": t.timestamp.isoformat(),
                "symbol": t.symbol,
                "side": t.side.value,
                "quantity": t.quantity,
                "price": t.price,
                "status": t.status,
                "strategy": t.strategy,
                "reason": t.reason,
            }
            for t in bot.trade_log[-100:]
        ]

    @app.get("/api/signals")
    async def api_signals() -> list[dict]:
        bot = _bot_ref.get("bot")
        if not bot:
            return []
        return [
            {
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "side": s.side.value,
                "strength": s.strength.value,
                "confidence": s.confidence,
                "strategy": s.strategy,
                "reason": s.reason,
            }
            for s in bot.signal_log[-100:]
        ]

    @app.get("/api/snapshots")
    async def api_snapshots() -> list[dict]:
        bot = _bot_ref.get("bot")
        if not bot:
            return []
        return [
            {
                "timestamp": s.timestamp.isoformat(),
                "equity": s.total_equity,
                "cash": s.cash,
                "positions": len(s.positions),
            }
            for s in bot.snapshots[-200:]
        ]

    return app
