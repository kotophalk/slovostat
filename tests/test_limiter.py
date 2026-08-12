import time
import tempfile
import os
import pytest
from unittest.mock import patch

from app.limiter import check_limit, record_request


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.mark.asyncio
async def test_within_limit(db_path):
    assert await check_limit("1.2.3.4", db_path) is True


@pytest.mark.asyncio
async def test_exceeds_limit(db_path):
    with patch("app.limiter.RATE_LIMIT_PER_DAY", 2):
        await record_request("1.2.3.4", db_path)
        await record_request("1.2.3.4", db_path)
        assert await check_limit("1.2.3.4", db_path) is False


@pytest.mark.asyncio
async def test_different_ips(db_path):
    with patch("app.limiter.RATE_LIMIT_PER_DAY", 1):
        await record_request("1.1.1.1", db_path)
        assert await check_limit("1.1.1.1", db_path) is False
        assert await check_limit("2.2.2.2", db_path) is True


@pytest.mark.asyncio
async def test_old_records_not_counted(db_path):
    with patch("app.limiter.RATE_LIMIT_PER_DAY", 1):
        with patch("app.limiter.time.time", return_value=1000.0):
            await record_request("1.2.3.4", db_path)
        # Now time is 1000 + 86401 (past 24h)
        with patch("app.limiter.time.time", return_value=87401.0):
            assert await check_limit("1.2.3.4", db_path) is True
