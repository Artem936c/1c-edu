"""Сквозные интеграционные тесты эндпоинтов микросервиса IRT.

Проверяются контракты эндпоинтов (кириллические ключи запросов / латинские
ключи ответов) и поведение системы на синтетических данных с известным θ_true:
сходимость оценки (метрика М-7), средняя длина сессии и восстановление
параметров банка при калибровке (таблица 3.5 ВКР).
"""

from __future__ import annotations

import numpy as np

# --- Доступность и контракт --------------------------------------------------


def test_health_ok(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_estimate_theta_contract(client) -> None:
    body = {
        "ИсторияОтветов": [
            {"ТрудностьB": -1.0, "ДискриминативностьA": 1.2, "Верно": True},
            {"ТрудностьB": 0.0, "ДискриминативностьA": 1.0, "Верно": True},
            {"ТрудностьB": 1.0, "ДискриминативностьA": 1.4, "Верно": False},
        ],
        "Априор": {"Мю": 0.0, "Сигма": 1.0},
    }
    response = client.post("/estimate_theta", json=body)
    assert response.status_code == 200
    data = response.json()
    # Ответ читается конфигурацией по латинским ключам.
    assert set(data) == {"theta", "se", "stop", "n_items"}
    assert data["n_items"] == 3
    assert -6.0 <= data["theta"] <= 6.0
    assert data["se"] > 0.0


def test_estimate_theta_monotonic(client) -> None:
    """Больше верных ответов на трудные задания → выше оценка θ."""

    def theta_for(corrects: list[bool]) -> float:
        body = {
            "ИсторияОтветов": [
                {"ТрудностьB": 0.0, "ДискриминативностьA": 1.0, "Верно": c}
                for c in corrects
            ]
        }
        return client.post("/estimate_theta", json=body).json()["theta"]

    weak = theta_for([False, False, False, True])
    strong = theta_for([True, True, True, False])
    assert strong > weak


def test_estimate_theta_empty_history(client) -> None:
    response = client.post("/estimate_theta", json={"ИсторияОтветов": []})
    assert response.status_code == 200
    data = response.json()
    assert data["n_items"] == 0
    assert data["theta"] == 0.0  # априорное среднее


# --- Выбор следующего задания ------------------------------------------------


def test_select_next_item_picks_closest(client) -> None:
    body = {
        "ТекущаяТета": 0.0,
        "Кандидаты": [
            {"Идентификатор": "easy", "ТрудностьB": -2.0, "ДискриминативностьA": 1.0},
            {"Идентификатор": "target", "ТрудностьB": 0.1, "ДискриминативностьA": 1.0},
            {"Идентификатор": "hard", "ТрудностьB": 2.5, "ДискриминативностьA": 1.0},
        ],
    }
    response = client.post("/select_next_item", json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["selected_id"] == "target"
    assert data["info"] > 0.0


def test_select_next_item_excludes_used(client) -> None:
    body = {
        "ТекущаяТета": 0.0,
        "Кандидаты": [
            {"Идентификатор": "a", "ТрудностьB": 0.0, "ДискриминативностьA": 1.0},
            {"Идентификатор": "b", "ТрудностьB": 0.2, "ДискриминативностьA": 1.0},
        ],
        "ИспользованныеЗадания": ["a"],
    }
    data = client.post("/select_next_item", json=body).json()
    assert data["selected_id"] == "b"


def test_select_next_item_422_when_no_candidates(client) -> None:
    body = {
        "ТекущаяТета": 0.0,
        "Кандидаты": [
            {"Идентификатор": "a", "ТрудностьB": 0.0, "ДискриминативностьA": 1.0}
        ],
        "ИспользованныеЗадания": ["a"],
    }
    response = client.post("/select_next_item", json=body)
    assert response.status_code == 422


# --- Полная адаптивная сессия по HTTP ----------------------------------------


def _run_session_over_http(client, sdg, bank, theta_true, rng, *, respect_stop, max_items):
    """Гоняет одну адаптивную сессию, обращаясь к эндпоинтам как конфигурация 1С.

    respect_stop=False — фиксированная длина max_items (для метрики М-7);
    respect_stop=True  — сессия останавливается по флагу stop (для длины сессии).
    Возвращает (θ_hat, SE, число предъявленных заданий).
    """
    used: list[str] = []
    history: list[dict] = []
    theta_hat = 0.0
    se = 99.0
    by_id = {item.id: item for item in bank}

    for _ in range(max_items):
        select_body = {
            "ТекущаяТета": theta_hat,
            "Кандидаты": [
                {"Идентификатор": it.id, "ТрудностьB": it.b, "ДискриминативностьA": it.a}
                for it in bank
            ],
            "ИспользованныеЗадания": used,
        }
        sel = client.post("/select_next_item", json=select_body)
        if sel.status_code == 422:
            break
        item = by_id[sel.json()["selected_id"]]
        correct = bool(sdg.simulate_response(rng, theta_true, item))
        used.append(item.id)
        history.append(
            {"ТрудностьB": item.b, "ДискриминативностьA": item.a, "Верно": correct}
        )

        est = client.post("/estimate_theta", json={"ИсторияОтветов": history}).json()
        theta_hat, se, stop = est["theta"], est["se"], est["stop"]
        if respect_stop and stop:
            break

    return theta_hat, se, len(history)


def test_full_session_rmse_at_length_15(client, sdg) -> None:
    """Метрика М-7: на фиксированной длине 15 заданий RMSE оценки θ ≤ 0.30 логит.

    Сессия гоняется целиком через HTTP-эндпоинты. Сиды детерминированы
    (default_rng([...])) — тест воспроизводим и не зависит от PYTHONHASHSEED.
    """
    bank = sdg.make_synthetic_bank(
        60, np.random.default_rng(20260531), b_range=(-3.0, 3.0), a_range=(2.0, 2.6), topic="ITG"
    )

    thetas = np.linspace(-2.0, 2.0, 9)
    replications = 4
    errors: list[float] = []
    for ti, theta_true in enumerate(thetas):
        for rep in range(replications):
            rng = np.random.default_rng([20260531, ti, rep])
            theta_hat, _se, _len = _run_session_over_http(
                client, sdg, bank, float(theta_true), rng, respect_stop=False, max_items=15
            )
            errors.append(theta_hat - theta_true)

    rmse = float(np.sqrt(np.mean(np.square(errors))))
    assert rmse <= 0.30


def test_full_session_stops_within_limit(client, sdg) -> None:
    """Таблица 3.5 ВКР: средняя длина адаптивной сессии ≤ 18, потолок ≤ 20."""
    bank = sdg.make_synthetic_bank(
        60, np.random.default_rng(20260531), b_range=(-3.0, 3.0), a_range=(2.0, 2.6), topic="ITG"
    )

    thetas = np.linspace(-2.0, 2.0, 9)
    lengths: list[int] = []
    for ti, theta_true in enumerate(thetas):
        rng = np.random.default_rng([20260531, 777, ti])
        _theta, _se, length = _run_session_over_http(
            client, sdg, bank, float(theta_true), rng, respect_stop=True, max_items=20
        )
        lengths.append(length)

    assert float(np.mean(lengths)) <= 18.0
    assert max(lengths) <= 20


def test_calibrate_bank_endpoint_recovers_difficulty(client, sdg) -> None:
    """Калибровка через /calibrate_bank восстанавливает трудность заданий."""
    rng = np.random.default_rng(20260531)
    bank = sdg.make_synthetic_bank(40, rng, a_range=(0.9, 1.6), topic="CAL")
    respondents = sdg.make_respondents(200, rng)
    matrix = sdg.generate_calibration_matrix(bank, respondents, rng)

    body = {"Тема": "CAL", "Метод": "JMLE", "Матрица": matrix}
    response = client.post("/calibrate_bank", json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "JMLE"
    assert data["n_users"] == 200
    assert data["n_items"] == 40

    by_item = {p["item_id"]: p for p in data["new_params"]}
    est_b = np.array([by_item[it.id]["b"] for it in bank])
    true_b = np.array([it.b for it in bank])

    corr = float(np.corrcoef(est_b, true_b)[0, 1])
    assert corr > 0.90

    # n каждой записи равно числу испытуемых, ответивших на задание.
    assert all(p["n"] == 200 for p in data["new_params"])


def test_calibrate_bank_empty_matrix_422(client) -> None:
    response = client.post("/calibrate_bank", json={"Метод": "JMLE", "Матрица": []})
    assert response.status_code == 422
