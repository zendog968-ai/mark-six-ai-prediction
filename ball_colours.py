"""六合彩 1–49 號碼球的固定紅、藍、綠顏色對照。

球色是號碼本身的固定展示屬性，而非每期攪珠會變動的資料。香港賽馬會的
六合彩 50 週年官方頁確認 49 個球分為紅、藍、綠三色，紅色 17 個、藍／綠
各 16 個。此模組將既有的固定號碼對照集中管理，並在匯入時驗證其完整性。
"""

from __future__ import annotations

from collections.abc import Iterable


COLOUR_SOURCE_URL = "https://campaigns.hkjc.com/2026-marksix/ch/funfacts"
COLOUR_MAPPING_VERSION = "marksix-fixed-colour-v1"
COLOUR_KEYS = ("red", "blue", "green")
COLOUR_LABELS = {"red": "紅色", "blue": "藍色", "green": "綠色"}
COLOUR_HEX = {"red": "#dc2626", "blue": "#2563eb", "green": "#16a34a"}

# 固定對照：紅色 17 個、藍色與綠色各 16 個。請勿從開獎結果推回球色。
COLOUR_NUMBERS = {
    "red": (1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46),
    "blue": (3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48),
    "green": (5, 6, 11, 16, 17, 21, 22, 27, 28, 32, 33, 38, 39, 43, 44, 49),
}
NUMBER_TO_COLOUR = {number: colour for colour, numbers in COLOUR_NUMBERS.items() for number in numbers}


def _validate_mapping() -> None:
    all_numbers = [number for numbers in COLOUR_NUMBERS.values() for number in numbers]
    if sorted(all_numbers) != list(range(1, 50)) or len(NUMBER_TO_COLOUR) != 49:
        raise RuntimeError("六合彩球色對照必須完整且唯一覆蓋 1 至 49。")
    if {colour: len(numbers) for colour, numbers in COLOUR_NUMBERS.items()} != {"red": 17, "blue": 16, "green": 16}:
        raise RuntimeError("六合彩球色對照的紅、藍、綠球數不符合固定 17／16／16 結構。")


_validate_mapping()


def colour_for_number(number: int) -> str:
    """返回 1–49 號碼的固定英文顏色鍵；範圍外輸入會明確拒絕。"""
    try:
        value = int(number)
    except (TypeError, ValueError) as error:
        raise ValueError("六合彩號碼必須為 1 至 49 的整數。") from error
    try:
        return NUMBER_TO_COLOUR[value]
    except KeyError as error:
        raise ValueError("六合彩號碼必須為 1 至 49 的整數。") from error


def colour_label(colour: str) -> str:
    """將內部球色鍵轉為介面使用的繁體中文名稱。"""
    try:
        return COLOUR_LABELS[colour]
    except KeyError as error:
        raise ValueError(f"不支援的球色：{colour}") from error


def colour_counts(numbers: Iterable[int]) -> dict[str, int]:
    """計算一組號碼的紅、藍、綠固定球色組成。"""
    counts = {colour: 0 for colour in COLOUR_KEYS}
    for number in numbers:
        counts[colour_for_number(int(number))] += 1
    return counts


def colour_composition_text(numbers: Iterable[int]) -> str:
    """以固定順序提供可讀的顏色組成文字。"""
    counts = colour_counts(numbers)
    return "、".join(f"{COLOUR_LABELS[colour]} {counts[colour]}" for colour in COLOUR_KEYS)
