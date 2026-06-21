"""Критерии остановки адаптивной сессии тестирования.

Сессия останавливается при достижении лимита заданий либо когда стандартная
ошибка оценки θ опускается до целевого порога (но не раньше минимального числа
заданий). Конфигурация 1С применяет собственные пороги из констант; ответ
микросервиса носит рекомендательный характер.
"""

from __future__ import annotations

DEFAULT_TARGET_SE = 0.30
DEFAULT_MAX_ITEMS = 20
DEFAULT_MIN_ITEMS = 5


def should_stop(
    n_items: int,
    se: float,
    target_se: float = DEFAULT_TARGET_SE,
    max_items: int = DEFAULT_MAX_ITEMS,
    min_items: int = DEFAULT_MIN_ITEMS,
) -> bool:
    """Возвращает True, если сессию пора завершить."""
    if n_items >= max_items:
        return True
    if n_items < min_items:
        return False
    return se <= target_se
