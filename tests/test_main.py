from contextlib import contextmanager
from unittest.mock import patch, AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@contextmanager
def allow_limit():
    """Лимитер отвечает «можно» и не ходит в базу."""
    with patch("app.main.check_limit", new_callable=AsyncMock, return_value=True) as check:
        with patch("app.main.record_request", new_callable=AsyncMock) as record:
            yield check, record


def test_index_returns_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Словостат" in resp.text


def test_index_supports_head():
    resp = client.head("/")
    assert resp.status_code == 200
    assert resp.text == ""


def test_index_without_metrika_id_has_no_counter():
    """По умолчанию (стенд, тесты, чужие копии) хиты в Метрику не шлются — и cookie-уведомление не нужно."""
    with patch("app.main.METRIKA_ID", ""):
        resp = client.get("/")
    assert "mc.yandex.ru" not in resp.text
    assert "ym(" not in resp.text
    assert 'id="cookie-notice"' not in resp.text
    assert 'href="/privacy"' in resp.text  # ссылка в футере — всегда


def test_index_with_metrika_id_renders_counter_and_cookie_notice():
    with patch("app.main.METRIKA_ID", "12345678"):
        resp = client.get("/")
    assert "https://mc.yandex.ru/metrika/tag.js?id=12345678" in resp.text
    assert 'ym(12345678,"init"' in resp.text
    assert "https://mc.yandex.ru/watch/12345678" in resp.text
    assert "webvisor:false" in resp.text
    assert 'id="cookie-notice"' in resp.text
    assert "nc_accepted=1" in resp.text


def test_privacy_page():
    resp = client.get("/privacy")
    assert resp.status_code == 200
    assert "Политика конфиденциальности" in resp.text
    assert "502917677947" in resp.text
    assert "info@delosvod.ru" in resp.text
    assert client.head("/privacy").status_code == 200


@pytest.mark.parametrize("raw,expected", [
    ("12345678", "12345678"),
    (" 12345678\n", "12345678"),
    ("", ""),
    ("abc", ""),
    ("123;alert(1)", ""),
])
def test_config_counter_id_accepts_digits_only(raw, expected):
    from app.config import _counter_id
    assert _counter_id(raw) == expected


def test_health_ok():
    with patch("app.main.ping_db", new_callable=AsyncMock):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_health_supports_head():
    with patch("app.main.ping_db", new_callable=AsyncMock):
        assert client.head("/health").status_code == 200


def test_health_reports_broken_db():
    with patch("app.main.ping_db", new_callable=AsyncMock, side_effect=OSError("disk I/O error")):
        resp = client.get("/health")
        assert resp.status_code == 503
        assert resp.json() == {"status": "error"}


def test_index_renders_all_metrics():
    from app.counter import METRICS

    resp = client.get("/")
    for metric in METRICS:
        assert f'data-metric="{metric.key}"' in resp.text
        assert metric.label in resp.text


def test_analyze_success():
    with patch("app.main.fetch_visible_text", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = "Привет мир"
        with allow_limit():
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

    with allow_limit():
        with patch("app.main.fetch_visible_text", new_callable=AsyncMock, side_effect=FetchError("Не удалось")):
            resp = client.post("/analyze", json={"url": "http://example.com"})
            assert resp.status_code == 422
            assert "Не удалось" in resp.json()["error"]


def test_failed_fetch_still_counts_against_limit():
    from app.fetcher import FetchError

    with allow_limit() as (_, record):
        with patch("app.main.fetch_visible_text", new_callable=AsyncMock, side_effect=FetchError("Не удалось")):
            client.post("/analyze", json={"url": "http://internal"})
    record.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "peer,forwarded,expected",
    [
        ("203.0.113.7", None, "203.0.113.7"),
        ("203.0.113.7", "1.1.1.1", "203.0.113.7"),  # прямому клиенту XFF не верим
        ("127.0.0.1", "198.51.100.9", "198.51.100.9"),
        ("127.0.0.1", "198.51.100.9, 10.0.0.2", "198.51.100.9"),
        ("127.0.0.1", "not-an-ip", "127.0.0.1"),
        ("127.0.0.1", None, "127.0.0.1"),
    ],
)
async def test_client_ip_used_for_rate_limit(peer, forwarded, expected):
    transport = httpx.ASGITransport(app=app, client=(peer, 50000))
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    with patch("app.main.fetch_visible_text", new_callable=AsyncMock, return_value="слово"):
        with allow_limit() as (check, _):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as proxied:
                await proxied.post("/analyze", json={"url": "http://example.com"}, headers=headers)
    check.assert_awaited_once_with(expected)


def test_favicon_is_served():
    resp = client.get("/static/favicon.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert '<link rel="icon" href="/static/favicon.svg"' in client.get("/").text
