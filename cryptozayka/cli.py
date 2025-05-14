"""Top-level CLI entry-point (`cryptozayka …`) based on Typer."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint

from .storage import add_batch
from .worker import worker_loop
from .treasury.eth import topup_min_reserve, collect_eth, _WALLETS

app = typer.Typer(help="CryptoZayka command‑line interface")


# ─────────────────────────── loader cmd ──────────────────────────
@app.command()
def load(path: Path = typer.Argument(..., exists=True, readable=True)):
    """Load batch IDs from *path* (text file, one id per line)."""
    ids = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    for bid in ids:
        asyncio.run(add_batch(bid))
        rprint(f"[green]✔ added[/] {bid}")
    rprint(f"[bold blue]Loaded {len(ids)} batch(es) from {path}[/]")


# ─────────────────────────── worker cmd ─────────────────────────
@app.command()
def worker():
    """Run endless worker loop (Ctrl+C to stop)."""
    logging.basicConfig(level="INFO", format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    rprint("[bold]🚀 Worker started. Press CTRL+C to exit…[/]")
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        rprint("[yellow]\nInterrupted by user[/]")


# ───────────────────────── treasury cmds ────────────────────────
treasury_app = typer.Typer(help="Manage treasury wallets")
app.add_typer(treasury_app, name="treasury")


@treasury_app.command("topup")  # cryptozayka treasury topup
def _topup(reserve: float = typer.Option(0.01), topup: float = typer.Option(0.015)):
    """Keep each sub‑wallet above *reserve* ETH."""
    asyncio.run(topup_min_reserve(reserve_eth=reserve, topup_eth=topup))


@treasury_app.command("collect")  # cryptozayka treasury collect
def _collect():
    """Collect ETH from all sub‑wallets back to the main wallet."""
    for w in _WALLETS[1:]:
        tx = collect_eth(w)
        if tx:
            rprint(f"[green]⬅ collected[/] from {w['label']} | tx={tx}")


if __name__ == "__main__":  # pragma: no cover
    app()
