"""Селектор следующего задания по критерию максимальной информации Фишера."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .irt_2pl import fisher_information


class HasParams(Protocol):
    """Минимальный контракт задания-кандидата: идентификатор и параметры IRT."""

    id: str
    b: float
    a: float


def select_next_item(
    theta: float,
    candidates: Iterable[HasParams],
    used_ids: Iterable[str] | None = None,
) -> tuple[HasParams | None, float]:
    """Выбирает задание с максимальной информацией Фишера в точке θ.

    Уже предъявленные задания (used_ids) исключаются. При равенстве информации
    предпочтение отдаётся первому кандидату. Возвращает (задание, информация);
    если подходящих кандидатов нет — (None, 0.0).
    """
    used = set(used_ids or ())
    best: HasParams | None = None
    best_info = -1.0
    for candidate in candidates:
        if candidate.id in used:
            continue
        info = fisher_information(theta, candidate.b, candidate.a)
        if info > best_info:
            best_info = info
            best = candidate
    return best, (best_info if best is not None else 0.0)
