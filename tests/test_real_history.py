from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lotto_data import REQUIRED_COLUMNS, generate_mock_data, select_data_source
from scripts.fetch_real_history import parse_lottery_hk_results


SAMPLE_HISTORY_HTML = """
<table class="_results">
  <tr><td>26/089</td><td><span class="date">15/08/2026</span></td>
  <td><ul class="balls"><li>4</li><li>16</li><li>25</li><li>27</li><li>28</li><li>33</li><li>14</li></ul></td></tr>
  <tr><td>26/088</td><td><span class="date">13/08/2026</span></td>
  <td><ul class="balls"><li>21</li><li>27</li><li>35</li><li>40</li><li>47</li><li>48</li><li>23</li></ul></td></tr>
</table>
"""


class RealHistoryTests(unittest.TestCase):
    def test_parser_extracts_valid_rows(self):
        results = parse_lottery_hk_results(SAMPLE_HISTORY_HTML, "https://example.test/2026")
        self.assertEqual([result.draw for result in results], [26089, 26088])
        self.assertEqual(results[0].date, "2026-08-15")
        self.assertEqual(results[0].main_numbers, (4, 16, 25, 27, 28, 33))
        self.assertEqual(results[0].special, 14)

    def test_default_real_history_precedes_mock_fallback(self):
        real = generate_mock_data(count=60).loc[:, REQUIRED_COLUMNS]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lotto_history_real.csv"
            real.to_csv(path, index=False)
            selected, label = select_data_source(None, path)
        pd.testing.assert_frame_equal(selected, real)
        self.assertEqual(label, "專案真實歷史 CSV")


if __name__ == "__main__":
    unittest.main()
