"""Калибровка банка заданий: оценка параметров b (трудность) и a (дискриминативность).

Реализованы два режима:

* JMLE (Joint Maximum Likelihood) — попеременная оценка способностей θ
  обучающихся и параметров заданий до сходимости. Параметры задания
  оцениваются методом L-BFGS-B (scipy.optimize.minimize).
* MMLE (Marginal Maximum Likelihood) — EM-алгоритм с интегрированием по
  скрытой θ ~ N(0, 1) на сетке Гаусса—Эрмита. Устойчив при разрежённой выборке.

Шкала θ фиксируется условием среднего θ = 0 (для JMLE) либо априорным
распределением N(0, 1) (для MMLE), что снимает неопределённость сдвига.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq, minimize

from .irt_rasch import estimate_theta

# Границы параметров заданий при оптимизации.
_A_BOUNDS = (0.2, 4.0)
_B_BOUNDS = (-5.0, 5.0)
# Минимум наблюдений на задание, при котором оцениваем дискриминативность a;
# ниже — фиксируем a = 1 (модель Раша) ради устойчивости.
_MIN_OBS_FOR_2PL = 12


@dataclass(frozen=True)
class Cell:
    """Одно наблюдение матрицы калибровки: пользователь, задание, ответ (0/1)."""

    user: str
    item: str
    response: int


@dataclass(frozen=True)
class ItemEstimate:
    """Результат калибровки одного задания."""

    item_id: str
    b: float
    a: float
    n: int


def _logistic(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _build_matrix(cells: list[Cell]) -> tuple[list[str], list[str], np.ndarray]:
    """Строит матрицу ответов R[пользователь, задание] со значениями {0, 1, NaN}."""
    users = sorted({c.user for c in cells})
    items = sorted({c.item for c in cells})
    u_index = {u: i for i, u in enumerate(users)}
    i_index = {it: j for j, it in enumerate(items)}

    matrix = np.full((len(users), len(items)), np.nan)
    for cell in cells:
        matrix[u_index[cell.user], i_index[cell.item]] = 1.0 if cell.response else 0.0
    return users, items, matrix


def _fit_b_rasch(theta: np.ndarray, y: np.ndarray) -> float:
    """Оценка трудности b в модели Раша (a = 1) через корень уравнения правдоподобия."""
    successes = float(y.sum())
    n = y.size
    if successes <= 0.0:
        return _B_BOUNDS[1]
    if successes >= n:
        return _B_BOUNDS[0]

    def score(b: float) -> float:
        return float(np.sum(_logistic(theta - b)) - successes)

    try:
        return float(brentq(score, -6.0, 6.0))
    except ValueError:
        return float(np.clip(np.mean(theta) - np.log(successes / (n - successes)), *_B_BOUNDS))


def _neg_item_loglik(params: np.ndarray, theta: np.ndarray, y: np.ndarray) -> float:
    """Отрицательный лог-правдоподобия задания (2PL) с мягкой регуляризацией."""
    a, b = params
    p = np.clip(_logistic(a * (theta - b)), 1e-9, 1.0 - 1e-9)
    loglik = float(np.sum(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))
    # Слабые априорные распределения: log a ~ N(0, 0.5), b ~ N(0, 4).
    loglik += -0.5 * (np.log(max(a, 1e-3)) / 0.5) ** 2
    loglik += -0.5 * (b / 4.0) ** 2
    return -loglik


def _fit_item_2pl(theta: np.ndarray, y: np.ndarray, a0: float, b0: float) -> tuple[float, float]:
    """Оценка (a, b) задания методом L-BFGS-B."""
    result = minimize(
        _neg_item_loglik,
        x0=np.array([a0, b0]),
        args=(theta, y),
        method="L-BFGS-B",
        bounds=[_A_BOUNDS, _B_BOUNDS],
    )
    a, b = result.x
    return float(a), float(b)


def calibrate_bank(
    cells: list[Cell],
    method: str = "JMLE",
    max_iter: int = 60,
    tol: float = 1e-3,
) -> list[ItemEstimate]:
    """Калибрует банк заданий по матрице ответов.

    method: "JMLE" | "MMLE" | "RASCH" (для RASCH дискриминативность фиксируется a = 1).
    Возвращает список оценок по каждому заданию.
    """
    if not cells:
        return []

    _users, items, matrix = _build_matrix(cells)
    method_norm = method.upper()
    if method_norm == "MMLE":
        return _calibrate_mmle(items, matrix)
    return _calibrate_jmle(items, matrix, rasch_only=method_norm == "RASCH", max_iter=max_iter, tol=tol)


def _calibrate_jmle(
    items: list[str],
    matrix: np.ndarray,
    rasch_only: bool,
    max_iter: int,
    tol: float,
) -> list[ItemEstimate]:
    n_users, n_items = matrix.shape
    theta = np.zeros(n_users)
    b = np.zeros(n_items)
    a = np.ones(n_items)

    for _ in range(max_iter):
        b_prev = b.copy()

        # Шаг 1: оценка способностей при текущих параметрах заданий.
        for u in range(n_users):
            observed = np.where(~np.isnan(matrix[u]))[0]
            if observed.size == 0:
                theta[u] = 0.0
                continue
            responses = [(float(b[j]), float(a[j]), bool(matrix[u, j])) for j in observed]
            theta[u], _ = estimate_theta(responses, prior_mu=0.0, prior_sigma=1.0)

        # Фиксация шкалы: среднее θ = 0.
        theta -= float(np.mean(theta))

        # Шаг 2: оценка параметров заданий при текущих способностях.
        for j in range(n_items):
            observed = ~np.isnan(matrix[:, j])
            theta_j = theta[observed]
            y_j = matrix[observed, j]
            if y_j.size == 0:
                continue
            if rasch_only or y_j.size < _MIN_OBS_FOR_2PL:
                a[j] = 1.0
                b[j] = _fit_b_rasch(theta_j, y_j)
            else:
                a[j], b[j] = _fit_item_2pl(theta_j, y_j, a[j], b[j])

        if float(np.max(np.abs(b - b_prev))) < tol:
            break

    counts = (~np.isnan(matrix)).sum(axis=0)
    return [
        ItemEstimate(item_id=items[j], b=float(b[j]), a=float(a[j]), n=int(counts[j]))
        for j in range(n_items)
    ]


def _calibrate_mmle(
    items: list[str],
    matrix: np.ndarray,
    n_quad: int = 21,
    max_iter: int = 80,
    tol: float = 1e-3,
) -> list[ItemEstimate]:
    """Маргинальная оценка (EM) с квадратурой Гаусса—Эрмита по θ ~ N(0, 1)."""
    n_users, n_items = matrix.shape
    nodes, raw_weights = np.polynomial.hermite_e.hermegauss(n_quad)
    weights = raw_weights / np.sqrt(2.0 * np.pi)  # нормировка к плотности N(0, 1)

    b = np.zeros(n_items)
    a = np.ones(n_items)
    mask = ~np.isnan(matrix)
    filled = np.where(mask, matrix, 0.0)

    for _ in range(max_iter):
        b_prev = b.copy()

        # E-шаг: апостериорное распределение θ по узлам квадратуры для каждого пользователя.
        # log P(node) = Σ_i [y·log p + (1−y)·log(1−p)] по наблюдённым заданиям.
        logp = np.zeros((n_users, n_quad))
        for q, node in enumerate(nodes):
            p = np.clip(_logistic(a * (node - b)), 1e-9, 1.0 - 1e-9)
            ll = filled * np.log(p) + (1.0 - filled) * np.log(1.0 - p)
            logp[:, q] = np.sum(np.where(mask, ll, 0.0), axis=1)
        logp += np.log(weights)[None, :]
        logp -= logp.max(axis=1, keepdims=True)
        posterior = np.exp(logp)
        posterior /= posterior.sum(axis=1, keepdims=True)

        # M-шаг: переоценка параметров каждого задания по ожидаемым счётчикам.
        for j in range(n_items):
            obs = mask[:, j]
            if not obs.any():
                continue
            post_j = posterior[obs]  # (n_obs, n_quad)
            y_j = matrix[obs, j]
            # Ожидаемое число предъявлений и верных ответов в каждом узле.
            n_node = post_j.sum(axis=0)
            r_node = (post_j * y_j[:, None]).sum(axis=0)

            def neg_ll(params: np.ndarray, n_node=n_node, r_node=r_node) -> float:
                aj, bj = params
                p = np.clip(_logistic(aj * (nodes - bj)), 1e-9, 1.0 - 1e-9)
                return -float(np.sum(r_node * np.log(p) + (n_node - r_node) * np.log(1.0 - p)))

            result = minimize(
                neg_ll,
                x0=np.array([a[j], b[j]]),
                method="L-BFGS-B",
                bounds=[_A_BOUNDS, _B_BOUNDS],
            )
            a[j], b[j] = result.x

        if float(np.max(np.abs(b - b_prev))) < tol:
            break

    counts = mask.sum(axis=0)
    return [
        ItemEstimate(item_id=items[j], b=float(b[j]), a=float(a[j]), n=int(counts[j]))
        for j in range(n_items)
    ]
