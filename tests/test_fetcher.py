import pytest
import httpx
from unittest.mock import AsyncMock, patch

from app.fetcher import fetch_visible_text, FetchError


SAMPLE_HTML = """
<html>
<head><title>Test</title></head>
<body>
<script>var x = 1;</script>
<style>.a { color: red; }</style>
<noscript>Enable JS</noscript>
<p>Привет мир</p>
<div>Hello world</div>
</body>
</html>
"""


def _mock_response(text, status_code=200):
    resp = httpx.Response(status_code, text=text, request=httpx.Request("GET", "http://x"))
    return resp


@pytest.mark.asyncio
async def test_extracts_visible_text():
    with patch("app.fetcher.httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        client.get.return_value = _mock_response(SAMPLE_HTML)
        mock_cls.return_value.__aenter__.return_value = client

        result = await fetch_visible_text("http://example.com")
        assert "Привет мир" in result
        assert "Hello world" in result
        assert "var x" not in result
        assert "color: red" not in result
        assert "Enable JS" not in result


@pytest.mark.asyncio
async def test_timeout_error():
    with patch("app.fetcher.httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        client.get.side_effect = httpx.TimeoutException("timeout")
        mock_cls.return_value.__aenter__.return_value = client

        with pytest.raises(FetchError, match="время ожидания"):
            await fetch_visible_text("http://example.com")


@pytest.mark.asyncio
async def test_http_error():
    with patch("app.fetcher.httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        client.get.return_value = _mock_response("Not Found", status_code=404)
        mock_cls.return_value.__aenter__.return_value = client

        with pytest.raises(FetchError, match="404"):
            await fetch_visible_text("http://example.com")
