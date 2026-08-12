from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import httpx
import pytest

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

PUBLIC_IP = "93.184.216.34"


def _client_factory(handler):
    def factory():
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=False,
            timeout=5,
        )

    return factory


@contextmanager
def mock_fetch(handler, resolve=PUBLIC_IP):
    """Подменяет HTTP-клиент и DNS: сеть в тестах не нужна."""
    resolver = AsyncMock()
    if callable(resolve):
        resolver.side_effect = resolve
    else:
        resolver.return_value = [resolve]
    with patch("app.fetcher._client", _client_factory(handler)):
        with patch("app.fetcher._resolve", resolver):
            yield


def _html_response(body, status_code=200, content_type="text/html; charset=utf-8"):
    def handler(request):
        return httpx.Response(
            status_code, content=body, headers={"content-type": content_type}
        )

    return handler


@pytest.mark.asyncio
async def test_extracts_visible_text():
    with mock_fetch(_html_response(SAMPLE_HTML.encode())):
        result = await fetch_visible_text("http://example.com")
        assert "Привет мир" in result
        assert "Hello world" in result
        assert "var x" not in result
        assert "color: red" not in result
        assert "Enable JS" not in result


@pytest.mark.asyncio
async def test_timeout_error():
    def handler(request):
        raise httpx.TimeoutException("timeout")

    with mock_fetch(handler):
        with pytest.raises(FetchError, match="время ожидания"):
            await fetch_visible_text("http://example.com")


@pytest.mark.asyncio
async def test_http_error():
    with mock_fetch(_html_response(b"Not Found", status_code=404)):
        with pytest.raises(FetchError, match="404"):
            await fetch_visible_text("http://example.com")


@pytest.mark.asyncio
async def test_detects_cp1251_encoding():
    body = "<html><body><p>Привет мир</p></body></html>".encode("cp1251")
    handler = _html_response(body, content_type="text/html; charset=windows-1251")
    with mock_fetch(handler):
        assert "Привет мир" in await fetch_visible_text("http://example.com")


@pytest.mark.asyncio
async def test_rejects_non_http_scheme():
    with mock_fetch(_html_response(b"")):
        with pytest.raises(FetchError, match="http"):
            await fetch_visible_text("file:///etc/passwd")


@pytest.mark.asyncio
@pytest.mark.parametrize("addr", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "::1"])
async def test_rejects_internal_addresses(addr):
    with mock_fetch(_html_response(SAMPLE_HTML.encode()), resolve=addr):
        with pytest.raises(FetchError, match="внутренним"):
            await fetch_visible_text("http://internal.example.com")


@pytest.mark.asyncio
async def test_rejects_internal_address_after_redirect():
    def handler(request):
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"location": "http://intra.example.com/"})
        return httpx.Response(200, content=b"<html>secret</html>")

    def resolve(host, *args, **kwargs):
        return [PUBLIC_IP] if host == "example.com" else ["10.1.2.3"]

    with mock_fetch(handler, resolve=resolve):
        with pytest.raises(FetchError, match="внутренним"):
            await fetch_visible_text("http://example.com")


@pytest.mark.asyncio
async def test_follows_allowed_redirect():
    def handler(request):
        if request.url.path == "/":
            return httpx.Response(302, headers={"location": "/final"})
        return httpx.Response(
            200,
            content="<html><p>Итог</p></html>".encode(),
            headers={"content-type": "text/html"},
        )

    with mock_fetch(handler):
        assert "Итог" in await fetch_visible_text("http://example.com/")


@pytest.mark.asyncio
async def test_too_many_redirects():
    def handler(request):
        return httpx.Response(302, headers={"location": "/next"})

    with mock_fetch(handler):
        with pytest.raises(FetchError, match="перенаправлений"):
            await fetch_visible_text("http://example.com/")


@pytest.mark.asyncio
async def test_rejects_non_html_content_type():
    with mock_fetch(_html_response(b"%PDF-1.4", content_type="application/pdf")):
        with pytest.raises(FetchError, match="не HTML"):
            await fetch_visible_text("http://example.com/doc.pdf")


@pytest.mark.asyncio
async def test_stops_on_oversized_body():
    body = b"<html>" + b"a" * 5000 + b"</html>"
    with mock_fetch(_html_response(body)):
        with patch("app.fetcher.MAX_PAGE_BYTES", 1000):
            with pytest.raises(FetchError, match="слишком большая"):
                await fetch_visible_text("http://example.com")


@pytest.mark.asyncio
async def test_rejects_oversized_content_length_before_download():
    def handler(request):
        return httpx.Response(
            200,
            content=b"<html></html>",
            headers={"content-type": "text/html", "content-length": "999999999"},
        )

    with mock_fetch(handler):
        with pytest.raises(FetchError, match="слишком большая"):
            await fetch_visible_text("http://example.com")
