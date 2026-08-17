"""六合彩 CSV 驗證、資料來源與特徵工程工具。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier


REQUIRED_COLUMNS = ("Draw", "Date", "N1", "N2", "N3", "N4", "N5", "N6", "Special")
NUMBER_COLUMNS = ("N1", "N2", "N3", "N4", "N5", "N6", "Special")
MAIN_COLUMNS = ("N1", "N2", "N3", "N4", "N5", "N6")
NUMBER_MIN = 1
NUMBER_MAX = 49
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_REAL_HISTORY_PATH = PROJECT_ROOT / "data" / "lotto_history_real.csv"


@dataclass(frozen=True)
class ValidationResult:
    data: pd.DataFrame | None
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return self.data is not None and not self.errors


def read_csv_with_validation(uploaded_file) -> ValidationResult:
    """讀取 UTF-8／Big5 CSV 並執行欄位與每期號碼驗證。"""
    parsing_errors: list[str] = []
    for encoding in ("utf-8-sig", "utf-8", "big5"):
        try:
            uploaded_file.seek(0)
            return validate_lotto_dataframe(pd.read_csv(uploaded_file, encoding=encoding))
        except UnicodeDecodeError:
            parsing_errors.append(f"無法以 {encoding} 解碼")
        except pd.errors.ParserError as error:
            return ValidationResult(None, (f"CSV 解析失敗：{error}",))
    return ValidationResult(None, ("CSV 編碼不支援；請使用 UTF-8 或 Big5 格式。", *parsing_errors))


def validate_lotto_dataframe(dataframe: pd.DataFrame) -> ValidationResult:
    """驗證預期欄位、日期、號碼範圍及一期間七個號碼不重複。"""
    missing = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing:
        return ValidationResult(None, (f"缺少必要欄位：{', '.join(missing)}。",))
    if dataframe.empty:
        return ValidationResult(None, ("CSV 沒有任何開獎紀錄。",))

    working = dataframe.loc[:, REQUIRED_COLUMNS].copy()
    errors: list[str] = []
    working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
    invalid_dates = working.index[working["Date"].isna()].tolist()
    if invalid_dates:
        errors.append(f"Date 欄位包含無效日期，資料列：{_row_labels(invalid_dates)}。")

    draw_values = pd.to_numeric(working["Draw"], errors="coerce")
    invalid_draws = working.index[draw_values.isna() | (draw_values % 1 != 0)].tolist()
    if invalid_draws:
        errors.append(f"Draw 欄位必須為整數，資料列：{_row_labels(invalid_draws)}。")
    elif draw_values.duplicated().any():
        errors.append("Draw 欄位不可重複。")
    else:
        working["Draw"] = draw_values.astype(int)

    for column in NUMBER_COLUMNS:
        numbers = pd.to_numeric(working[column], errors="coerce")
        invalid = working.index[numbers.isna() | (numbers % 1 != 0) | (numbers < NUMBER_MIN) | (numbers > NUMBER_MAX)].tolist()
        if invalid:
            errors.append(f"{column} 必須是 1 到 49 的整數，資料列：{_row_labels(invalid)}。")
        else:
            working[column] = numbers.astype(int)

    if not errors:
        duplicated_rows = []
        for index, row in working.iterrows():
            values = [int(row[column]) for column in NUMBER_COLUMNS]
            if len(set(values)) != len(values):
                duplicated_rows.append(index)
        if duplicated_rows:
            errors.append(f"同一期的 6 個正選與特別號不可重複，資料列：{_row_labels(duplicated_rows)}。")

    if errors:
        return ValidationResult(None, tuple(errors))
    return ValidationResult(working.sort_values(["Date", "Draw"]).reset_index(drop=True), ())


def _row_labels(indexes: Iterable[int], limit: int = 8) -> str:
    labels = [str(index + 2) for index in list(indexes)[:limit]]
    return ", ".join(labels) + ("…" if len(list(indexes)) > limit else "")


def generate_mock_data(count: int = 1000, seed: int = 20260817) -> pd.DataFrame:
    """產生僅供介面展示的可重現模擬資料。"""
    generator = np.random.default_rng(seed)
    rows = []
    for draw in range(1, count + 1):
        values = generator.choice(np.arange(1, 50), size=7, replace=False)
        main = sorted(values[:6].tolist())
        rows.append([draw, pd.Timestamp("2018-01-01") + pd.Timedelta(days=draw * 3), *main, int(values[6])])
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)


def load_real_history(path: Path = DEFAULT_REAL_HISTORY_PATH) -> ValidationResult:
    """讀取專案內受版本控制的真實歷史 CSV，並沿用相同驗證邏輯。"""
    if not path.exists():
        return ValidationResult(None, (f"找不到真實歷史 CSV：{path.name}。",))
    try:
        return validate_lotto_dataframe(pd.read_csv(path))
    except (OSError, pd.errors.ParserError) as error:
        return ValidationResult(None, (f"無法讀取真實歷史 CSV：{error}",))


def select_data_source(
    validated_upload: pd.DataFrame | None,
    real_history_path: Path = DEFAULT_REAL_HISTORY_PATH,
) -> tuple[pd.DataFrame, str]:
    """有效上傳優先；否則預設使用真實 CSV，只在檔案有問題時回退至模擬資料。"""
    if validated_upload is not None:
        return validated_upload.copy(), "真實 CSV 資料"
    real_history = load_real_history(real_history_path)
    if real_history.is_valid:
        return real_history.data.copy(), "專案真實歷史 CSV"
    return generate_mock_data(), "模擬資料（真實歷史 CSV 不可用）"


def number_features(draws: pd.DataFrame, cutoff: int, number: int, window: int = 50) -> tuple[int, int, int]:
    history = draws.iloc[:cutoff]
    matrix = history.loc[:, MAIN_COLUMNS].to_numpy(dtype=int)
    frequency_50 = int((matrix[-window:] == number).sum())
    frequency_10 = int((matrix[-10:] == number).sum())
    gap = len(history)
    hits = np.where(matrix == number)[0]
    if len(hits):
        gap = len(history) - int(hits[-1]) - 1
    return frequency_50, frequency_10, gap


def build_training_data(draws: pd.DataFrame, window: int = 50) -> tuple[np.ndarray, np.ndarray]:
    """為每期的 49 個候選號碼建立頻率、短期頻率、Gap 與是否開出標籤。"""
    if len(draws) <= window:
        return np.empty((0, 3)), np.empty((0,))
    matrix = draws.loc[:, MAIN_COLUMNS].to_numpy(dtype=int)
    rolling_window = np.zeros(49, dtype=np.int16)
    rolling_ten = np.zeros(49, dtype=np.int16)
    last_seen = np.full(49, -1, dtype=np.int32)
    for index in range(window):
        values = matrix[index] - 1
        np.add.at(rolling_window, values, 1)
        if index >= window - 10:
            np.add.at(rolling_ten, values, 1)
        last_seen[values] = index

    rows: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    for cutoff in range(window, len(draws)):
        gaps = np.where(last_seen >= 0, cutoff - last_seen - 1, cutoff)
        rows.append(np.column_stack((rolling_window, rolling_ten, gaps)))
        target = np.zeros(49, dtype=np.int8)
        target[matrix[cutoff] - 1] = 1
        labels.append(target)

        added = matrix[cutoff] - 1
        np.add.at(rolling_window, added, 1)
        np.add.at(rolling_ten, added, 1)
        last_seen[added] = cutoff
        removed_window = matrix[cutoff - window] - 1
        np.add.at(rolling_window, removed_window, -1)
        if cutoff >= 10:
            removed_ten = matrix[cutoff - 10] - 1
            np.add.at(rolling_ten, removed_ten, -1)
    return np.vstack(rows).astype(np.float32), np.concatenate(labels).astype(np.int8)


def train_random_forest(draws: pd.DataFrame, window: int = 50, n_estimators: int = 50):
    """以目前來源資料訓練模型並輸出下期的相對分數；資料不足時回傳原因。"""
    features, labels = build_training_data(draws, window)
    if not len(features):
        return None, f"至少需要 {window + 1} 期有效資料才能建立目前的 {window} 期特徵。"
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        min_samples_leaf=16,
        max_depth=6,
        class_weight="balanced_subsample",
        random_state=20260817,
        n_jobs=-1,
    )
    model.fit(features, labels)
    current = np.asarray([number_features(draws, len(draws), number, window) for number in range(1, 50)], dtype=np.float32)
    probabilities = model.predict_proba(current)[:, 1]
    ranked = sorted(zip(range(1, 50), probabilities, strict=True), key=lambda pair: pair[1], reverse=True)
    return ranked, None


def rolling_backtest(
    draws: pd.DataFrame,
    training_window: int = 200,
    test_periods: int = 20,
    feature_window: int = 50,
    random_trials: int = 100,
    seed: int = 20260817,
) -> tuple[pd.DataFrame | None, str | None]:
    """以每一期之前可見的歷史資料重訓模型，與同一期實際開獎結果作樣本外比較。"""
    if test_periods < 1 or random_trials < 1:
        return None, "測試期數與隨機試驗次數必須大於零。"
    minimum_history = max(training_window, feature_window + 1)
    start = max(minimum_history, len(draws) - test_periods)
    if start >= len(draws):
        return None, f"至少需要 {minimum_history + 1} 期資料才能完成目前設定的滾動回測。"

    rng = np.random.default_rng(seed)
    rows = []
    for target_index in range(start, len(draws)):
        history = draws.iloc[:target_index]
        ranked, error = train_random_forest(history, window=feature_window, n_estimators=20)
        if error:
            return None, error
        ai_numbers = [number for number, _score in ranked[:6]]
        actual_numbers = draws.iloc[target_index].loc[list(MAIN_COLUMNS)].astype(int).tolist()
        actual_set = set(actual_numbers)
        ai_hits = len(set(ai_numbers) & actual_set)
        random_hits = [
            len(set(rng.choice(np.arange(1, 50), size=6, replace=False).tolist()) & actual_set)
            for _ in range(random_trials)
        ]
        row = draws.iloc[target_index]
        rows.append(
            {
                "期數": int(row["Draw"]),
                "日期": pd.Timestamp(row["Date"]),
                "AI Top-6 命中": ai_hits,
                "隨機平均命中": float(np.mean(random_hits)),
                "AI 推薦號碼": " · ".join(f"{number:02d}" for number in sorted(ai_numbers)),
                "實際正選號碼": " · ".join(f"{number:02d}" for number in sorted(actual_numbers)),
            }
        )
    return pd.DataFrame(rows), None


def filter_history(
    draws: pd.DataFrame,
    start_date,
    end_date,
    selected_numbers: Iterable[int] = (),
) -> pd.DataFrame:
    """依日期區間與『任一指定號碼』篩選；指定號碼同時涵蓋正選及特別號。"""
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    filtered = draws.loc[(draws["Date"] >= start) & (draws["Date"] <= end)].copy()
    numbers = list(selected_numbers)
    if numbers:
        filtered = filtered.loc[filtered.loc[:, NUMBER_COLUMNS].isin(numbers).any(axis=1)]
    return filtered.reset_index(drop=True)


def generate_filtered_combinations(sorted_probs, n_groups: int = 5, seed: int = 20260817):
    """以相對權重在前 25 個候選號碼內抽樣，排除 6 單／6 雙。"""
    rng = np.random.default_rng(seed)
    top_pool = [number for number, _probability in sorted_probs[:25]]
    top_weights = np.array([max(float(probability), 0.0001) for _number, probability in sorted_probs[:25]], dtype=float)
    top_weights /= top_weights.sum()
    combinations = []
    attempts = 0
    while len(combinations) < n_groups and attempts < 5000:
        attempts += 1
        combination = sorted(rng.choice(top_pool, size=6, replace=False, p=top_weights).tolist())
        odd_count = sum(number % 2 for number in combination)
        if odd_count not in (0, 6) and combination not in combinations:
            combinations.append(combination)
    if len(combinations) != n_groups:
        raise RuntimeError("無法產生足夠的合法組合。")
    return combinations
