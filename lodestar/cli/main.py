"""Lodestar CLI — command-line interface for the trading bot."""

from __future__ import annotations

import threading

import click
from rich.console import Console
from rich.table import Table

from lodestar.config import load_settings
from lodestar.utils.logging import setup_logging

console = Console()


@click.group()
@click.option("--log-level", default="INFO", help="Logging level")
@click.option("--log-file", default=None, help="Optional log file path")
@click.pass_context
def cli(ctx: click.Context, log_level: str, log_file: str | None) -> None:
    """Lodestar — Automated Trading Bot."""
    ctx.ensure_object(dict)
    ctx.obj["logger"] = setup_logging(level=log_level, log_file=log_file)
    ctx.obj["settings"] = load_settings()


# ------------------------------------------------------------------
# run — start the bot
# ------------------------------------------------------------------


@cli.command()
@click.option(
    "--symbols",
    default="",
    help="Comma-separated list of symbols to trade (e.g. AAPL,MSFT,TSLA)",
)
@click.option("--paper/--live", default=True, help="Paper or live trading mode")
@click.pass_context
def run(ctx: click.Context, symbols: str, paper: bool) -> None:
    """Start the trading bot."""
    from lodestar.bot import TradingBot

    settings = ctx.obj["settings"]
    if paper:
        settings.trading.mode = "paper"
    else:
        settings.trading.mode = "live"

    custom = [s.strip().upper() for s in symbols.split(",") if s.strip()] or None

    console.print(f"\n[bold green]Lodestar Trading Bot[/bold green]")
    console.print(f"  Mode:       [yellow]{settings.trading.mode}[/yellow]")
    console.print(f"  Strategies: {settings.strategies.enabled_list}")
    console.print(f"  Interval:   {settings.trading.interval_minutes}m")
    if custom:
        console.print(f"  Symbols:    {custom}")
    console.print()

    if settings.trading.mode == "live":
        if not click.confirm(
            "You are about to trade with REAL money. Continue?", default=False
        ):
            console.print("[red]Aborted.[/red]")
            return

    bot = TradingBot(settings)
    bot.run(custom_watchlist=custom)


# ------------------------------------------------------------------
# scan — run a single scan cycle
# ------------------------------------------------------------------


@cli.command()
@click.option("--symbols", default="", help="Comma-separated symbols")
@click.pass_context
def scan(ctx: click.Context, symbols: str) -> None:
    """Run a single scan cycle without continuous loop."""
    from lodestar.bot import TradingBot

    settings = ctx.obj["settings"]
    settings.trading.mode = "paper"
    custom = [s.strip().upper() for s in symbols.split(",") if s.strip()] or None

    bot = TradingBot(settings)
    if not bot.connect():
        console.print("[red]Failed to connect to broker[/red]")
        return

    bot.refresh_watchlist(custom=custom)
    trades = bot.scan_and_trade()
    bot.disconnect()

    # Display results
    if bot.signal_log:
        table = Table(title="Signals")
        table.add_column("Symbol")
        table.add_column("Strategy")
        table.add_column("Side")
        table.add_column("Strength")
        table.add_column("Confidence")
        table.add_column("Reason")
        for sig in bot.signal_log:
            table.add_row(
                sig.symbol,
                sig.strategy,
                sig.side.value,
                sig.strength.value,
                f"{sig.confidence:.0%}",
                sig.reason,
            )
        console.print(table)

    if trades:
        table = Table(title="Trades Executed")
        table.add_column("Symbol")
        table.add_column("Side")
        table.add_column("Qty")
        table.add_column("Price")
        table.add_column("Status")
        table.add_column("Strategy")
        for t in trades:
            table.add_row(
                t.symbol,
                t.side.value,
                f"{t.quantity:.4f}",
                f"${t.price:.2f}",
                t.status,
                t.strategy,
            )
        console.print(table)
    else:
        console.print("[yellow]No trades executed.[/yellow]")


# ------------------------------------------------------------------
# portfolio — show current portfolio
# ------------------------------------------------------------------


@cli.command()
@click.pass_context
def portfolio(ctx: click.Context) -> None:
    """Display current portfolio positions."""
    from lodestar.bot import TradingBot

    settings = ctx.obj["settings"]
    bot = TradingBot(settings)
    if not bot.connect():
        console.print("[red]Failed to connect[/red]")
        return

    snap = bot.portfolio.snapshot()
    bot.disconnect()

    console.print(f"\n[bold]Portfolio Snapshot[/bold]")
    console.print(f"  Total Equity: [green]${snap.total_equity:,.2f}[/green]")
    console.print(f"  Cash:         ${snap.cash:,.2f}")
    console.print(f"  Positions:    {len(snap.positions)}\n")

    if snap.positions:
        table = Table(title="Open Positions")
        table.add_column("Symbol")
        table.add_column("Qty", justify="right")
        table.add_column("Avg Cost", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("Value", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("P&L %", justify="right")
        for p in snap.positions:
            pnl_color = "green" if p.unrealized_pnl >= 0 else "red"
            table.add_row(
                p.symbol,
                f"{p.quantity:.4f}",
                f"${p.average_cost:.2f}",
                f"${p.current_price:.2f}",
                f"${p.market_value:,.2f}",
                f"[{pnl_color}]${p.unrealized_pnl:+,.2f}[/{pnl_color}]",
                f"[{pnl_color}]{p.unrealized_pnl_pct:+.2%}[/{pnl_color}]",
            )
        console.print(table)


# ------------------------------------------------------------------
# dashboard — launch the web dashboard
# ------------------------------------------------------------------


@cli.command()
@click.pass_context
def dashboard(ctx: click.Context) -> None:
    """Launch the web dashboard."""
    from lodestar.dashboard.app import create_app

    settings = ctx.obj["settings"]
    app = create_app(settings)

    import uvicorn

    console.print(
        f"\n[bold green]Dashboard[/bold green] → "
        f"http://{settings.dashboard.host}:{settings.dashboard.port}\n"
    )
    uvicorn.run(app, host=settings.dashboard.host, port=settings.dashboard.port)


# ------------------------------------------------------------------
# dashboard-and-bot — run both concurrently
# ------------------------------------------------------------------


@cli.command("run-all")
@click.option("--symbols", default="", help="Comma-separated symbols")
@click.option("--paper/--live", default=True)
@click.pass_context
def run_all(ctx: click.Context, symbols: str, paper: bool) -> None:
    """Run the trading bot AND web dashboard together."""
    from lodestar.bot import TradingBot
    from lodestar.dashboard.app import create_app

    settings = ctx.obj["settings"]
    settings.trading.mode = "paper" if paper else "live"
    custom = [s.strip().upper() for s in symbols.split(",") if s.strip()] or None

    bot = TradingBot(settings)
    app = create_app(settings, bot=bot)

    # Start bot in background thread
    bot_thread = threading.Thread(target=bot.run, kwargs={"custom_watchlist": custom}, daemon=True)
    bot_thread.start()

    import uvicorn

    console.print(
        f"\n[bold green]Lodestar[/bold green] running — "
        f"Dashboard at http://{settings.dashboard.host}:{settings.dashboard.port}\n"
    )
    uvicorn.run(app, host=settings.dashboard.host, port=settings.dashboard.port)
