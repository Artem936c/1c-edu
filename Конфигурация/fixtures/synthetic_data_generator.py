"""Генератор синтетических данных для интеграционного тестирования и апробации.

Формирует ответы модельных испытуемых с заранее известными значениями θ_true
по банку тестовых заданий и сохраняет результат в JSON. Полученные наборы
используются двояко:

* интеграционными тестами микросервиса IRT (сквозная проверка эндпоинтов и
  сходимости оценок на данных с известным θ_true);
* для загрузки в тестовую информационную базу 1С при апробации (проверка
  сценариев тестирования, калибровки и обновления траектории).

Банк по умолчанию читается из реальных фикстур ``question_bank/*.json``
(параметры b и a заданий платформы 1С). Если фикстуры недоступны — банк
генерируется синтетически.

Запуск из каталога ``Конфигурация/fixtures``:

    python synthetic_data_generator.py --n-users 100 --seed 20260531 --out synthetic

Модуль также пригоден как библиотека: функции ``load_bank``,
``simulate_response``, ``generate_calibration_matrix``, ``simulate_session``
импортируются интеграционными тестами.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

# Каталоги по умолчанию относительно расположения этого файла.
FIXTURES_DIR = Path(__file__).resolve().parent
QUESTION_BANK_DIR = FIXTURES_DIR / "question_bank"
DEFAULT_OUT_DIR = FIXTURES_DIR / "synthetic"
DEFAULT_SEED = 20260531


@dataclass(frozen=True)
class Item:
    """Задание банка с истинными параметрами IRT."""

    id: str
    topic: str
    b: float
    a: float = 1.0


@dataclass(frozen=True)
class Respondent:
    """Модельный испытуемый с истинной способностью θ_true."""

    user: str
    theta_true: float


def load_bank(bank_dir: Path = QUESTION_BANK_DIR) -> list[Item]:
    """Читает банк заданий из ``question_bank/*.json``.

    Извлекает идентификатор (``код``), тему и параметры b/a каждого задания.
    Если каталог пуст или отсутствует — возвращает пустой список (вызывающая
    сторона может построить синтетический банк через ``make_synthetic_bank``).
    """
    items: list[Item] = []
    if not bank_dir.exists():
        return items
    for path in sorted(bank_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        topic = str(data.get("код_темы") or data.get("тема") or path.stem)
        for task in data.get("задания", []):
            item_id = str(task.get("код") or task.get("наименование"))
            b = float(task.get("b", 0.0))
            a = float(task.get("a", 1.0))
            items.append(Item(id=item_id, topic=topic, b=b, a=a))
    return items


def make_synthetic_bank(
    n_items: int,
    rng: np.random.Generator,
    b_range: tuple[float, float] = (-2.0, 2.0),
    a_range: tuple[float, float] = (0.8, 1.8),
    topic: str = "SYNTHETIC",
) -> list[Item]:
    """Строит синтетический банк с равномерно распределёнными b и a."""
    return [
        Item(
            id=f"{topic}-{i:03d}",
            topic=topic,
            b=float(rng.uniform(*b_range)),
            a=float(rng.uniform(*a_range)),
        )
        for i in range(n_items)
    ]


def make_respondents(
    n_users: int,
    rng: np.random.Generator,
    grid: bool = False,
) -> list[Respondent]:
    """Создаёт модельных испытуемых.

    При ``grid=True`` θ_true берётся из равномерной сетки [-2.5, 2.5]
    (детерминированное покрытие шкалы), иначе — из N(0, 1).
    """
    thetas = np.linspace(-2.5, 2.5, n_users) if grid else rng.normal(0.0, 1.0, size=n_users)
    return [Respondent(user=f"u{i:04d}", theta_true=float(t)) for i, t in enumerate(thetas)]


def prob_correct(theta: float, b: float, a: float = 1.0) -> float:
    """Вероятность верного ответа по двухпараметрической логистической модели."""
    return 1.0 / (1.0 + math.exp(-a * (theta - b)))


def simulate_response(rng: np.random.Generator, theta: float, item: Item) -> int:
    """Симулирует ответ (1 — верно, 0 — неверно) по 2PL."""
    return int(rng.random() < prob_correct(theta, item.b, item.a))


def generate_calibration_matrix(
    bank: list[Item],
    respondents: list[Respondent],
    rng: np.random.Generator,
) -> list[dict[str, object]]:
    """Полная матрица «испытуемый × задание × ответ» для калибровки банка.

    Формат ячейки совпадает с телом запроса ``/calibrate_bank`` микросервиса
    (ключи ``Пользователь``, ``Задание``, ``Ответ``).
    """
    matrix: list[dict[str, object]] = []
    for r in respondents:
        for item in bank:
            matrix.append(
                {
                    "Пользователь": r.user,
                    "Задание": item.id,
                    "Ответ": simulate_response(rng, r.theta_true, item),
                }
            )
    return matrix


def simulate_session(
    theta_true: float,
    bank: list[Item],
    rng: np.random.Generator,
    test_length: int = 15,
) -> list[dict[str, object]]:
    """Симулирует адаптивную сессию жадным выбором по информации Фишера.

    Возвращает историю в формате истории ответов ``/estimate_theta``
    (ключи ``ТрудностьB``, ``ДискриминативностьA``, ``Верно``). Логика выбора
    повторяет селектор микросервиса, чтобы данные были реалистичными без
    обращения к сервису на этапе генерации.
    """
    theta_hat = 0.0
    used: set[str] = set()
    history: list[dict[str, object]] = []
    for _ in range(min(test_length, len(bank))):
        best: Item | None = None
        best_info = -1.0
        for item in bank:
            if item.id in used:
                continue
            p = prob_correct(theta_hat, item.b, item.a)
            info = (item.a**2) * p * (1.0 - p)
            if info > best_info:
                best_info = info
                best = item
        if best is None:
            break
        correct = bool(simulate_response(rng, theta_true, best))
        history.append(
            {"ТрудностьB": best.b, "ДискриминативностьA": best.a, "Верно": correct}
        )
        used.add(best.id)
        theta_hat = _quick_theta(history)
    return history


def _quick_theta(history: list[dict[str, object]]) -> float:
    """Грубая оценка θ методом Ньютона — только для управления симуляцией."""
    theta = 0.0
    for _ in range(20):
        num = 0.0
        den = 0.0
        for h in history:
            b = float(h["ТрудностьB"])
            a = float(h["ДискриминативностьA"])
            y = 1.0 if h["Верно"] else 0.0
            p = prob_correct(theta, b, a)
            num += a * (y - p)
            den += (a**2) * p * (1.0 - p)
        if den < 1e-9:
            break
        step = num / den
        theta += step
        theta = max(-6.0, min(6.0, theta))
        if abs(step) < 1e-4:
            break
    return theta


def build_dataset(
    n_users: int,
    seed: int = DEFAULT_SEED,
    test_length: int = 15,
    grid: bool = False,
    bank_dir: Path = QUESTION_BANK_DIR,
) -> dict[str, object]:
    """Собирает полный синтетический набор: банк, испытуемые, матрица, сессии."""
    rng = np.random.default_rng(seed)
    bank = load_bank(bank_dir)
    if not bank:
        bank = make_synthetic_bank(60, rng)
    respondents = make_respondents(n_users, rng, grid=grid)

    matrix = generate_calibration_matrix(bank, respondents, rng)
    sessions = [
        {
            "Пользователь": r.user,
            "θ_true": r.theta_true,
            "ИсторияОтветов": simulate_session(r.theta_true, bank, rng, test_length),
        }
        for r in respondents
    ]

    return {
        "meta": {
            "seed": seed,
            "n_users": n_users,
            "n_items": len(bank),
            "test_length": test_length,
            "theta_grid": grid,
        },
        "bank": [asdict(i) for i in bank],
        "respondents": [asdict(r) for r in respondents],
        "calibration_matrix": matrix,
        "sessions": sessions,
    }


def write_dataset(dataset: dict[str, object], out_dir: Path) -> dict[str, Path]:
    """Сохраняет компоненты набора в отдельные JSON-файлы каталога out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "synthetic_bank.json": dataset["bank"],
        "synthetic_respondents.json": dataset["respondents"],
        "calibration_matrix.json": {
            "Тема": "SYNTHETIC",
            "Метод": "JMLE",
            "Матрица": dataset["calibration_matrix"],
        },
        "synthetic_sessions.json": dataset["sessions"],
        "dataset_meta.json": dataset["meta"],
    }
    written: dict[str, Path] = {}
    for name, payload in files.items():
        path = out_dir / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        written[name] = path
    return written


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Генератор синтетических данных IRT.")
    parser.add_argument("--n-users", type=int, default=100, help="число модельных испытуемых")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="seed ГПСЧ")
    parser.add_argument("--test-length", type=int, default=15, help="длина адаптивной сессии")
    parser.add_argument(
        "--grid",
        action="store_true",
        help="θ_true из равномерной сетки вместо N(0,1)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="каталог для сохранения JSON-файлов",
    )
    return parser.parse_args()


def main() -> None:
    # Консоль Windows по умолчанию cp1252 — переключаем вывод на UTF-8,
    # чтобы кириллические сообщения не вызывали UnicodeEncodeError.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = _parse_args()
    dataset = build_dataset(
        n_users=args.n_users,
        seed=args.seed,
        test_length=args.test_length,
        grid=args.grid,
    )
    written = write_dataset(dataset, args.out)
    meta = dataset["meta"]
    print(
        f"Сгенерировано: {meta['n_users']} испытуемых × {meta['n_items']} заданий "
        f"(seed={meta['seed']})."
    )
    for name, path in written.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
