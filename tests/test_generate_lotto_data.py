import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from generate_lotto_data import generate_draws, validate_draws


class LottoGeneratorTests(unittest.TestCase):
    def test_same_seed_produces_the_same_one_thousand_draws(self):
        first = generate_draws(1000, 20260817)
        second = generate_draws(1000, 20260817)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 1000)

    def test_every_draw_has_six_unique_main_numbers_and_one_unique_special_number(self):
        draws = generate_draws(1000, 20260817)
        validate_draws(draws)
        for draw in draws:
            values = list(draw.main) + [draw.special]
            self.assertEqual(len(draw.main), 6)
            self.assertEqual(len(set(values)), 7)
            self.assertTrue(all(1 <= value <= 49 for value in values))


if __name__ == "__main__":
    unittest.main()
