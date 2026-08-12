import time
import aiosqlite

from app.config import RATE_LIMIT_PER_DAY, DATABASE_PATH

_DAY_SECONDS = 86400


async def _get_db(db_path: str = None) -> aiosqlite.Connection:
    db = await aiosqlite.connect(db_path or DATABASE_PATH)
    await db.execute(
        "CREATE TABLE IF NOT EXISTS requests (ip TEXT, timestamp REAL)"
    )
    await db.commit()
    return db


async def check_limit(ip: str, db_path: str = None) -> bool:
    """Возвращает True если лимит НЕ превышен."""
    db = await _get_db(db_path)
    try:
        cutoff = time.time() - _DAY_SECONDS
        async with db.execute(
            "SELECT COUNT(*) FROM requests WHERE ip = ? AND timestamp > ?",
            (ip, cutoff),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] < RATE_LIMIT_PER_DAY
    finally:
        await db.close()


async def record_request(ip: str, db_path: str = None) -> None:
    """Записывает запрос."""
    db = await _get_db(db_path)
    try:
        await db.execute(
            "INSERT INTO requests (ip, timestamp) VALUES (?, ?)",
            (ip, time.time()),
        )
        await db.execute(
            "DELETE FROM requests WHERE timestamp < ?",
            (time.time() - _DAY_SECONDS,),
        )
        await db.commit()
    finally:
        await db.close()
