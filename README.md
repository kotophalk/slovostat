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

## Тесты

```bash
pytest
```
