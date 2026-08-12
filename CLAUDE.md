# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Команды

```bash
source .venv/bin/activate           # venv уже создан в .venv
pip install -r requirements.txt
uvicorn app.main:app --reload       # http://localhost:8000

pytest                              # весь набор (48 тестов, ~0.5 с)
pytest tests/test_fetcher.py::test_rejects_internal_addresses   # один тест
pytest -k redirect                  # по подстроке

docker build -t slovostat . && docker run -p 8000:8000 slovostat
```

Для локальной отладки на своих страницах: `SLOVOSTAT_ALLOW_PRIVATE_TARGETS=1` —
иначе fetcher откажется ходить на `127.0.0.1` и в приватные сети.

Язык проекта — русский: интерфейс, тексты ошибок, комментарии, коммиты.

## Архитектура

Один POST-роут делает всю работу; модули под ним разделены по ответственности
и почти не знают друг о друге.

```
POST /analyze
  → clientip.get_client_ip   IP клиента (X-Forwarded-For только от доверенных прокси)
  → limiter.check_limit      SQLite, скользящее окно 24 ч
  → limiter.record_request   ДО загрузки, а не после
  → fetcher.fetch_visible_text
       _check_target         схема + резолв + is_global — на каждом редиректе
       _read_limited         потоковое чтение с лимитом размера
       extract_visible_text  BeautifulSoup, кодировка по meta
  → counter.count_text       все метрики из реестра METRICS
```

Инварианты, которые легко нечаянно сломать:

- **Проверка цели — на каждом URL цепочки.** Редиректы обрабатываются вручную
  (`follow_redirects=False`), потому что `follow_redirects=True` увёл бы запрос
  на внутренний адрес в обход проверки. Не включать автоследование.
- **Лимит списывается до загрузки.** Иначе неудачные URL ничего не стоят и
  сервисом можно бесплатно перебирать чужие сайты.
- **`X-Forwarded-For` принимается только от адресов из `TRUSTED_PROXIES`.**
  При прямом соединении заголовок игнорируется — иначе лимит обходится подделкой.
- **`METRICS` в `counter.py` — единственный источник правды о метриках.** Ключи
  JSON-ответа и блоки на странице (`data-metric`) берутся оттуда же; добавление
  метрики не должно требовать правок в шаблоне.
- **Соединение с SQLite одно на процесс** (`limiter._db`), открывается в lifespan
  и лениво в тестах. Схема и индекс создаются только в `init_db`.

Остаточный риск, зафиксированный сознательно: между проверкой DNS и соединением
httpx резолвит имя заново, поэтому DNS rebinding теоретически возможен.
Закрывается только подключением к уже проверенному IP.

## Тесты

Сеть в тестах не используется. Приёмы, на которых легко споткнуться:

- Тесты `fetcher` подменяют `app.fetcher._client` (фабрика клиента с
  `httpx.MockTransport`) и `app.fetcher._resolve` — см. хелпер `mock_fetch`.
- Тесты `main` патчат импортированные в `app.main` имена (`app.main.check_limit`,
  `app.main.fetch_visible_text`), а не модули-источники.
- В starlette 0.41 у `TestClient` нет параметра `client=`. Чтобы задать IP
  клиента, нужен `httpx.ASGITransport(app=app, client=(ip, port))`.
- Значения HTTP-заголовков в httpx только ASCII — кириллица в `X-Forwarded-For`
  падает на кодировании, а не в коде приложения.
- Фикстура БД — `pytest_asyncio.fixture` с `init_db`/`close_db`: соединение
  aiosqlite привязано к event loop конкретного теста.

## Документация

`docs/architecture.md` — модули и решения, `docs/configuration.md` — переменные
окружения и правила запросов, `docs/deploy.md` — VPS и reverse proxy,
`docs/development.md` — как добавить метрику.
