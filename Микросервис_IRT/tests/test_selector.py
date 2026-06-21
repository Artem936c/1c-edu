"""Тесты селектора заданий и сходимости адаптивной сессии (метрика М-7)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.irt_rasch import estimate_theta
from app.selector import select_next_item


@dataclass(frozen=True)
class Item:
    id: str
    b: float
    a: float = 1.0


def test_selects_max_information_item() -> None:
    # При θ = 0 и равной дискриминативности максимум информации — у задания с b ближе к θ.
    candidates = [Item("easy", -2.0), Item("target", 0.1), Item("hard", 2.5)]
    selected, info = select_next_item(0.0, candidates)
    assert selected is not None
    assert selected.id == "target"
    assert info > 0.0


def test_discrimination_wins_when_targeted() -> None:
    candidates = [Item("low_a", 0.0, a=0.5), Item("high_a", 0.0, a=2.0)]
    selected, _ = select_next_item(0.0, candidates)
    assert selected is not None
    assert selected.id == "high_a"


def test_skips_used_items() -> None:
    candidates = [Item("a", 0.0), Item("b", 0.2)]
    selected, _ = select_next_item(0.0, candidates, used_ids=["a"])
    assert selected is not None
    assert selected.id == "b"


def test_returns_none_when_all_used() -> None:
    candidates = [Item("a", 0.0)]
    selected, info = select_next_item(0.0, candidates, used_ids=["a"])
    assert selected is None
    assert info == 0.0


def test_adaptive_session_converges(rng, simulate) -> None:
    # Банк с хорошей дискриминативностью; 15-задачная адаптивная сессия.
    n_items = 60
    test_length = 15
    bank = [
        Item(f"q{i}", b=float(rng.uniform(-3.0, 3.0)), a=float(rng.uniform(2.0, 2.6)))
        for i in range(n_items)
    ]

    true_thetas = np.linspace(-2.0, 2.0, 25)
    replications = 8

    errors = []
    for theta_true in true_thetas:
        for _ in range(replications):
            theta_hat = 0.0
            used: set[str] = set()
            history: list[tuple[float, float, bool]] = []
            for _step in range(test_length):
                item, _ = select_next_item(theta_hat, bank, used_ids=used)
                assert item is not None
                correct = bool(simulate(rng, theta_true, item.b, item.a))
                history.append((item.b, item.a, correct))
                used.add(item.id)
                theta_hat, _se = estimate_theta(history, prior_mu=0.0, prior_sigma=1.0)
            errors.append(theta_hat - theta_true)

    rmse = float(np.sqrt(np.mean(np.square(errors))))
    # Метрика М-7 (раздел 3.6 ВКР): RMSE ≤ 0.30 логит при длине теста 15 заданий.
    assert rmse <= 0.30
