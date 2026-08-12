# SlovoStat

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
[![тесты](https://github.com/kotophalk/slovostat/actions/workflows/tests.yml/badge.svg)](https://github.com/kotophalk/slovostat/actions/workflows/tests.yml)
[![лицензия](https://img.shields.io/github/license/kotophalk/slovostat?color=green)](LICENSE)

Подсчёт слов и символов на веб-странице по URL. Вводишь адрес — получаешь
количество слов, символов с пробелами и без. Считается только видимый текст:
скрипты, стили и мета-теги в статистику не попадают.

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

## API

```bash
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}'
```

```json
{"words": 19, "chars": 127, "chars_no_spaces": 109}
```

Ошибки приходят как `{"error": "..."}`: `429` — превышен лимит запросов,
`422` — страницу не удалось загрузить или ссылка не разрешена.

## Документация

- [Настройки и лимиты](docs/configuration.md) — переменные окружения, какие
  ссылки принимаются, работа за reverse proxy
- [Архитектура](docs/architecture.md) — модули, поток запроса, принятые решения
- [Деплой](docs/deploy.md) — VPS, Docker, Caddy или Nginx
- [Разработка](docs/development.md) — тесты и как добавить метрику

## Тесты

```bash
pytest
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
