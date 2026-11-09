import unittest
from skillsmgr.risk import risk_scan


class UnicodeAdvisoryTests(unittest.TestCase):
    def test_invisible_controls_have_escaped_explainable_evidence(self):
        findings = risk_scan({'body': 'a\u202eb\U000e0061c\u200bd'})
        findings = [f for f in findings if f['kind'] == 'unicode']
        self.assertTrue(findings)
        evidence = str(findings)
        for expected in ('U+202E', 'RIGHT-TO-LEFT OVERRIDE', 'U+E0061', 'TAG LATIN SMALL LETTER A', 'U+200B', 'ZERO WIDTH SPACE'):
            self.assertIn(expected, evidence)
        for character in ('\u202e', '\U000e0061', '\u200b'):
            self.assertNotIn(character, evidence)
        self.assertTrue(all(f['advisory'] for f in findings))

    def test_description_and_bounded_repeated_findings(self):
        findings = [f for f in risk_scan({'description': '\u202e' * 10000}) if f['kind'] == 'unicode']
        self.assertTrue(findings)
        self.assertLess(len(str(findings)), 3000)
        self.assertIn('description', str(findings))
        self.assertIn('10000', str(findings))

    def test_ordinary_unicode_is_not_flagged(self):
        self.assertFalse(any(f['kind'] == 'unicode' for f in risk_scan({'body': 'नमस्ते café 😀'})))

    def test_distinct_controls_are_bounded_and_scanning_is_read_only(self):
        original = ''.join(chr(code) for code in range(0xE0001, 0xE0080))
        record = {'body': original}
        findings = [f for f in risk_scan(record) if f['kind'] == 'unicode']
        self.assertEqual(record['body'], original)
        self.assertEqual(len(findings), 1)
        self.assertIn('additional occurrences omitted', findings[0]['evidence'])
        self.assertLess(len(findings[0]['evidence']), 3000)
        self.assertIn('does not establish safety', findings[0]['why'])
