#!/usr/bin/env python3
"""產生 1,000 期模擬六合彩資料、計算特徵並以 Random Forest 生成權重快照。

執行方式：
  python3 scripts/generate_lotto_data.py --database-url "$DATABASE_URL"

程式會輸出 CSV 至 data/lotto_simulated_1000.csv，並把資料、49 個號碼統計與 5 組
推薦組合寫入資料庫。所有輸出只作統計教育及實驗用途，並非開獎預測。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import pymysql
from sklearn.ensemble import RandomForestClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CSV_PATH = DATA_DIR / "lotto_simulated_1000.csv"
MODEL_REPORT_PATH = DATA_DIR / "lotto_model_report.json"
RANDOM_SEED = 20260817
NUMBER_MIN = 1
NUMBER_MAX = 49
MAIN_COUNT = 6
WINDOW = 50


@dataclass(frozen=True)
class Draw:
    draw_no: int
    draw_date: date
    main: tuple[int, ...]
    special: int


def generate_draws(count: int, seed: int) -> list[Draw]:
    """生成具有效範圍、不重複主號與不重複特別號的模擬開獎資料。"""
    generator = random.Random(seed)
    first_date = date.today() - timedelta(days=(count - 1) * 3)
    draws: list[Draw] = []
    for draw_no in range(1, count + 1):
        values = generator.sample(range(NUMBER_MIN, NUMBER_MAX + 1), MAIN_COUNT + 1)
        main = tuple(sorted(values[:MAIN_COUNT]))
        draws.append(
            Draw(
                draw_no=draw_no,
                draw_date=first_date + timedelta(days=(draw_no - 1) * 3),
                main=main,
                special=values[MAIN_COUNT],
            )
        )
    return draws


def validate_draws(draws: list[Draw]) -> None:
    if len(draws) != 1000:
        raise ValueError("預期必須產生 1,000 期資料。")
    for draw in draws:
        values = list(draw.main) + [draw.special]
        if len(draw.main) != MAIN_COUNT or len(set(values)) != MAIN_COUNT + 1:
            raise ValueError(f"第 {draw.draw_no} 期含有重複號碼。")
        if any(value < NUMBER_MIN or value > NUMBER_MAX for value in values):
            raise ValueError(f"第 {draw.draw_no} 期含有範圍外號碼。")


def write_csv(draws: list[Draw], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "draw_no", "draw_date", "main_1", "main_2", "main_3",
                "main_4", "main_5", "main_6", "special",
            ],
        )
        writer.writeheader()
        for draw in draws:
            writer.writerow(
                {
                    "draw_no": draw.draw_no,
                    "draw_date": draw.draw_date.isoformat(),
                    **{f"main_{index + 1}": value for index, value in enumerate(draw.main)},
                    "special": draw.special,
                }
            )


def number_features(history: list[Draw], number: int) -> dict[str, int]:
    """依已知歷史資料計算指定號碼的頻率、遺漏期與特徵值。"""
    latest_window = history[-WINDOW:]
    latest_ten = history[-10:]
    frequency_50 = sum(number in draw.main for draw in latest_window)
    frequency_10 = sum(number in draw.main for draw in latest_ten)
    gap = len(history)
    for offset, draw in enumerate(reversed(history)):
        if number in draw.main:
            gap = offset
            break
    return {"frequency_50": frequency_50, "frequency_10": frequency_10, "gap": gap}


def temperature_for(frequency_50: int) -> str:
    """依近 50 期主號平均出現次數（約 6.12）標記冷熱門。"""
    if frequency_50 >= 8:
        return "熱門"
    if frequency_50 <= 4:
        return "冷門"
    return "平穩"


def make_training_data(draws: list[Draw]) -> tuple[list[list[int]], list[int]]:
    rows: list[list[int]] = []
    labels: list[int] = []
    for index in range(WINDOW, len(draws)):
        history = draws[:index]
        target_numbers = set(draws[index].main)
        for number in range(NUMBER_MIN, NUMBER_MAX + 1):
            features = number_features(history, number)
            rows.append([features["frequency_50"], features["frequency_10"], features["gap"]])
            labels.append(1 if number in target_numbers else 0)
    return rows, labels


def model_weights(draws: list[Draw]) -> tuple[dict[int, float], dict[str, Any]]:
    features, labels = make_training_data(draws)
    model = RandomForestClassifier(
        n_estimators=240,
        min_samples_leaf=12,
        max_depth=7,
        class_weight="balanced_subsample",
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    model.fit(features, labels)
    current_features = []
    for number in range(NUMBER_MIN, NUMBER_MAX + 1):
        feature = number_features(draws, number)
        current_features.append([feature["frequency_50"], feature["frequency_10"], feature["gap"]])
    probabilities = model.predict_proba(current_features)[:, 1]
    report = {
        "model": "RandomForestClassifier",
        "features": ["frequency_50", "frequency_10", "gap"],
        "training_rows": len(features),
        "positive_rate": round(sum(labels) / len(labels), 6),
        "random_seed": RANDOM_SEED,
        "note": "模型分數僅為模擬資料上的相對權重，不能可靠預測真實開獎結果。",
    }
    return {number: float(probabilities[number - 1]) for number in range(1, 50)}, report


def create_recommendations(weights: dict[int, float]) -> list[dict[str, Any]]:
    """以非均勻抽樣產生五組組合；剔除六單與六雙，且確保組合不重複。"""
    generator = random.Random(RANDOM_SEED + 71)
    population = list(range(NUMBER_MIN, NUMBER_MAX + 1))
    normalized_weights = [max(weights[number], 0.0001) for number in population]
    results: list[dict[str, Any]] = []
    seen: set[tuple[int, ...]] = set()
    attempts = 0
    while len(results) < 5 and attempts < 5000:
        attempts += 1
        remaining_numbers = population[:]
        remaining_weights = normalized_weights[:]
        selected: list[int] = []
        for _ in range(MAIN_COUNT):
            chosen = generator.choices(remaining_numbers, weights=remaining_weights, k=1)[0]
            pick_index = remaining_numbers.index(chosen)
            selected.append(chosen)
            remaining_numbers.pop(pick_index)
            remaining_weights.pop(pick_index)
        numbers = tuple(sorted(selected))
        odd_count = sum(number % 2 for number in numbers)
        if odd_count in (0, MAIN_COUNT) or numbers in seen:
            continue
        seen.add(numbers)
        consecutive_pairs = sum(right == left + 1 for left, right in zip(numbers, numbers[1:]))
        results.append(
            {
                "numbers": list(numbers),
                "odd_even": f"{odd_count} 單 / {MAIN_COUNT - odd_count} 雙",
                "number_sum": sum(numbers),
                "consecutive_pairs": consecutive_pairs,
            }
        )
    if len(results) != 5:
        raise RuntimeError("無法產生足夠的合法推薦組合。")
    return results


def database_connection(database_url: str):
    parsed = urlparse(database_url)
    if parsed.scheme not in ("mysql", "mysql+pymysql"):
        raise ValueError("DATABASE_URL 必須為 MySQL 連線字串。")
    return pymysql.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=(parsed.path or "").lstrip("/"),
        charset="utf8mb4",
        autocommit=False,
        ssl={"ssl": {}} if "ssl=true" in parsed.query.lower() else None,
    )


def persist_to_database(
    database_url: str,
    draws: list[Draw],
    weights: dict[int, float],
    recommendations: list[dict[str, Any]],
) -> None:
    connection = database_connection(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM lotto_recommendations")
            cursor.execute("DELETE FROM lotto_number_stats")
            cursor.execute("DELETE FROM lotto_draws")
            draw_rows = [
                (draw.draw_no, draw.draw_date, *draw.main, draw.special)
                for draw in draws
            ]
            cursor.executemany(
                """
                INSERT INTO lotto_draws
                (drawNo, drawDate, main1, main2, main3, main4, main5, main6, special)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                draw_rows,
            )
            stat_rows = []
            for number in range(NUMBER_MIN, NUMBER_MAX + 1):
                features = number_features(draws, number)
                stat_rows.append(
                    (
                        number,
                        features["frequency_50"],
                        features["gap"],
                        temperature_for(features["frequency_50"]),
                        round(weights[number] * 10000),
                    )
                )
            cursor.executemany(
                """
                INSERT INTO lotto_number_stats
                (number, frequency50, gap, temperature, modelWeight)
                VALUES (%s, %s, %s, %s, %s)
                """,
                stat_rows,
            )
            cursor.executemany(
                """
                INSERT INTO lotto_recommendations
                (setIndex, numbers, oddEven, numberSum, consecutivePairs)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        index,
                        json.dumps(recommendation["numbers"]),
                        recommendation["odd_even"],
                        recommendation["number_sum"],
                        recommendation["consecutive_pairs"],
                    )
                    for index, recommendation in enumerate(recommendations, start=1)
                ],
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="建立模擬六合彩分析資料集。")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--skip-db", action="store_true", help="僅輸出 CSV 與模型報告，不寫入資料庫。")
    arguments = parser.parse_args()

    draws = generate_draws(count=1000, seed=RANDOM_SEED)
    validate_draws(draws)
    write_csv(draws, CSV_PATH)
    weights, report = model_weights(draws)
    recommendations = create_recommendations(weights)
    MODEL_REPORT_PATH.write_text(
        json.dumps({"report": report, "recommendations": recommendations}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not arguments.skip_db:
        if not arguments.database_url:
            raise ValueError("未提供 DATABASE_URL；請傳入 --database-url 或使用 --skip-db。")
        persist_to_database(arguments.database_url, draws, weights, recommendations)
    print(f"已生成 {len(draws)} 期模擬資料：{CSV_PATH}")
    print(f"模型報告：{MODEL_REPORT_PATH}")


if __name__ == "__main__":
    main()
