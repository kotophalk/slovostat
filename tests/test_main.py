import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_index_returns_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SlovoStat" in resp.text


def test_analyze_success():
    with patch("app.main.fetch_visible_text", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = "Привет мир"
        with patch("app.main.check_limit", new_callable=AsyncMock, return_value=True):
            with patch("app.main.record_request", new_callable=AsyncMock):
                resp = client.post("/analyze", json={"url": "http://example.com"})
                assert resp.status_code == 200
                data = resp.json()
                assert data["words"] == 2
                assert data["chars"] == 10
                assert data["chars_no_spaces"] == 9


def test_analyze_rate_limited():
    with patch("app.main.check_limit", new_callable=AsyncMock, return_value=False):
        resp = client.post("/analyze", json={"url": "http://example.com"})
        assert resp.status_code == 429
        assert "лимит" in resp.json()["error"].lower()


def test_analyze_fetch_error():
    from app.fetcher import FetchError

    with patch("app.main.check_limit", new_callable=AsyncMock, return_value=True):
        with patch("app.main.fetch_visible_text", new_callable=AsyncMock, side_effect=FetchError("Не удалось")):
            resp = client.post("/analyze", json={"url": "http://example.com"})
            assert resp.status_code == 422
            assert "Не удалось" in resp.json()["error"]
