"""Local Llama2‐7B with simple RAG for cheap preliminary screening.

Requires running llama.cpp server at http://llama:8080 (see docker-compose snippet).

Functions:
  `screen_project(name, desc) -> (is_flagged: bool, reason: str)`

Logic:
  • Query local model: "Is project likely scam …?" with temperature=0.
  • If confident 'yes', mark as scam → GPT not called (save tokens).
"""
from __future__ import annotations

import aiohttp
import logging
import os

log = logging.getLogger(__name__)
_LLAMA_URL = os.getenv("LLAMA_URL", "http://llama:8080/completion")


async def _llama(prompt: str) -> str:
    async with aiohttp.ClientSession() as s:
        payload = {
            "prompt": prompt,
            "temperature": 0,
            "max_tokens": 128,
            "stop": ["\n"],
        }
        async with s.post(_LLAMA_URL, json=payload, timeout=30) as r:
            r.raise_for_status()
            data = await r.json()
            return data["content"].strip()


async def screen_project(name: str, description: str) -> tuple[bool, str]:
    prompt = f"""Answer strictly with 'YES' or 'NO' and a short reason.
Question: Is the following airdrop project a scam risk?
Project: {name}
Details: {description}
Answer:"""
    try:
        reply = await _llama(prompt)
    except Exception as e:
        log.debug("llama error: %s", e)
        return False, ""

    lower = reply.lower()
    if lower.startswith("yes"):
        return True, reply
    return False, reply
