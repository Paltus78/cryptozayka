"""Expose current gas price as Prometheus gauge."""
from __future__ import annotations

import asyncio
from prometheus_client import Gauge

from ..treasury.gas import get_gas_price_wei, start_oracle

GAS_PRICE_GWEI = Gauge("gas_price_gwei", "Current gas price in gwei")

start_oracle()

async def loop():
    while True:
        wei = await get_gas_price_wei()
        GAS_PRICE_GWEI.set(wei / 1e9)
        await asyncio.sleep(30)
