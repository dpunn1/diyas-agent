import io
import os
import sys
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pedia  # noqa: E402


class ScoreTests(unittest.TestCase):
    def run_score(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = pedia.main(['pedia.py', 'score'])
        return code, buf.getvalue()

    def test_last_line_is_covered_total_verdict(self):
        _, out = self.run_score()
        last = out.strip().splitlines()[-1]
        self.assertIn(' of ', last)
        self.assertIn('covered:', last)
        self.assertTrue(last.endswith('PASS') or last.endswith('below target'))

    def test_miss_lines_have_question_answer_first(self):
        _, out = self.run_score()
        misses = [l for l in out.splitlines() if l.startswith('MISS: ')]
        for line in misses:
            self.assertIn(' | answer: ', line)
            self.assertIn(' | first: ', line)

    def test_exit_code_matches_verdict(self):
        code, out = self.run_score()
        last = out.strip().splitlines()[-1]
        if last.endswith('PASS'):
            self.assertEqual(code, 0)
        else:
            self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
