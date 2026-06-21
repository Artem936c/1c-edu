"""Оценка уровня подготовленности θ по истории ответов.

Используется метод максимального правдоподобия (MLE) для невырожденных
паттернов ответов и MAP-оценка с нормальным априорным распределением
N(μ, σ) для вырожденных (все ответы верные либо все неверные) — это не даёт
оценке уйти в ±∞. Оптимизация одномерная, выполняется методом Брента
(scipy.optimize.minimize_scalar, method="bounded").

Хотя модуль назван по модели Раша, оценщик учитывает индивидуальную
дискриминативность a каждого задания (для a = 1 получается чистая модель Раша).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from scipy.optimize import minimize_scalar

from .irt_2pl import clamp_prob, fisher_information, prob_correct

# Допустимый диапазон оценки θ в логитах и потолок стандартной ошибки.
THETA_MIN = -6.0
THETA_MAX = 6.0
SE_MAX = 99.0

# Тип элемента истории: (трудность b, дискриминативность a, верно/неверно).
Response = tuple[float, float, bool]


def log_likelihood(theta: float, responses: Sequence[Response]) -> float:
    """Логарифм правдоподобия θ при заданной истории ответов."""
    total = 0.0
    for b, a, correct in responses:
        p = clamp_prob(prob_correct(theta, b, a))
        total += math.log(p) if correct else math.log(1.0 - p)
    return total


def total_information(theta: float, responses: Sequence[Response]) -> float:
    """Суммарная информация Фишера набора заданий в точке θ."""
    return sum(fisher_information(theta, b, a) for b, a, _ in responses)


def estimate_theta(
    responses: Sequence[Response],
    prior_mu: float = 0.0,
    prior_sigma: float = 1.0,
) -> tuple[float, float]:
    """Оценивает θ и стандартную ошибку SE по истории ответов.

    Возвращает кортеж (θ, SE). При пустой истории возвращает априорное
    среднее и σ как SE. Для вырожденных паттернов применяется MAP-регуляризация.
    """
    if not responses:
        se = prior_sigma if prior_sigma and prior_sigma > 0.0 else SE_MAX
        return prior_mu, se

    corrects = [bool(c) for _, _, c in responses]
    degenerate = all(corrects) or not any(corrects)
    sigma = prior_sigma if prior_sigma and prior_sigma > 0.0 else None
    apply_prior = degenerate and sigma is not None

    def objective(theta: float) -> float:
        value = -log_likelihood(theta, responses)
        if apply_prior:
            value += 0.5 * ((theta - prior_mu) / sigma) ** 2
        return value

    result = minimize_scalar(objective, bounds=(THETA_MIN, THETA_MAX), method="bounded")
    theta_hat = float(result.x)

    info = total_information(theta_hat, responses)
    if apply_prior:
        info += 1.0 / (sigma * sigma)

    se = SE_MAX if info <= 1e-9 else min(1.0 / math.sqrt(info), SE_MAX)
    return theta_hat, se
