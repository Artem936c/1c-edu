"""Фикстуры интеграционных тестов: HTTP-клиент и доступ к генератору данных.

TestClient FastAPI построен на httpx и поднимает приложение через ASGI без
реального сетевого порта — это и есть сквозная проверка эндпоинтов «как из 1С».
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Каталог fixtures лежит в соседнем компоненте репозитория (1C_Code/fixtures).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_GENERATOR_PATH = _REPO_ROOT / "1C_Code" / "fixtures" / "synthetic_data_generator.py"


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def sdg() -> ModuleType:
    """Импортирует модуль генератора синтетических данных по абсолютному пути."""
    if not _GENERATOR_PATH.exists():
        pytest.skip(f"Генератор синтетических данных не найден: {_GENERATOR_PATH}")
    spec = importlib.util.spec_from_file_location("synthetic_data_generator", _GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["synthetic_data_generator"] = module
    spec.loader.exec_module(module)
    return module
