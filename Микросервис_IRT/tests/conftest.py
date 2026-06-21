"""Общие фикстуры и помощники для тестов микросервиса IRT."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

# Зафиксированный seed — тесты должны быть детерминированными.
SEED = 20260531


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(SEED)


@pytest.fixture
def simulate() -> Callable[[np.random.Generator, float, float, float], int]:
    """Возвращает функцию симуляции ответа по 2PL: 1 — верно, 0 — неверно."""

    def _simulate(generator: np.random.Generator, theta: float, b: float, a: float = 1.0) -> int:
        p = 1.0 / (1.0 + np.exp(-a * (theta - b)))
        return int(generator.random() < p)

    return _simulate
