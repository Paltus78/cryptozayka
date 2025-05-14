"""Treasury helpers: dynamic gas oracle, POA-support, авто-топ-ап / сбор ETH."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from decimal import Decimal
from importlib import import_module
from typing import Dict, List, Callable, Any

from web3 import Web3

log = logging.getLogger(__name__)

# ──────────────── universal geth_poa_middleware ────────────────
def _load_poa() -> Callable[[Callable[..., Any], "Web3"], Callable[..., Any]]:
    for mod, attr in (
        ("web3.middleware", "geth_poa_middleware"),          # ≤6.1
        ("web3.middleware.geth_poa", "geth_poa_middleware"), # ≥6.2
    ):
        try:
            return getattr(import_module(mod), attr)
        except (ImportError, AttributeError):
            continue

    # web3 7.x beta – модуля нет: добавляем no-op и пишем warning
    log.warning("geth_poa_middleware not found – using no-op stub")
    def _noop(make_request, _w3):
        return make_request
    return _noop

geth_poa_middleware = _load_poa()
# ─────────────────────────────────────────────────────────────────

# ─────────────── runtime config ────────────────────────────────
RPC_URL  = os.getenv("ETH_RPC_URL") or "https://mainnet.infura.io/v3/demo"
MIN_RESERVE_ETH = Decimal(os.getenv("MIN_RESERVE_ETH", "0.05"))

MAIN_ADDRESS = Web3.to_checksum_address(os.getenv("MAIN_WALLET_ADDRESS", "0x0"))
MAIN_PK      = os.getenv("MAIN_WALLET_PK", "0x0")

SUB_WALLETS: List[Dict[str, str]] = json.loads(os.getenv("SUB_WALLETS_JSON", "[]"))
for w in SUB_WALLETS:
    w["address"] = Web3.to_checksum_address(w["address"])

# экспорт для cli
_WALLETS = SUB_WALLETS

# ─────────────── web3 init ─────────────────────────────────────
w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

GAS_LIMIT = 21_000

# ─────────────── helpers ───────────────────────────────────────
async def _gas_price_wei() -> int:
    # простой gas-oracle: берем средний gasPrice сети
    return int(w3.eth.gas_price * 1.1)  # +10 % буфер

def _eth(balance_wei: int) -> Decimal:
    return Decimal(w3.from_wei(balance_wei, "ether"))

def get_balance(addr: str) -> Decimal:
    return _eth(w3.eth.get_balance(Web3.to_checksum_address(addr)))

async def _send_eth(from_pk: str, to_addr: str, amount_eth: Decimal) -> str:
    gas_price = await _gas_price_wei()
    account   = w3.eth.account.from_key(from_pk)
    tx = {
        "to": Web3.to_checksum_address(to_addr),
        "value": w3.to_wei(amount_eth, "ether"),
        "gas": GAS_LIMIT,
        "gasPrice": gas_price,
        "nonce": w3.eth.get_transaction_count(account.address, "pending"),
    }
    signed = w3.eth.account.sign_transaction(tx, from_pk)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    log.info("TX  %.4f ETH  %s → %s  | %s",
             amount_eth, account.address, to_addr, tx_hash.hex())
    return tx_hash.hex()

# ─────────────── public ops (used by cli.py) ───────────────────
async def topup_min_reserve_async() -> None:
    """Пополнить каждый суб-кошелёк до MIN_RESERVE_ETH из главного."""
    for w in SUB_WALLETS:
        bal = get_balance(w["address"])
        if bal < MIN_RESERVE_ETH:
            need = MIN_RESERVE_ETH - bal
            await _send_eth(MAIN_PK, w["address"], need)

def topup_min_reserve() -> None:
    asyncio.run(topup_min_reserve_async())


async def collect_eth_async() -> None:
    """Собрать всё сверх резерва обратно на главный кошелёк."""
    for w in SUB_WALLETS:
        bal = get_balance(w["address"])
        excess = bal - MIN_RESERVE_ETH
        if excess > Decimal("0"):
            await _send_eth(w["priv_key"], MAIN_ADDRESS, excess)

def collect_eth() -> None:
    asyncio.run(collect_eth_async())


__all__ = [
    "_WALLETS",
    "get_balance",
    "topup_min_reserve",
    "collect_eth",
]
