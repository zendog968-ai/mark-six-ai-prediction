import unittest

from recommendation_strengths import recommendation_strengths, sort_recommendations_by_strength


class RecommendationStrengthTests(unittest.TestCase):
    def test_strengths_are_relative_to_strongest_valid_group(self):
        recommendations = [
            {"set_index": 1, "numbers": [1, 2, 3, 4, 5, 6]},
            {"set_index": 2, "numbers": [7, 8, 9, 10, 11, 12]},
        ]
        weights = {number: 1.0 for number in range(1, 7)} | {number: 0.8 for number in range(7, 13)}
        result = recommendation_strengths(recommendations, weights)
        self.assertEqual(result[0]["relative_strength_percent"], 100)
        self.assertEqual(result[1]["relative_strength_percent"], 80)
        self.assertEqual(result[1]["strength_label"], "相對推薦強度 80%")

    def test_sorting_places_highest_mean_fusion_score_first(self):
        groups = [[7, 8, 9, 10, 11, 12], [1, 2, 3, 4, 5, 6]]
        weights = {number: 1.0 for number in range(1, 7)} | {number: 0.5 for number in range(7, 13)}
        self.assertEqual(sort_recommendations_by_strength(groups, weights)[0], [1, 2, 3, 4, 5, 6])


if __name__ == "__main__":
    unittest.main()
