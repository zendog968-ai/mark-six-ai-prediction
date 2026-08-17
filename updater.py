#!/usr/bin/env python3
"""低頻更新六合彩歷史資料並輸出最新模型實驗結果。

此程式只讀取公開結果頁面，每次執行最多對每個白名單來源發出一次請求；
寫入前會驗證期號、日期、1–49 範圍與 7 個號碼的不重複性。
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import pandas as pd
import requests
from bs4 import BeautifulSoup

from lotto_data import (
    MAIN_COLUMNS,
    NUMBER_COLUMNS,
    REQUIRED_COLUMNS,
    FUSION_FEATURE_NAMES,
    FUSION_MODEL_NAME,
    generate_filtered_combinations,
    train_fusion_model,
    validate_lotto_dataframe,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_HISTORY_PATH = PROJECT_ROOT / "data" / "lotto_history_real.csv"
DEFAULT_PREDICTION_PATH = PROJECT_ROOT / "data" / "latest_prediction.json"
OFFICIAL_RESULTS_URL = "https://bet.hkjc.com/en/marksix/results"
FALLBACK_RESULTS_URL = "https://www.lotteryextreme.com/marksix/results"
REQUEST_TIMEOUT_SECONDS = 20
REQUEST_RETRIES = 2
USER_AGENT = "MarkSixDataUpdater/1.0 (+https://github.com/zendog968-ai/mark-six-ai-prediction)"
LEGACY_COLUMNS = {
    "draw_no": "Draw",
    "draw_date": "Date",
    "main_1": "N1",
    "main_2": "N2",
    "main_3": "N3",
    "main_4": "N4",
    "main_5": "N5",
    "main_6": "N6",
    "special": "Special",
}


class UpdateError(RuntimeError):
    """公開結果無法安全讀取或解析時使用。"""


@dataclass(frozen=True)
class DrawResult:
    draw: int
    date: str
    main_numbers: tuple[int, int, int, int, int, int]
    special: int
    source_url: str

    def to_record(self) -> dict[str, object]:
        return {
            "Draw": self.draw,
            "Date": self.date,
            **{f"N{index + 1}": number for index, number in enumerate(self.main_numbers)},
            "Special": self.special,
        }


def fetch_html(url: str, session: requests.Session | None = None) -> str:
    """以明確逾時、有限重試與單一識別字串取得白名單來源。"""
    client = session or requests.Session()
    last_error: Exception | None = None
    for attempt in range(REQUEST_RETRIES):
        try:
            response = client.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as error:
            last_error = error
            if attempt + 1 < REQUEST_RETRIES:
                time.sleep(1 + attempt)
    raise UpdateError(f"無法取得 {url}：{last_error}")


def parse_lotteryextreme_results(html: str, source_url: str = FALLBACK_RESULTS_URL) -> list[DrawResult]:
    """解析備援頁相鄰的期號列與號碼列；可處理來源頁未閉合的 li 標記。"""
    draw_block = re.compile(
        r"<tr\b[^>]*\bclass\s*=\s*['\"][^'\"]*\bcy\b[^'\"]*['\"][^>]*>.*?"
        r"(\d{2}/\d{2}/\d{4}).*?\((\d{2}/\d{3})\).*?</tr>\s*"
        r"<tr\b[^>]*>.*?<ul\b[^>]*\bclass\s*=\s*['\"][^'\"]*\bdisplayball\b[^'\"]*['\"][^>]*>(.*?)</ul>",
        re.IGNORECASE | re.DOTALL,
    )
    results: list[DrawResult] = []
    for date_text, draw_text, number_block in draw_block.findall(html):
        values = [int(value) for value in re.findall(r"<li\b[^>]*>\s*(\d{1,2})", number_block, re.IGNORECASE)]
        if len(values) != 7:
            continue
        results.append(
            DrawResult(
                draw=int(draw_text.replace("/", "")),
                date=datetime.strptime(date_text, "%d/%m/%Y").date().isoformat(),
                main_numbers=tuple(sorted(values[:6])),
                special=values[6],
                source_url=source_url,
            )
        )
    return results


def parse_official_results(html: str, source_url: str = OFFICIAL_RESULTS_URL) -> list[DrawResult]:
    """嘗試從官方公開頁的文字序列讀取結果；結構改變時安全地回退至備援來源。"""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    pattern = re.compile(
        r"(\d{2}/\d{3})\s+(\d{2}/\d{2}/\d{4})(?:\s+\d{2}/\d{2}/\d{4})?\s+"
        r"(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s*\+\s*(\d{1,2})"
    )
    results = []
    for match in pattern.finditer(text):
        values = [int(value) for value in match.groups()[2:]]
        results.append(
            DrawResult(
                draw=int(match.group(1).replace("/", "")),
                date=datetime.strptime(match.group(2), "%d/%m/%Y").date().isoformat(),
                main_numbers=tuple(sorted(values[:6])),
                special=values[6],
                source_url=source_url,
            )
        )
    return results


def validate_draw_result(result: DrawResult) -> DrawResult:
    """以與 Streamlit 上傳相同的核心約束檢查外部抓取結果。"""
    validation = validate_lotto_dataframe(pd.DataFrame([result.to_record()], columns=REQUIRED_COLUMNS))
    if not validation.is_valid:
        raise UpdateError("抓取的最新開獎結果未通過驗證：" + "；".join(validation.errors))
    return result


def get_latest_draw(fetcher: Callable[[str], str] = fetch_html) -> DrawResult:
    """先嘗試官方頁，無可解析結果時才查詢備援頁；任何結果都會先驗證。"""
    source_attempts = (
        (OFFICIAL_RESULTS_URL, parse_official_results),
        (FALLBACK_RESULTS_URL, parse_lotteryextreme_results),
    )
    errors = []
    for url, parser in source_attempts:
        try:
            parsed = parser(fetcher(url), url)
            if parsed:
                return validate_draw_result(parsed[0])
            errors.append(f"{url} 沒有可解析結果")
        except Exception as error:  # noqa: BLE001 - collect per-source failure without writing data
            errors.append(f"{url}：{error}")
    raise UpdateError("所有公開來源均未提供可安全寫入的結果：" + " | ".join(errors))


def load_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise UpdateError(f"找不到歷史 CSV：{path}")
    history = pd.read_csv(path)
    if set(LEGACY_COLUMNS).issubset(history.columns):
        history = history.rename(columns=LEGACY_COLUMNS)
    validation = validate_lotto_dataframe(history)
    if not validation.is_valid:
        raise UpdateError("現有歷史 CSV 未通過驗證：" + "；".join(validation.errors))
    return validation.data


def append_if_new(history: pd.DataFrame, latest: DrawResult) -> tuple[pd.DataFrame, bool]:
    """按期號及日期去重，避免排程重跑時重複附加同一期。"""
    if int(latest.draw) in set(history["Draw"].astype(int)):
        return history, False
    if pd.Timestamp(latest.date) in set(pd.to_datetime(history["Date"])):
        return history, False
    combined = pd.concat([history, pd.DataFrame([latest.to_record()])], ignore_index=True)
    validation = validate_lotto_dataframe(combined)
    if not validation.is_valid:
        raise UpdateError("合併最新結果後的 CSV 未通過驗證：" + "；".join(validation.errors))
    return validation.data, True


def build_prediction_payload(history: pd.DataFrame, latest: DrawResult, appended: bool) -> dict[str, object]:
    ranked, model_details, error = train_fusion_model(history)
    if error or ranked is None or model_details is None:
        raise UpdateError(error or "模型訓練失敗。")
    combinations = generate_filtered_combinations(ranked, n_groups=5)
    top_details = model_details.head(25)
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "purpose": "僅供統計教育與實驗用途，無法可靠預測真實開獎結果。",
        "history_records": len(history),
        "latest_draw": {**asdict(latest), "appended_to_history": appended},
        "model": {
            "name": FUSION_MODEL_NAME,
            "features": list(FUSION_FEATURE_NAMES),
            "fusion": {"random_forest_weight": 0.5, "xgboost_weight": 0.5},
            "kmeans_clusters": int(model_details["kmeans_cluster"].nunique()),
        },
        "top_weights": [
            {
                "number": int(row.number),
                "relative_weight": round(float(row.fused_score), 6),
                "random_forest_weight": round(float(row.random_forest_score), 6),
                "xgboost_weight": round(float(row.xgboost_score), 6),
                "kmeans_cluster": int(row.kmeans_cluster),
            }
            for row in top_details.itertuples(index=False)
        ],
        "top_5_recommendations": [
            {
                "set_index": index,
                "numbers": combination,
                "odd_count": sum(number % 2 for number in combination),
                "number_sum": sum(combination),
                "consecutive_pairs": sum(right == left + 1 for left, right in zip(combination, combination[1:])),
            }
            for index, combination in enumerate(combinations, start=1)
        ],
    }


def cached_prediction_matches(history: pd.DataFrame, latest: DrawResult, payload: dict[str, object]) -> bool:
    """只在快取確實對應目前歷史資料與最新期號時才避免重訓。"""
    cached_draw = payload.get("latest_draw")
    cached_model = payload.get("model")
    if not isinstance(cached_draw, dict) or not isinstance(cached_model, dict):
        return False
    try:
        return (
            int(payload.get("history_records", -1)) == len(history)
            and int(cached_draw.get("draw", -1)) == latest.draw
            and cached_model.get("name") == FUSION_MODEL_NAME
        )
    except (TypeError, ValueError):
        return False


def update(history_path: Path, output_path: Path, fetcher: Callable[[str], str] = fetch_html, dry_run: bool = False) -> dict[str, object]:
    history = load_history(history_path)
    latest = get_latest_draw(fetcher)
    updated_history, appended = append_if_new(history, latest)
    if not appended and output_path.exists() and not dry_run:
        cached_payload = json.loads(output_path.read_text(encoding="utf-8"))
        if cached_prediction_matches(updated_history, latest, cached_payload):
            cached_payload["run_appended_to_history"] = False
            return cached_payload
    payload = build_prediction_payload(updated_history, latest, appended)
    payload["run_appended_to_history"] = appended
    if not dry_run:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        updated_history.to_csv(history_path, index=False)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="更新公開六合彩結果並輸出最新模型實驗結果。")
    parser.add_argument("--history-csv", type=Path, default=DEFAULT_HISTORY_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_PREDICTION_PATH)
    parser.add_argument("--dry-run", action="store_true", help="只驗證與分析，不寫入 CSV 或 JSON。")
    args = parser.parse_args()
    result = update(args.history_csv, args.output_json, dry_run=args.dry_run)
    status = "已附加新一期" if result["run_appended_to_history"] else "沒有新一期可附加"
    print(f"{status}；已使用 {result['history_records']} 期資料產生最新實驗結果。")


if __name__ == "__main__":
    main()
