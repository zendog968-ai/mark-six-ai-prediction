import unittest

from lotto_data import generate_filtered_combinations, generate_mock_data, train_fusion_model


class FullDatasetTrainingTests(unittest.TestCase):
    def test_one_thousand_draws_complete_the_training_pipeline(self):
        ranked, details, error = train_fusion_model(
            generate_mock_data(),
            random_forest_estimators=15,
            xgboost_estimators=15,
        )
        self.assertIsNone(error)
        self.assertIsNotNone(details)
        self.assertEqual(len(ranked), 49)
        self.assertIn("kmeans_cluster", details.columns)
        self.assertIn("fused_score", details.columns)
        self.assertTrue(details["kmeans_cluster"].between(0, 3).all())
        self.assertEqual(len(generate_filtered_combinations(ranked)), 5)


if __name__ == "__main__":
    unittest.main()
