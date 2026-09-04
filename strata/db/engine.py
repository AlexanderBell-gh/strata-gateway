import os
from pathlib import Path

import aiosqlite

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        raise RuntimeError("Database not initialised")
    return _db


async def connect(db_path: str) -> aiosqlite.Connection:
    global _db
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(db_path)
    _db.row_factory = aiosqlite.Row
    return _db


async def close() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
