import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pedia  # noqa: E402

KNOWN = {
    'People', 'History', 'Geography', 'Arts', 'Philosophy and religion',
    'Everyday life', 'Society and social sciences', 'Biological and health sciences',
    'Physical sciences', 'Technology', 'Mathematics',
}


class ProfileSubjectsTests(unittest.TestCase):
    def test_subjects_is_a_list_of_known_subjects(self):
        with open(pedia.PROFILE, encoding='utf-8') as f:
            subjects = json.load(f).get('subjects')
        self.assertIsInstance(subjects, list)
        for s in subjects:
            self.assertIn(s, KNOWN)

    def test_load_profile_returns_subjects(self):
        subjects, _ = pedia.load_profile()
        self.assertIsInstance(subjects, list)
        self.assertEqual(subjects, ['Technology'])


if __name__ == '__main__':
    unittest.main()
