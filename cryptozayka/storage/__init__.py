"""
Публичный API пакета cryptozayka.storage
Импортирует всё из внутреннего модуля pg, + alias get_db.
"""

from .pg import (  # noqa
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

