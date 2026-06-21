#!/usr/bin/env bash
# Полный прогон проверок проекта (этап 14 плана реализации).
#
# Выполняет:
#   1. Линтер микросервиса IRT (ruff)               — блокирующий;
#   2. Модульные и интеграционные тесты (pytest)    — блокирующий;
#   3. Статическую типизацию микросервиса (mypy)     — информационный;
#   4. Дымовой запуск генератора синтетических данных — блокирующий.
#
# Сценарии «1С: xUnitFor1C» (tests_1c/) запускаются вручную в информационной
# базе — см. ../tests_1c/README.md. Здесь выводится только напоминание.
#
# Запуск из каталога Конфигурация/deploy:  bash run_all_tests.sh
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KONFIG_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"
MICROSERVICE_DIR="$(cd "${KONFIG_DIR}/../Микросервис_IRT" && pwd)"
GENERATOR="${KONFIG_DIR}/fixtures/synthetic_data_generator.py"

# --- Выбор интерпретатора Python --------------------------------------------
# Приоритет: uv (рекомендуется на этой машине) → локальный .venv → системный python.
if command -v uv >/dev/null 2>&1; then
    PY=(uv run python)
    RUFF=(uv run ruff)
    MYPY=(uv run mypy)
elif [ -x "${MICROSERVICE_DIR}/.venv/Scripts/python.exe" ]; then
    PY=("${MICROSERVICE_DIR}/.venv/Scripts/python.exe")
    RUFF=("${MICROSERVICE_DIR}/.venv/Scripts/ruff.exe")
    MYPY=("${MICROSERVICE_DIR}/.venv/Scripts/mypy.exe")
elif [ -x "${MICROSERVICE_DIR}/.venv/bin/python" ]; then
    PY=("${MICROSERVICE_DIR}/.venv/bin/python")
    RUFF=("${MICROSERVICE_DIR}/.venv/bin/ruff")
    MYPY=("${MICROSERVICE_DIR}/.venv/bin/mypy")
else
    PY=(python)
    RUFF=(ruff)
    MYPY=(mypy)
fi

echo "==> Микросервис: ${MICROSERVICE_DIR}"
cd "${MICROSERVICE_DIR}"

echo "==> [1/4] ruff check"
"${RUFF[@]}" check app tests

echo "==> [2/4] pytest (модульные + интеграционные)"
"${PY[@]}" -m pytest

echo "==> [3/4] mypy app (информационно)"
if ! "${MYPY[@]}" app; then
    echo "    ВНИМАНИЕ: mypy сообщил о замечаниях типизации (не блокирует прогон)."
fi

echo "==> [4/4] Дымовой запуск генератора синтетических данных"
SMOKE_OUT="$(mktemp -d)"
"${PY[@]}" "${GENERATOR}" --n-users 20 --out "${SMOKE_OUT}"
rm -rf "${SMOKE_OUT}"

echo ""
echo "==> Готово. Автоматические проверки пройдены."
echo "    Сценарии «1С: xUnitFor1C» запустите вручную: см. ${KONFIG_DIR}/tests_1c/README.md"
