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
async def test_cleanup_removes_old_rows(db):
    with patch("app.limiter._CLEANUP_EVERY", 1):
        with patch("app.limiter.time.time", return_value=1000.0):
            await record_request("1.2.3.4")
        with patch("app.limiter.time.time", return_value=87401.0):
            await record_request("5.6.7.8")

    connection = await limiter._connection()
    async with connection.execute("SELECT COUNT(*) FROM requests") as cursor:
        assert (await cursor.fetchone())[0] == 1


@pytest.mark.asyncio
async def test_reuses_single_connection(db):
    assert await limiter._connection() is await limiter._connection()
