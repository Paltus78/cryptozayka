"""Claim & swap tokens via 0x API (stub)."""
import aiohttp, os, logging, asyncio
from web3 import Web3
from decimal import Decimal

from .eth import w3, MAIN_ADDRESS, MAIN_PK, get_gas_price_wei, GAS_LIMIT

log = logging.getLogger(__name__)
ZEROX = "https://api.0x.org/"

async def claim_and_swap(token_address: str, amount: int):
    # claim tx already executed earlier, now build swap
    async with aiohttp.ClientSession() as s:
        params = {
            "sellToken": token_address,
            "buyToken": "USDC",
            "sellAmount": amount,
            "takerAddress": MAIN_ADDRESS,
        }
        async with s.get(ZEROX + "swap/v1/quote", params=params) as r:
            quote = await r.json()
    tx = quote["to"]
    data = quote["data"]
    value = int(quote["value"])
    gas_price = await get_gas_price_wei()
    txn = {
        "to": tx,
        "data": data,
        "value": value,
        "gas": GAS_LIMIT * 2,
        "gasPrice": gas_price,
        "nonce": w3.eth.get_transaction_count(MAIN_ADDRESS, "pending"),
    }
    signed = w3.eth.account.sign_transaction(txn, MAIN_PK)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    log.info("Swap tx: %s", tx_hash.hex())
    return tx_hash.hex()
