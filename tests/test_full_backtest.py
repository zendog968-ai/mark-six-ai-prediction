import unittest

from lotto_data import generate_mock_data, rolling_backtest


class FullBacktestTests(unittest.TestCase):
    def test_default_style_twenty_period_backtest_completes(self):
        results, error = rolling_backtest(generate_mock_data(), training_window=200, test_periods=20, random_trials=25)
        self.assertIsNone(error)
        self.assertEqual(len(results), 20)
        self.assertIn("AI Top-6 命中", results.columns)
        self.assertIn("隨機平均命中", results.columns)


if __name__ == "__main__":
    unittest.main()
