"""Тесты модели Раша/2PL и оценки θ."""

from __future__ import annotations

import math

import numpy as np

from app.irt_2pl import fisher_information, prob_correct
from app.irt_rasch import SE_MAX, estimate_theta


def test_prob_monotonic_in_theta() -> None:
    assert prob_correct(-2.0, 0.0) < prob_correct(0.0, 0.0) < prob_correct(2.0, 0.0)
    assert prob_correct(0.0, 0.0) == 0.5


def test_information_peaks_at_difficulty() -> None:
    # Для модели Раша (a = 1) информация максимальна при θ = b.
    at_b = fisher_information(0.0, 0.0)
    off_b = fisher_information(1.5, 0.0)
    assert at_b > off_b
    assert math.isclose(at_b, 0.25, rel_tol=1e-9)


def test_discrimination_scales_information() -> None:
    # Информация растёт как a².
    assert math.isclose(fisher_information(0.0, 0.0, a=2.0), 1.0, rel_tol=1e-9)


def test_empty_history_returns_prior() -> None:
    theta, se = estimate_theta([], prior_mu=0.3, prior_sigma=1.0)
    assert theta == 0.3
    assert se == 1.0


def test_all_correct_uses_map_and_stays_bounded() -> None:
    # Вырожденный паттерн: все ответы верные → MAP не уходит в +∞.
    responses = [(b, 1.0, True) for b in (-1.0, -0.5, 0.0, 0.5, 1.0)]
    theta, se = estimate_theta(responses, prior_mu=0.0, prior_sigma=1.0)
    assert 0.0 < theta < 6.0
    assert se < SE_MAX


def test_estimate_recovers_known_theta(rng, simulate) -> None:
    # Фиксированный тест из 40 заданий, трудности равномерно в [−2.5, 2.5].
    difficulties = np.linspace(-2.5, 2.5, 40)
    true_thetas = np.linspace(-2.0, 2.0, 41)

    errors = []
    estimates = []
    for theta_true in true_thetas:
        responses = [
            (float(b), 1.0, bool(simulate(rng, theta_true, float(b))))
            for b in difficulties
        ]
        theta_hat, se = estimate_theta(responses, prior_mu=0.0, prior_sigma=1.0)
        errors.append(theta_hat - theta_true)
        estimates.append(theta_hat)
        assert 0.0 < se < 1.0

    rmse = float(np.sqrt(np.mean(np.square(errors))))
    bias = float(np.mean(errors))
    corr = float(np.corrcoef(estimates, true_thetas)[0, 1])

    # 40 заданий модели Раша: ожидаемая SE ≈ 0.35, оценка несмещённая.
    # corr ограничен снизу шумом одной симуляции на точку (теоретический предел ≈ 0.96).
    assert rmse < 0.45
    assert abs(bias) < 0.15
    assert corr > 0.90
