import asyncio
import logging
import time

import aiosqlite

from app.config import RATE_LIMIT_PER_DAY, DATABASE_PATH

logger = logging.getLogger(__name__)

_DAY_SECONDS = 86400
# Политика конфиденциальности обещает удалять IP «по истечении суток».
# Раньше записи чистились раз в 100 вставок, и при малом трафике жили
# дольше суток — поэтому чистка идёт по времени, фоновым циклом из
# lifespan, независимо от того, приходят ли запросы (16.11.2026).
_PURGE_INTERVAL = 600

_db: aiosqlite.Connection | None = None
_db_lock = asyncio.Lock()


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
    db = await _connection()
    await db.execute(
        "INSERT INTO requests (ip, timestamp) VALUES (?, ?)", (ip, time.time())
    )
    await db.commit()


async def purge_expired(now: float | None = None) -> int:
    """Удаляет записи старше суток. Возвращает число удалённых строк."""
    db = await _connection()
    cutoff = (time.time() if now is None else now) - _DAY_SECONDS
    cursor = await db.execute("DELETE FROM requests WHERE timestamp < ?", (cutoff,))
    await db.commit()
    return cursor.rowcount


async def purge_loop(interval: float = _PURGE_INTERVAL) -> None:
    """Чистит протухшие записи сразу при старте и затем раз в interval секунд.

    Ошибка базы не останавливает цикл: следующая попытка — через interval.
    """
    while True:
        try:
            await purge_expired()
        except Exception:
            logger.exception("Не удалось удалить устаревшие записи лимитера")
        await asyncio.sleep(interval)
