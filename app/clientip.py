import ipaddress

from fastapi import Request

from app.config import TRUSTED_PROXIES

_UNKNOWN = "unknown"


def _networks(values: tuple[str, ...]) -> list[ipaddress._BaseNetwork]:
    nets = []
    for value in values:
        try:
            nets.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            continue
    return nets


_TRUSTED = _networks(TRUSTED_PROXIES)


def _is_trusted(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in net for net in _TRUSTED)


def _valid_ip(addr: str) -> bool:
    try:
        ipaddress.ip_address(addr)
    except ValueError:
        return False
    return True


def get_client_ip(request: Request) -> str:
    """IP клиента с учётом reverse proxy.

    Прямому соединению верим как есть. Если запрос пришёл от доверенного
    прокси — идём по X-Forwarded-For справа налево и берём первый адрес,
    который не является нашим прокси. Подделанные клиентом значения при этом
    остаются левее доверенной цепочки и не влияют на результат.
    """
    peer = request.client.host if request.client else ""
    if not peer:
        return _UNKNOWN
    if not _is_trusted(peer):
        return peer

    forwarded = request.headers.get("x-forwarded-for", "")
    for candidate in reversed([p.strip() for p in forwarded.split(",") if p.strip()]):
        if not _valid_ip(candidate):
            # Мусор в заголовке — дальше по цепочке верить нечему.
            return peer
        if not _is_trusted(candidate):
            return candidate
    return peer
