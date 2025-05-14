"""
Legacy-shim для старого импорта `cryptozayka.storage_pg`.

Весь реальный код теперь в пакете `cryptozayka.storage.pg`.
Этот файл просто реэкспортирует публичные функции.
"""

from cryptozayka.storage.pg import (  # noqa: F401
    get_pool,
    get_db,
    add_batch,
    next_batch,
    mark_batch,
)

__all__ = [
    "get_pool",
    "get_db",
    "add_batch",
    "next_batch",
    "mark_batch",
]
