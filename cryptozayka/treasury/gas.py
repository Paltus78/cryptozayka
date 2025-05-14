"""Asynchronous gas price oracle.

Fetches current fast gas price (Gwei) every 60 s from `https://gasstation-mainnet.matic.network/v2`
as fallback can query `https://ethgasstation.info/json/ethgasAPI.json`.

Treasury functions should call :func:`get_gas_price_wei` for up‑to‑date value.
"""
from __future__ import annotations

import asyncio
import logging
import os

import aiohttp

_gas_price_wei = 30 * 10**9  # default 30 gwei
_lock = asyncio.Lock()

log = logging.getLogger(__name__)

async def _fetch_matic() -> int | None:
    url = "https://gasstation-mainnet.matic.network/v2"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
        async with s.get(url) as r:
            if r.status != 200:
                return None
            data = await r.json()
            gwei = data["fast"]["maxFee"]
            return int(gwei * 1e9)

async def _fetch_ethgasstation() -> int | None:
    url = "https://ethgasstation.info/json/ethgasAPI.json"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
        async with s.get(url) as r:
            if r.status != 200:
                return None
            data = await r.json()
            # ethgasstation returns 10x gwei
            gwei = data["fast"] / 10
            return int(gwei * 1e9)

async def _update_loop() -> None:
    global _gas_price_wei
    while True:
        for fetch in (_fetch_matic, _fetch_ethgasstation):
            try:
                val = await fetch()
                if val:
                    async with _lock:
                        _gas_price_wei = val
                    log.debug("⛽ Gas oracle updated: %.1f gwei", val / 1e9)
                    break
            except Exception as e:  # noqa: BLE001
                log.debug("gas oracle fetch error: %s", e)
        await asyncio.sleep(60)

def start_oracle() -> None:
    """Launch background task (idempotent)."""
    if os.getenv("_GAS_ORACLE_STARTED"):
        return
    os.environ["_GAS_ORACLE_STARTED"] = "1"
    asyncio.get_event_loop().create_task(_update_loop())

async def get_gas_price_wei() -> int:
    async with _lock:
        return _gas_price_wei
