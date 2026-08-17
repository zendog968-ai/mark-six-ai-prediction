import io
import unittest

import pandas as pd

from lotto_data import (
    REQUIRED_COLUMNS,
    generate_filtered_combinations,
    generate_mock_data,
    filter_history,
    read_csv_with_validation,
    rolling_backtest,
    select_data_source,
    train_random_forest,
    validate_lotto_dataframe,
)


def valid_frame():
    rows = [
        [1, "2024-01-02", 1, 5, 10, 18, 25, 49, 7],
        [2, "2024-01-05", 2, 6, 11, 19, 26, 48, 8],
    ]
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)


class UploadedCsvValidationTests(unittest.TestCase):
    def test_valid_rows_are_sorted_and_accepted(self):
        frame = valid_frame().iloc[::-1]
        result = validate_lotto_dataframe(frame)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.data["Draw"].tolist(), [1, 2])
        self.assertEqual(result.data["N1"].dtype.kind, "i")

    def test_uploaded_csv_content_is_read_and_validated(self):
        content = valid_frame().to_csv(index=False).encode("utf-8")
        result = read_csv_with_validation(io.BytesIO(content))
        self.assertTrue(result.is_valid)
        self.assertEqual(result.data["Special"].tolist(), [7, 8])

    def test_missing_columns_are_rejected(self):
        result = validate_lotto_dataframe(valid_frame().drop(columns="Special"))
        self.assertFalse(result.is_valid)
        self.assertIn("缺少必要欄位", result.errors[0])

    def test_out_of_range_and_duplicate_period_numbers_are_rejected(self):
        out_of_range = valid_frame()
        out_of_range.loc[0, "N2"] = 50
        self.assertFalse(validate_lotto_dataframe(out_of_range).is_valid)
        duplicate = valid_frame()
        duplicate.loc[0, "Special"] = duplicate.loc[0, "N1"]
        result = validate_lotto_dataframe(duplicate)
        self.assertFalse(result.is_valid)
        self.assertIn("不可重複", result.errors[0])

    def test_valid_upload_replaces_mock_data_source(self):
        uploaded = validate_lotto_dataframe(valid_frame()).data
        data, source = select_data_source(uploaded)
        self.assertEqual(source, "真實 CSV 資料")
        self.assertEqual(len(data), 2)
        mock, source = select_data_source(None)
        self.assertEqual(source, "模擬資料")
        self.assertEqual(len(mock), 1000)

    def test_mock_data_is_itself_valid(self):
        result = validate_lotto_dataframe(generate_mock_data(60))
        self.assertTrue(result.is_valid)

    def test_current_data_source_can_train_and_generate_non_extreme_combinations(self):
        ranked, error = train_random_forest(generate_mock_data(60))
        self.assertIsNone(error)
        self.assertEqual(len(ranked), 49)
        combinations = generate_filtered_combinations(ranked)
        self.assertEqual(len(combinations), 5)
        self.assertTrue(all(0 < sum(number % 2 for number in combination) < 6 for combination in combinations))

    def test_history_filter_applies_inclusive_dates_and_any_selected_number(self):
        draws = generate_mock_data(20)
        start = draws.iloc[4]["Date"].date()
        end = draws.iloc[9]["Date"].date()
        selected = int(draws.iloc[6]["N3"])
        filtered = filter_history(draws, start, end, [selected])
        self.assertTrue((filtered["Date"] >= pd.Timestamp(start)).all())
        self.assertTrue((filtered["Date"] <= pd.Timestamp(end)).all())
        self.assertTrue(filtered.loc[:, ["N1", "N2", "N3", "N4", "N5", "N6", "Special"]].isin([selected]).any(axis=1).all())

    def test_rolling_backtest_only_uses_prior_history_and_returns_comparable_metrics(self):
        draws = generate_mock_data(80)
        backtest, error = rolling_backtest(draws, training_window=60, test_periods=5, random_trials=10)
        self.assertIsNone(error)
        self.assertEqual(len(backtest), 5)
        self.assertEqual(backtest["期數"].tolist(), draws["Draw"].tail(5).tolist())
        self.assertTrue(backtest["AI Top-6 命中"].between(0, 6).all())
        self.assertTrue(backtest["隨機平均命中"].between(0, 6).all())


if __name__ == "__main__":
    unittest.main()
