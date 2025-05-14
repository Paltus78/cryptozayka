"""Batch results parser – converts OpenAI `.jsonl` dumps into DB entries."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..storage import get_db
from ..core.strategy import _interpret  # reuse scam/recommend detector

log = logging.getLogger(__name__)


def _ensure_table() -> None:
    """Create `gpt_judgements` table if it doesn't exist."""
    create_sql = """        CREATE TABLE IF NOT EXISTS gpt_judgements(
        project  TEXT PRIMARY KEY,
        verdict  TEXT NOT NULL,
        text     TEXT NOT NULL,
        ts       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"""
    # Run sync via connection helper
    import asyncio
    asyncio.run(_run_sql(create_sql))


async def _run_sql(sql: str) -> None:
    async with get_db() as db:
        await db.executescript(sql)
        await db.commit()


def _extract_project(entry: dict) -> tuple[str, str]:
    """Return (project_name, gpt_reply). Fallbacks for legacy formats."""
    project = (
        entry.get("project") or
        entry.get("custom_id") or
        entry.get("id") or
        "unknown"
    )
    reply = (
        entry.get("response", {})
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    if not reply and "content" in entry:
        reply = entry["content"]
    return str(project), reply


async def _store(project: str, verdict: str, text: str) -> None:
    async with get_db() as db:
        await db.execute(
            """INSERT OR REPLACE INTO gpt_judgements(project, verdict, text, ts)
                   VALUES (?, ?, ?, ?);""",
            (project, verdict, text, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def parse_file(path: Path) -> int:
    """Parse single `.jsonl` file and persist judgements. Returns count."""
    if path.suffix != ".jsonl":
        raise ValueError("expected .jsonl file")
    lines = path.read_text(encoding="utf-8").splitlines()

    imported = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            log.warning("skip bad json (%s): %s", path.name, e)
            continue

        project, reply = _extract_project(entry)
        if not reply:
            log.warning("skip empty reply for %s in %s", project, path.name)
            continue

        is_scam, recommend = _interpret(reply)
        verdict = "🚫 scam" if is_scam else ("✅ participate" if recommend else "⚠️ skip")
        await _store(project, verdict, reply)
        imported += 1
    log.info("%s: imported %d judgements", path.name, imported)
    return imported


async def parse_dir(dir_path: Path) -> int:
    """Parse all `.jsonl` files in directory. Returns total count."""
    _ensure_table()
    total = 0
    for file in dir_path.iterdir():
        if file.suffix == ".jsonl":
            total += await parse_file(file)
    log.info("Total judgements imported: %d", total)
    return total
