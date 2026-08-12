import os


def _split(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


RATE_LIMIT_PER_DAY = int(os.environ.get("SLOVOSTAT_RATE_LIMIT", "25"))
REQUEST_TIMEOUT = int(os.environ.get("SLOVOSTAT_TIMEOUT", "10"))
DATABASE_PATH = os.environ.get("SLOVOSTAT_DB_PATH", "slovostat.db")

# Максимальный размер загружаемой страницы.
MAX_PAGE_MB = float(os.environ.get("SLOVOSTAT_MAX_PAGE_MB", "5"))
MAX_PAGE_BYTES = int(MAX_PAGE_MB * 1024 * 1024)

# Адреса, от которых мы доверяем заголовку X-Forwarded-For. По умолчанию —
# localhost и приватные сети: приложение слушает только за reverse proxy.
TRUSTED_PROXIES = _split(
    os.environ.get(
        "SLOVOSTAT_TRUSTED_PROXIES",
        "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fd00::/8",
    )
)

# Разрешить запросы к приватным адресам. Только для локальной разработки:
# на публичном сервере это открывает SSRF во внутреннюю сеть.
ALLOW_PRIVATE_TARGETS = _flag(os.environ.get("SLOVOSTAT_ALLOW_PRIVATE_TARGETS", "0"))
