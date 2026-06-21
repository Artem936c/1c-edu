"""Pydantic-схемы запросов и ответов микросервиса IRT.

Конфигурация 1С сериализует структуры через ЗаписатьJSON, сохраняя имена
полей как есть — поэтому ключи входных пакетов кириллические (ИсторияОтветов,
Априор, ТекущаяТета, Кандидаты, ...). Сопоставление выполняется через alias.
Ответы конфигурация читает по латинским ключам (theta, se, selected_id) —
их и отдаём наружу.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _CyrillicInput(BaseModel):
    """База для входных схем: разрешает заполнение по alias и по имени поля."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


# --- /estimate_theta ---------------------------------------------------------


class HistoryItem(_CyrillicInput):
    b: float = Field(alias="ТрудностьB")
    # Последний элемент истории из АдаптивноеТестирование.ОбработатьОтвет
    # приходит без дискриминативности — по умолчанию 1.0 (модель Раша).
    a: float = Field(default=1.0, alias="ДискриминативностьA")
    correct: bool = Field(alias="Верно")


class Prior(_CyrillicInput):
    mu: float = Field(default=0.0, alias="Мю")
    sigma: float = Field(default=1.0, alias="Сигма")


class EstimateThetaRequest(_CyrillicInput):
    history: list[HistoryItem] = Field(default_factory=list, alias="ИсторияОтветов")
    prior: Prior = Field(default_factory=Prior, alias="Априор")


class EstimateThetaResponse(BaseModel):
    theta: float
    se: float
    stop: bool
    n_items: int


# --- /select_next_item -------------------------------------------------------


class Candidate(_CyrillicInput):
    id: str = Field(alias="Идентификатор")
    b: float = Field(alias="ТрудностьB")
    a: float = Field(default=1.0, alias="ДискриминативностьA")


class SelectNextItemRequest(_CyrillicInput):
    theta: float = Field(default=0.0, alias="ТекущаяТета")
    candidates: list[Candidate] = Field(alias="Кандидаты")
    used_ids: list[str] = Field(default_factory=list, alias="ИспользованныеЗадания")


class SelectNextItemResponse(BaseModel):
    selected_id: str
    info: float


# --- /calibrate_bank ---------------------------------------------------------


class CalibrationCell(_CyrillicInput):
    user: str = Field(alias="Пользователь")
    item: str = Field(alias="Задание")
    response: int = Field(alias="Ответ")


class CalibrateBankRequest(_CyrillicInput):
    topic: str = Field(default="", alias="Тема")
    matrix: list[CalibrationCell] = Field(alias="Матрица")
    method: str = Field(default="JMLE", alias="Метод")


class ItemParams(BaseModel):
    item_id: str
    b: float
    a: float
    n: int


class CalibrateBankResponse(BaseModel):
    new_params: list[ItemParams]
    method: str
    n_items: int
    n_users: int
