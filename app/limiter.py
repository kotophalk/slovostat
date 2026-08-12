import asyncio
import time

import aiosqlite

from app.config import RATE_LIMIT_PER_DAY, DATABASE_PATH

_DAY_SECONDS = 86400
# Чистим протухшие записи не на каждой вставке: таблица маленькая,
# а лишний DELETE на каждый запрос — лишняя запись на диск.
_CLEANUP_EVERY = 100

_db: aiosqlite.Connection | None = None
_db_lock = asyncio.Lock()
_writes_since_cleanup = 0


async def init_db(db_path: str | None = None) -> aiosqlite.Connection:
    """Открывает соединение и создаёт схему. Вызывается один раз при старте."""
    global _db
    async with _db_lock:
        if _db is None:
            db = await aiosqlite.connect(db_path or DATABASE_PATH)
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                "CREATE TABLE IF NOT EXISTS requests (ip TEXT NOT NULL, timestamp REAL NOT NULL)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS requests_ip_ts ON requests (ip, timestamp)"
            )
            await db.commit()
            _db = db
    return _db


async def close_db() -> None:
    global _db
    async with _db_lock:
        if _db is not None:
            await _db.close()
            _db = None


async def _connection() -> aiosqlite.Connection:
    return _db if _db is not None else await init_db()


async def ping_db() -> None:
    """Проверяет, что база отвечает. Бросает исключение, если нет."""
    db = await _connection()
    await db.execute("SELECT 1")


async def check_limit(ip: str) -> bool:
    """Возвращает True если лимит НЕ превышен."""
    db = await _connection()
    cutoff = time.time() - _DAY_SECONDS
    async with db.execute(
        "SELECT COUNT(*) FROM requests WHERE ip = ? AND timestamp > ?",
        (ip, cutoff),
    ) as cursor:
        row = await cursor.fetchone()
    return row[0] < RATE_LIMIT_PER_DAY


async def record_request(ip: str) -> None:
    """Записывает запрос."""
    global _writes_since_cleanup
    db = await _connection()
    now = time.time()
    await db.execute("INSERT INTO requests (ip, timestamp) VALUES (?, ?)", (ip, now))

    _writes_since_cleanup += 1
    if _writes_since_cleanup >= _CLEANUP_EVERY:
        _writes_since_cleanup = 0
        await db.execute(
            "DELETE FROM requests WHERE timestamp < ?", (now - _DAY_SECONDS,)
        )
    await db.commit()
