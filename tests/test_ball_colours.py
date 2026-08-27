import unittest

from ball_colours import COLOUR_KEYS, COLOUR_NUMBERS, NUMBER_TO_COLOUR, colour_counts, colour_for_number


class BallColourTests(unittest.TestCase):
    def test_fixed_mapping_is_complete_and_uses_expected_group_sizes(self) -> None:
        self.assertEqual(set(NUMBER_TO_COLOUR), set(range(1, 50)))
        self.assertEqual({colour: len(COLOUR_NUMBERS[colour]) for colour in COLOUR_KEYS}, {"red": 17, "blue": 16, "green": 16})

    def test_known_numbers_and_composition_are_deterministic(self) -> None:
        self.assertEqual(colour_for_number(1), "red")
        self.assertEqual(colour_for_number(9), "blue")
        self.assertEqual(colour_for_number(37), "blue")
        self.assertEqual(colour_for_number(38), "green")
        self.assertEqual(colour_for_number(49), "green")
        self.assertEqual(colour_counts([1, 9, 49, 2, 10, 5]), {"red": 2, "blue": 2, "green": 2})

    def test_out_of_range_numbers_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            colour_for_number(50)
