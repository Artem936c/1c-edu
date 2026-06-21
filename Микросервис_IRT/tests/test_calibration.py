"""Тесты калибровки банка заданий (JMLE/MMLE/Rasch)."""

from __future__ import annotations

import numpy as np

from app.calibration import Cell, calibrate_bank


def _build_cells(rng, true_b, true_a, n_users):
    """Симулирует матрицу ответов n_users × len(true_b) по 2PL."""
    thetas = rng.normal(0.0, 1.0, size=n_users)
    cells = []
    for u in range(n_users):
        for j, (b, a) in enumerate(zip(true_b, true_a, strict=True)):
            p = 1.0 / (1.0 + np.exp(-a * (thetas[u] - b)))
            resp = int(rng.random() < p)
            cells.append(Cell(user=f"u{u}", item=f"q{j}", response=resp))
    return cells


def _centered_rmse(estimated, true_values):
    est = np.asarray(estimated) - np.mean(estimated)
    tru = np.asarray(true_values) - np.mean(true_values)
    return float(np.sqrt(np.mean(np.square(est - tru))))


def _aligned_rmse(estimated, true_values):
    """RMSE восстановления после линковки шкал.

    Параметры IRT определены лишь с точностью до линейного преобразования
    латентной шкалы θ, поэтому корректная мера восстановления — RMSE остатков
    после приведения оценок к истинной шкале линейной регрессией (linking).
    """
    est = np.asarray(estimated, dtype=float)
    tru = np.asarray(true_values, dtype=float)
    design = np.vstack([est, np.ones_like(est)]).T
    slope, intercept = np.linalg.lstsq(design, tru, rcond=None)[0]
    predicted = slope * est + intercept
    return float(np.sqrt(np.mean(np.square(predicted - tru))))


def test_rasch_recovers_difficulty(rng) -> None:
    n_items = 60
    n_users = 100
    true_b = rng.uniform(-2.0, 2.0, size=n_items)
    true_a = np.ones(n_items)

    cells = _build_cells(rng, true_b, true_a, n_users)
    estimates = calibrate_bank(cells, method="RASCH")

    by_item = {e.item_id: e for e in estimates}
    est_b = [by_item[f"q{j}"].b for j in range(n_items)]

    rmse = _centered_rmse(est_b, true_b)
    corr = float(np.corrcoef(est_b, true_b)[0, 1])
    assert corr > 0.95
    assert rmse < 0.30
    assert all(e.n == n_users for e in estimates)


def test_jmle_recovers_parameters(rng) -> None:
    n_items = 60
    n_users = 120
    true_b = rng.uniform(-2.0, 2.0, size=n_items)
    true_a = rng.uniform(0.8, 1.8, size=n_items)

    cells = _build_cells(rng, true_b, true_a, n_users)
    estimates = calibrate_bank(cells, method="JMLE")

    by_item = {e.item_id: e for e in estimates}
    est_b = [by_item[f"q{j}"].b for j in range(n_items)]
    est_a = [by_item[f"q{j}"].a for j in range(n_items)]

    rmse_b = _aligned_rmse(est_b, true_b)
    corr_b = float(np.corrcoef(est_b, true_b)[0, 1])
    corr_a = float(np.corrcoef(est_a, true_a)[0, 1])

    assert corr_b > 0.90
    assert rmse_b < 0.40
    # Дискриминативность восстанавливается грубее, но согласованно по знаку тренда.
    assert corr_a > 0.30


def test_mmle_recovers_difficulty(rng) -> None:
    n_items = 40
    n_users = 250
    true_b = rng.uniform(-2.0, 2.0, size=n_items)
    true_a = rng.uniform(0.9, 1.6, size=n_items)

    cells = _build_cells(rng, true_b, true_a, n_users)
    estimates = calibrate_bank(cells, method="MMLE")

    by_item = {e.item_id: e for e in estimates}
    est_b = [by_item[f"q{j}"].b for j in range(n_items)]

    corr_b = float(np.corrcoef(est_b, true_b)[0, 1])
    rmse_b = _aligned_rmse(est_b, true_b)
    assert corr_b > 0.92
    assert rmse_b < 0.40


def test_degenerate_item_does_not_crash(rng) -> None:
    # Задание, на которое все ответили верно, и задание, на которое все ошиблись.
    cells = []
    for u in range(20):
        cells.append(Cell(user=f"u{u}", item="all_correct", response=1))
        cells.append(Cell(user=f"u{u}", item="all_wrong", response=0))
        cells.append(Cell(user=f"u{u}", item="mixed", response=u % 2))

    estimates = calibrate_bank(cells, method="JMLE")
    by_item = {e.item_id: e for e in estimates}
    # Лёгкое задание — низкая трудность, трудное — высокая.
    assert by_item["all_correct"].b < by_item["mixed"].b < by_item["all_wrong"].b
