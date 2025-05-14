"""Feature‑flags via Unleash (https://getunleash.io).

Env vars used:
  UNLEASH_URL      – http(s) endpoint of Unleash server
  UNLEASH_API_TOKEN – client token
  UNLEASH_APP_NAME – defaults to 'cryptozayka'

Usage:
  from cryptozayka.core.flags import is_enabled, get_variant

  if is_enabled("new_prompt"):
      ...
  model = get_variant("gpt_model", "gpt-4o-mini")
"""

import os
from functools import lru_cache
from typing import Any

from UnleashClient import UnleashClient

_url = os.getenv("UNLEASH_URL")
_token = os.getenv("UNLEASH_API_TOKEN")
_app = os.getenv("UNLEASH_APP_NAME", "cryptozayka")

_client: UnleashClient | None = None
if _url and _token:
    _client = UnleashClient(url=_url, app_name=_app, custom_headers={"Authorization": _token})
    _client.initialize_client()


def _off() -> bool:
    return _client is None

def is_enabled(flag: str, context: dict[str, Any] | None = None, default: bool = False) -> bool:
    if _off():
        return default
    return _client.is_enabled(flag, context or {}, default)


def get_variant(flag: str, default: str) -> str:
    if _off():
        return default
    variant = _client.get_variant(flag)
    if variant["enabled"]:
        return variant["name"]
    return default
