import httpx
from bs4 import BeautifulSoup

from app.config import REQUEST_TIMEOUT

REMOVE_TAGS = {"script", "style", "noscript", "head", "meta", "link"}


class FetchError(Exception):
    """Ошибка при загрузке страницы."""


async def fetch_visible_text(url: str) -> str:
    """Загружает страницу и возвращает видимый текст."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
    except httpx.TimeoutException:
        raise FetchError("Превышено время ожидания")
    except httpx.HTTPStatusError as e:
        raise FetchError(f"Сервер вернул ошибку: {e.response.status_code}")
    except httpx.RequestError:
        raise FetchError("Не удалось загрузить страницу")

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())
