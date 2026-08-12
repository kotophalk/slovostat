from unittest.mock import Mock

import pytest

from app.clientip import get_client_ip


def _request(peer, forwarded=None):
    request = Mock()
    request.client = Mock(host=peer) if peer else None
    request.headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return request


@pytest.mark.parametrize(
    "peer,forwarded,expected",
    [
        # Прямое соединение: заголовку от клиента верить нельзя.
        ("203.0.113.7", None, "203.0.113.7"),
        ("203.0.113.7", "1.1.1.1", "203.0.113.7"),
        # Запрос от доверенного прокси.
        ("127.0.0.1", "198.51.100.9", "198.51.100.9"),
        ("172.17.0.1", "198.51.100.9", "198.51.100.9"),
        # Цепочка прокси: берём последний недоверенный адрес справа.
        ("127.0.0.1", "1.1.1.1, 198.51.100.9, 10.0.0.2", "198.51.100.9"),
        # Подделка слева от реального адреса не проходит.
        ("127.0.0.1", "8.8.8.8, 198.51.100.9", "198.51.100.9"),
        # Мусор в заголовке — откатываемся на адрес прокси.
        ("127.0.0.1", "not-an-ip", "127.0.0.1"),
        ("127.0.0.1", "198.51.100.9, ерунда", "127.0.0.1"),
        ("127.0.0.1", None, "127.0.0.1"),
        # Только доверенные адреса в цепочке.
        ("127.0.0.1", "10.0.0.2", "127.0.0.1"),
    ],
)
def test_get_client_ip(peer, forwarded, expected):
    assert get_client_ip(_request(peer, forwarded)) == expected


def test_missing_client():
    assert get_client_ip(_request(None)) == "unknown"
