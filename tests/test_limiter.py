import asyncio

import pytest
import pytest_asyncio
from unittest.mock import patch

from app import limiter
from app.limiter import check_limit, record_request


@pytest_asyncio.fixture
async def db(tmp_path):
    await limiter.close_db()
    await limiter.init_db(str(tmp_path / "test.db"))
    yield
    await limiter.close_db()


@pytest.mark.asyncio
async def test_within_limit(db):
    assert await check_limit("1.2.3.4") is True


@pytest.mark.asyncio
async def test_exceeds_limit(db):
    with patch("app.limiter.RATE_LIMIT_PER_DAY", 2):
        await record_request("1.2.3.4")
        await record_request("1.2.3.4")
        assert await check_limit("1.2.3.4") is False


@pytest.mark.asyncio
async def test_different_ips(db):
    with patch("app.limiter.RATE_LIMIT_PER_DAY", 1):
        await record_request("1.1.1.1")
        assert await check_limit("1.1.1.1") is False
        assert await check_limit("2.2.2.2") is True


@pytest.mark.asyncio
async def test_old_records_not_counted(db):
    with patch("app.limiter.RATE_LIMIT_PER_DAY", 1):
        with patch("app.limiter.time.time", return_value=1000.0):
            await record_request("1.2.3.4")
        # Now time is 1000 + 86401 (past 24h)
        with patch("app.limiter.time.time", return_value=87401.0):
            assert await check_limit("1.2.3.4") is True


@pytest.mark.asyncio
async def test_purge_removes_rows_older_than_a_day(db):
    # Политика обещает удалять IP «по истечении суток» — без оглядки на трафик.
    with patch("app.limiter.time.time", return_value=1000.0):
        await record_request("1.2.3.4")
    with patch("app.limiter.time.time", return_value=80000.0):
        await record_request("5.6.7.8")

    removed = await limiter.purge_expired(now=87401.0)

    assert removed == 1
    connection = await limiter._connection()
    async with connection.execute("SELECT ip FROM requests") as cursor:
        assert [row[0] for row in await cursor.fetchall()] == ["5.6.7.8"]


@pytest.mark.asyncio
async def test_purge_loop_purges_at_start_and_survives_errors(db):
    # Чистка идёт по времени, а не по числу вставок: при тишине на сайте
    # старые IP тоже должны уйти. Ошибка базы не должна убивать цикл.
    calls = []

    async def flaky_purge(now=None):
        calls.append(now)
        if len(calls) == 1:
            raise RuntimeError("база недоступна")
        return 0

    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    with patch("app.limiter.purge_expired", flaky_purge), patch("app.limiter.asyncio.sleep", fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            await limiter.purge_loop(interval=600)

    assert len(calls) == 2
    assert sleeps == [600, 600]


@pytest.mark.asyncio
async def test_reuses_single_connection(db):
    assert await limiter._connection() is await limiter._connection()
