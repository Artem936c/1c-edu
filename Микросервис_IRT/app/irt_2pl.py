"""Базовые функции двухпараметрической логистической модели IRT (2PL).

Однопараметрическая модель Раша (1PL) — частный случай при дискриминативности a = 1.
P(верно | θ, b, a) = 1 / (1 + exp(-a · (θ − b))).
"""

from __future__ import annotations

import math

# Граница для отсечения вероятностей от 0 и 1 (численная устойчивость логарифмов).
_EPS = 1e-12


def prob_correct(theta: float, b: float, a: float = 1.0) -> float:
    """Вероятность верного ответа по 2PL (численно устойчивый логистик)."""
    z = a * (theta - b)
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


def fisher_information(theta: float, b: float, a: float = 1.0) -> float:
    """Информация Фишера задания в точке θ: I(θ) = a² · P · (1 − P)."""
    p = prob_correct(theta, b, a)
    return a * a * p * (1.0 - p)


def clamp_prob(p: float) -> float:
    """Отсекает вероятность в (ε, 1 − ε) для безопасного взятия логарифма."""
    return min(max(p, _EPS), 1.0 - _EPS)
