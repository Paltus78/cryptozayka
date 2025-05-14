"""Compatibility wrapper: old imports `cryptozayka.storage` now point to Postgres backend.

No code changes needed in existing modules.
"""
from __future__ import annotations

from .storage_pg import add_batch, next_batch, mark_batch  # re-export
