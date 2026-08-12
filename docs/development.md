# Разработка

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Чтобы проверять сервис на локальных страницах, нужен флаг — иначе fetcher
откажется ходить на `127.0.0.1`:

```bash
SLOVOSTAT_ALLOW_PRIVATE_TARGETS=1 uvicorn app.main:app --reload
```

## Тесты

```bash
pytest                                    # весь набор
pytest tests/test_fetcher.py              # один файл
pytest -k redirect                        # по подстроке в имени
```

Сеть не используется: HTTP-клиент подменяется на `httpx.MockTransport`, а DNS —
на мок резолвера (хелпер `mock_fetch` в [`tests/test_fetcher.py`](../tests/test_fetcher.py)).
Тесты роутов патчат имена, импортированные в `app.main`, а не модули-источники.

## Как добавить метрику

Метрики описаны одним списком в [`app/counter.py`](../app/counter.py):

```python
METRICS = (
    ...,
    Metric("cyrillic", "кириллицы", lambda text: sum(1 for c in text if "а" <= c.lower() <= "я")),
)
```

Больше ничего править не нужно: ключ появится в ответе `/analyze`, а блок с
подписью — на странице (шаблон рендерит метрики по этому же списку и заполняет
их по атрибуту `data-metric`). Сетка результатов подстраивается под количество
блоков сама.

Проверить: `test_index_renders_all_metrics` в
[`tests/test_main.py`](../tests/test_main.py) пройдёт по всем метрикам реестра.

## Соглашения

- Язык проекта русский: интерфейс, тексты ошибок, комментарии, сообщения
  коммитов.
- Комментарии объясняют «почему», а не «что» — особенно там, где код выглядит
  избыточным (ручные редиректы, списание лимита до загрузки).
- Настройки не читаются из `os.environ` по месту: всё в `app/config.py`.
