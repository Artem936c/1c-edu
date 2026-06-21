"""FastAPI-приложение микросервиса IRT.

Эндпоинты, к которым обращается конфигурация 1С (общий модуль КлиентIRTСервиса):

* POST /select_next_item — выбор следующего задания по информации Фишера;
* POST /estimate_theta   — оценка θ и SE по истории ответов;
* POST /calibrate_bank   — калибровка параметров банка (JMLE/MMLE);
* GET|POST /health       — проба доступности сервиса.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .calibration import Cell, calibrate_bank
from .irt_rasch import estimate_theta
from .schemas import (
    CalibrateBankRequest,
    CalibrateBankResponse,
    EstimateThetaRequest,
    EstimateThetaResponse,
    ItemParams,
    SelectNextItemRequest,
    SelectNextItemResponse,
)
from .selector import select_next_item
from .stopping import should_stop

app = FastAPI(
    title="Микросервис IRT",
    version="0.1.0",
    description="Расчёты моделей IRT для приложения автоматизированного обучения по 1С 8.3.",
)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "irt", "status": "ok"}


@app.api_route("/health", methods=["GET", "POST"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/estimate_theta", response_model=EstimateThetaResponse)
def estimate_theta_endpoint(request: EstimateThetaRequest) -> EstimateThetaResponse:
    responses = [(item.b, item.a, item.correct) for item in request.history]
    theta, se = estimate_theta(responses, request.prior.mu, request.prior.sigma)
    n_items = len(responses)
    return EstimateThetaResponse(
        theta=theta,
        se=se,
        stop=should_stop(n_items, se),
        n_items=n_items,
    )


@app.post("/select_next_item", response_model=SelectNextItemResponse)
def select_next_item_endpoint(request: SelectNextItemRequest) -> SelectNextItemResponse:
    selected, info = select_next_item(request.theta, request.candidates, request.used_ids)
    if selected is None:
        raise HTTPException(status_code=422, detail="Нет доступных кандидатов для выбора задания.")
    return SelectNextItemResponse(selected_id=selected.id, info=info)


@app.post("/calibrate_bank", response_model=CalibrateBankResponse)
def calibrate_bank_endpoint(request: CalibrateBankRequest) -> CalibrateBankResponse:
    cells = [Cell(user=c.user, item=c.item, response=int(c.response)) for c in request.matrix]
    if not cells:
        raise HTTPException(status_code=422, detail="Пустая матрица ответов для калибровки.")
    estimates = calibrate_bank(cells, method=request.method)
    n_users = len({c.user for c in cells})
    return CalibrateBankResponse(
        new_params=[
            ItemParams(item_id=e.item_id, b=e.b, a=e.a, n=e.n) for e in estimates
        ],
        method=request.method.upper(),
        n_items=len(estimates),
        n_users=n_users,
    )
