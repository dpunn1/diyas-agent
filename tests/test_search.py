import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pedia  # noqa: E402


class SearchTests(unittest.TestCase):
    def run_search(self, query):
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch('sys.stdin') as stdin:
            stdin.isatty.return_value = False
            code = pedia.main(['pedia.py', 'search', query])
        return code, buf.getvalue()

    def test_prints_numbered_results(self):
        code, out = self.run_search('photosynthesis')
        self.assertEqual(code, 0)
        lines = [l for l in out.splitlines() if l.strip()]
        self.assertTrue(lines[0].startswith('1. '))

    def test_respects_results_count(self):
        with open(pedia.PROFILE, encoding='utf-8') as f:
            n = json.load(f).get('results', 5)
        _, out = self.run_search('history of music')
        numbered = [l for l in out.splitlines() if l[:1].isdigit() and '. ' in l]
        self.assertLessEqual(len(numbered), n)

    def test_no_prompt_when_not_a_terminal(self):
        _, out = self.run_search('photosynthesis')
        self.assertNotIn('Read which?', out)

    def test_empty_query_prints_nothing(self):
        code, out = self.run_search('the of and')
        self.assertEqual(code, 0)
        self.assertEqual(out, '')


if __name__ == '__main__':
    unittest.main()
