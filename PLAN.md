# Implementation Plan — SlovoStat

## Problem Statement
Простой веб-сервис для подсчёта слов и символов на веб-странице по URL. Целевая аудитория — SEO-специалисты на российском рынке. Unix way: одна функция, но качественно.

## Requirements
- Пользователь вводит URL → получает: количество слов, символов с пробелами, символов без пробелов
- Считаем только видимый текст страницы (без скриптов, стилей, мета-тегов)
- Интерфейс на русском языке
- Rate limiting: 25 запросов/день по IP, лимит легко менять
- Хранение счётчиков — SQLite
- Архитектура позволяет добавлять новые метрики (кириллица/латиница/цифры/эмодзи) без переписывания
- Docker для деплоя, локальный запуск для разработки
- Python 3.11+, FastAPI, pip + requirements.txt

## Stack
- FastAPI + Jinja2 для рендера одной HTML-страницы
- `httpx` (async) для загрузки страниц по URL
- `beautifulsoup4` для извлечения видимого текста
- `aiosqlite` для async-доступа к SQLite (rate limiting)

## Structure
```
slovostat/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, роуты
│   ├── counter.py       # Логика подсчёта (слова, символы)
│   ├── fetcher.py       # Загрузка и парсинг страницы
│   ├── limiter.py       # Rate limiting (SQLite)
│   ├── config.py        # Настройки (лимиты, таймауты)
│   └── templates/
│       └── index.html   # Единственная страница
├── tests/
│   ├── test_counter.py
│   ├── test_fetcher.py
│   └── test_limiter.py
├── Dockerfile
├── requirements.txt
└── README.md
```

## Flow
Пользователь → URL → FastAPI → Rate Limit Check (SQLite) → если OK → Fetcher (httpx) → BeautifulSoup (извлечение текста) → Counter (подсчёт) → Результат. Если лимит превышен → 429.
