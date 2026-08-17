import unittest

from lotto_data import generate_filtered_combinations, generate_mock_data, train_random_forest


class FullDatasetTrainingTests(unittest.TestCase):
    def test_one_thousand_draws_complete_the_training_pipeline(self):
        ranked, error = train_random_forest(generate_mock_data())
        self.assertIsNone(error)
        self.assertEqual(len(ranked), 49)
        self.assertEqual(len(generate_filtered_combinations(ranked)), 5)


if __name__ == "__main__":
    unittest.main()
