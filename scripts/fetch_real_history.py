#!/usr/bin/env python3
"""建立真實香港六合彩歷史資料 CSV。

此程式只會讀取明確白名單的公開結果頁面。每個年度最多請求一次，
輸出前會沿用應用程式的欄位、日期、期號與七個號碼合法性驗證。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lotto_data import REQUIRED_COLUMNS, validate_lotto_dataframe  # noqa: E402
from updater import DrawResult, UpdateError, fetch_html, get_latest_draw, validate_draw_result  # noqa: E402


HISTORY_SOURCE_TEMPLATE = "https://lottery.hk/en/mark-six/results/{year}"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "lotto_history_real.csv"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "data" / "lotto_history_real.metadata.json"


def parse_lottery_hk_results(html: str, source_url: str) -> list[DrawResult]:
    """從年度結果表擷取期號、日期、六個正選與特別號。"""
    soup = BeautifulSoup(html, "html.parser")
    parsed: list[DrawResult] = []
    for row in soup.select("table._results tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 3:
            continue
        draw_text = cells[0].get_text(" ", strip=True)
        date_node = cells[1].select_one("span.date")
        number_nodes = cells[2].select("ul.balls li")
        if date_node is None or not number_nodes:
            continue
        try:
            draw_parts = draw_text.split("/")
            if len(draw_parts) != 2 or not all(part.isdigit() for part in draw_parts):
                continue
            numbers = [int(node.get_text(strip=True)) for node in number_nodes]
            if len(numbers) != 7:
                continue
            result = DrawResult(
                draw=int("".join(draw_parts)),
                date=datetime.strptime(date_node.get_text(strip=True), "%d/%m/%Y").date().isoformat(),
                main_numbers=tuple(sorted(numbers[:6])),
                special=numbers[6],
                source_url=source_url,
            )
            parsed.append(validate_draw_result(result))
        except (TypeError, ValueError, UpdateError):
            continue
    return parsed


def fetch_history(years: Iterable[int]) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """低頻擷取各年度結果頁；拒絕空白、重複或未通過資料驗證的輸出。"""
    records: list[dict[str, object]] = []
    sources: list[str] = []
    for position, year in enumerate(sorted(set(int(value) for value in years))):
        source_url = HISTORY_SOURCE_TEMPLATE.format(year=year)
        if position:
            time.sleep(0.5)
        parsed = parse_lottery_hk_results(fetch_html(source_url), source_url)
        if not parsed:
            raise UpdateError(f"年度結果頁未提供可驗證資料：{source_url}")
        records.extend(result.to_record() for result in parsed)
        sources.append(source_url)

    result = validate_lotto_dataframe(pd.DataFrame(records, columns=REQUIRED_COLUMNS))
    if not result.is_valid:
        raise UpdateError("真實歷史資料未通過驗證：" + "；".join(result.errors))
    return result.data, tuple(sources)


def verify_latest_history_draw(history: pd.DataFrame) -> DrawResult:
    """將資料集中最新一期與現有主／備援單期更新器的結果交叉核對。"""
    latest = get_latest_draw()
    record = history.sort_values(["Date", "Draw"]).iloc[-1]
    expected = [int(record[f"N{index}"]) for index in range(1, 7)] + [int(record["Special"])]
    actual = list(latest.main_numbers) + [latest.special]
    if int(record["Draw"]) != latest.draw or expected != actual:
        raise UpdateError(
            "年度歷史資料最新一期與即時結果來源不一致："
            f"CSV={int(record['Draw'])}，即時來源={latest.draw}。"
        )
    return latest


def write_history(output_path: Path, metadata_path: Path, years: Iterable[int]) -> pd.DataFrame:
    history, sources = fetch_history(years)
    latest = verify_latest_history_draw(history)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(output_path, index=False)
    metadata_path.write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "purpose": "真實香港六合彩公開歷史結果；僅供統計教育與實驗用途。",
                "records": len(history),
                "start_date": str(history["Date"].min().date()),
                "end_date": str(history["Date"].max().date()),
                "latest_draw": latest.to_record(),
                "history_sources": list(sources),
                "latest_cross_check_source": latest.source_url,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return history


def main() -> None:
    parser = argparse.ArgumentParser(description="建立可驗證的香港六合彩真實歷史 CSV。")
    parser.add_argument("--years", nargs="+", type=int, default=[2025, 2026])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    args = parser.parse_args()
    history = write_history(args.output, args.metadata, args.years)
    print(
        f"已寫入 {len(history)} 期真實歷史資料："
        f"{history['Date'].min().date()} 至 {history['Date'].max().date()}。"
    )


if __name__ == "__main__":
    main()
