import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pedia  # noqa: E402


class ProfileResultsTests(unittest.TestCase):
    def test_results_is_a_positive_integer(self):
        with open(pedia.PROFILE, encoding='utf-8') as f:
            results = json.load(f).get('results')
        self.assertIsInstance(results, int)
        self.assertGreater(results, 0)

    def test_load_profile_returns_results(self):
        _, results = pedia.load_profile()
        self.assertEqual(results, 5)


if __name__ == '__main__':
    unittest.main()
