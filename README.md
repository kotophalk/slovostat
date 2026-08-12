# SlovoStat

Подсчёт слов и символов на веб-странице по URL.

## Запуск локально

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Открыть http://localhost:8000

## Запуск в Docker

```bash
docker build -t slovostat .
docker run -p 8000:8000 slovostat
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `SLOVOSTAT_RATE_LIMIT` | 25 | Лимит запросов в день на IP |
| `SLOVOSTAT_TIMEOUT` | 10 | Таймаут загрузки страницы (сек) |
| `SLOVOSTAT_DB_PATH` | slovostat.db | Путь к SQLite базе |
| `SLOVOSTAT_MAX_PAGE_MB` | 5 | Максимальный размер страницы (МБ) |
| `SLOVOSTAT_TRUSTED_PROXIES` | localhost + приватные сети | Адреса, от которых принимается `X-Forwarded-For` |
| `SLOVOSTAT_ALLOW_PRIVATE_TARGETS` | 0 | Разрешить анализ приватных адресов (только для разработки) |

## Ограничения запросов

- Только `http://` и `https://`, только публичные адреса. Запросы к localhost,
  приватным сетям и адресам метаданных облака отклоняются (защита от SSRF).
- Не больше 5 редиректов, каждый проверяется отдельно.
- Только HTML/текст; загрузка обрывается на `SLOVOSTAT_MAX_PAGE_MB`.
- Лимит списывается и при неудачной загрузке — иначе перебор URL ничего не стоит.

За reverse proxy реальный IP берётся из `X-Forwarded-For`, но только если запрос
пришёл с адреса из `SLOVOSTAT_TRUSTED_PROXIES`. При прямом доступе заголовок
игнорируется, чтобы лимит нельзя было обойти подделкой.

## Как добавить метрику

Все метрики описаны в [`app/counter.py`](app/counter.py) в кортеже `METRICS`:

```python
METRICS = (
    ...,
    Metric("cyrillic", "кириллицы", lambda text: sum(1 for c in text if "а" <= c.lower() <= "я")),
)
```

Новая запись автоматически попадает и в ответ `/analyze`, и на страницу —
шаблон рендерит метрики по этому же списку.

## Тесты

```bash
pytest
```
