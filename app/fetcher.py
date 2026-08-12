import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import (
    ALLOW_PRIVATE_TARGETS,
    MAX_PAGE_BYTES,
    MAX_PAGE_MB,
    REQUEST_TIMEOUT,
)

REMOVE_TAGS = {"script", "style", "noscript", "head", "meta", "link", "template"}
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_CONTENT_TYPES = {"application/xhtml+xml", "application/xml"}
MAX_REDIRECTS = 5
USER_AGENT = "Mozilla/5.0 (compatible; SlovoStat/1.0)"


class FetchError(Exception):
    """Ошибка при загрузке страницы."""


def _client() -> httpx.AsyncClient:
    # Редиректы обрабатываем сами: каждый следующий URL нужно проверить.
    return httpx.AsyncClient(
        follow_redirects=False,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ru,en;q=0.8"},
    )


async def _resolve(host: str) -> list[str]:
    """Все IP-адреса хоста."""
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise FetchError("Не удалось определить адрес сайта")
    return [info[4][0] for info in infos]


def _is_public(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return ip.is_global


async def _check_target(url: str) -> None:
    """Пускаем только на публичные http(s)-адреса.

    Защита от SSRF: без неё сервис ходит по любому адресу, который дал
    пользователь, — включая localhost, внутреннюю сеть и метаданные облака.

    Остаточный риск: между проверкой и соединением httpx резолвит имя заново,
    поэтому DNS rebinding теоретически возможен. Полностью закрывается только
    подключением к уже проверенному IP.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise FetchError("Поддерживаются только ссылки http:// и https://")
    if not parsed.hostname:
        raise FetchError("Некорректная ссылка")
    if ALLOW_PRIVATE_TARGETS:
        return
    for addr in await _resolve(parsed.hostname):
        if not _is_public(addr):
            raise FetchError("Доступ к внутренним адресам запрещён")


def _check_content_type(resp: httpx.Response) -> None:
    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype and not ctype.startswith("text/") and ctype not in ALLOWED_CONTENT_TYPES:
        raise FetchError("По ссылке не HTML-страница")


def _too_big() -> FetchError:
    return FetchError(f"Страница слишком большая (больше {MAX_PAGE_MB:g} МБ)")


async def _read_limited(resp: httpx.Response) -> bytes:
    """Читает тело ответа, обрывая загрузку на лимите размера."""
    declared = resp.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_PAGE_BYTES:
        raise _too_big()

    chunks: list[bytes] = []
    total = 0
    async for chunk in resp.aiter_bytes():
        total += len(chunk)
        if total > MAX_PAGE_BYTES:
            raise _too_big()
        chunks.append(chunk)
    return b"".join(chunks)


async def _download(url: str) -> tuple[bytes, str | None]:
    try:
        async with _client() as client:
            for _ in range(MAX_REDIRECTS + 1):
                await _check_target(url)
                async with client.stream("GET", url) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise FetchError("Сервер вернул некорректный редирект")
                        url = str(resp.url.join(location))
                        continue
                    resp.raise_for_status()
                    _check_content_type(resp)
                    return await _read_limited(resp), resp.charset_encoding
        raise FetchError("Слишком много перенаправлений")
    except httpx.TimeoutException:
        raise FetchError("Превышено время ожидания")
    except httpx.HTTPStatusError as e:
        raise FetchError(f"Сервер вернул ошибку: {e.response.status_code}")
    except httpx.RequestError:
        raise FetchError("Не удалось загрузить страницу")


def extract_visible_text(body: bytes, encoding: str | None = None) -> str:
    """Видимый текст страницы. Кодировку bs4 при необходимости определит сам."""
    soup = BeautifulSoup(body, "html.parser", from_encoding=encoding)
    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


async def fetch_visible_text(url: str) -> str:
    """Загружает страницу и возвращает видимый текст."""
    body, encoding = await _download(url)
    return extract_visible_text(body, encoding)
