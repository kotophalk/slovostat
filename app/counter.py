from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Metric:
    """Одна метрика: ключ в JSON, подпись в интерфейсе и способ подсчёта."""

    key: str
    label: str
    compute: Callable[[str], int]


# Единственное место, где описаны метрики: новая добавляется сюда — и сразу
# появляется и в ответе API, и на странице.
METRICS: tuple[Metric, ...] = (
    Metric("words", "слов", lambda text: len(text.split())),
    Metric("chars", "символов", len),
    Metric(
        "chars_no_spaces",
        "без пробелов",
        lambda text: sum(1 for c in text if not c.isspace()),
    ),
)


def count_text(text: str) -> dict[str, int]:
    """Подсчёт всех метрик для текста."""
    return {metric.key: metric.compute(text) for metric in METRICS}


def metric_labels() -> list[dict[str, str]]:
    """Описание метрик для рендера страницы."""
    return [{"key": metric.key, "label": metric.label} for metric in METRICS]
