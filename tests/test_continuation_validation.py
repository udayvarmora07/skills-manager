import tempfile
import unittest
from pathlib import Path

from skillsmgr.hygiene import hygiene_report
from skillsmgr.validator import validate_text


class ContinuationValidationTests(unittest.TestCase):
    def test_mapping_compatibility_explains_portability(self):
        result = validate_text('---\nname: example\ndescription: Use this when testing.\ncompatibility:\n  platform: any\n---\nbody')
        issue = next(i for i in result.errors if i.key == 'compatibility')
        self.assertIn('mapping', issue.message)
        self.assertIn('string', issue.message)
        self.assertIn('upload', issue.message)
        self.assertIn('ignore', issue.message)

    def test_unknown_keys_one_warning_and_combined_limit(self):
        text = '---\nname: example\ndescription: "' + 'x' * 800 + '"\nwhen_to_use: "' + 'y' * 737 + '"\ncustom: value\n---\nbody'
        result = validate_text(text)
        warnings = [i for i in result.warnings if i.key == 'frontmatter']
        self.assertEqual(len(warnings), 1)
        self.assertIn('when_to_use', warnings[0].message)
        self.assertIn('custom', warnings[0].message)
        self.assertTrue(any('1536' in i.message for i in result.issues))
        result = validate_text(text.replace('y' * 737, 'y' * 736))
        self.assertFalse(any('1536' in i.message for i in result.issues))

    def test_spec_keys_have_no_unknown_warning(self):
        result = validate_text("---\nname: example\ndescription: Use this when testing.\nlicense: MIT\ncompatibility: any\nmetadata:\n  author: Example\nallowed-tools: Read\n---\nbody")
        self.assertFalse(any(i.key == 'frontmatter' for i in result.warnings))

    def test_unknown_keys_escape_bidirectional_controls(self):
        result = validate_text('---\nname: example\ndescription: Use this when testing.\n"bad\u202ekeyé": value\n---\nbody')
        warning = next(i for i in result.warnings if i.key == 'frontmatter')
        self.assertNotIn('\u202e', warning.message)
        self.assertIn('\\u202e', warning.message)
        self.assertNotIn('é', warning.message)

    def test_empty_report_and_distinct_copies(self):
        self.assertEqual(hygiene_report([], scope='all')['summary']['physical_instances'], 0)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = []
            for parent in ('one', 'two'):
                skill = root / parent / 'example'
                skill.mkdir(parents=True)
                (skill / 'SKILL.md').write_text('---\nname: example\ndescription: Use this when testing.\ncompatibility:\n  platform: any\n---\nbody')
                records.append(dict(name='example', scope=parent, path=str(skill)))
            report = hygiene_report(records, scope='all')
            self.assertEqual(report['summary']['physical_instances'], 2)
            self.assertEqual(len([f for f in report['findings'] if f['category'] == 'validation']), 2)

    def test_alias_states_and_bounded_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / 'example'
            skill.mkdir()
            (skill / 'SKILL.md').write_text('---\nname: example\ndescription: Use this when testing.\ncompatibility:\n  platform: any\n---\nbody')
            records = [dict(name='example', scope=f'{i:03}', path=str(skill), disabled=bool(i % 2), addressable=True, malformed=False, instance_state=f'state-{i}') for i in range(101)]
            report = hygiene_report(records, scope='all')
            instance = next(f for f in report['findings'] if f['category'] == 'validation')['instances'][0]
            self.assertEqual(len(instance['observations']), 100)
            self.assertEqual(instance['observations_total'], 101)
            self.assertTrue(instance['observations_truncated'])
            self.assertIs(instance['observations'][1]['disabled'], True)
            self.assertIs(instance['observations'][1]['addressable'], True)
            self.assertIs(instance['observations'][1]['malformed'], False)
            self.assertEqual(instance['observations'][1]['instance_state'], 'state-1')

    def test_aliases_visible_on_one_physical_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / 'example'
            skill.mkdir()
            (skill / 'SKILL.md').write_text('---\nname: example\ndescription: Use this when testing.\ncompatibility:\n  platform: any\n---\nbody')
            alias = root / 'alias'
            alias.symlink_to(skill, target_is_directory=True)
            records = [dict(name='example', scope='a', path=str(skill)), dict(name='example', scope='b', path=str(alias))]
            report = hygiene_report(records, scope='all')
            findings = [f for f in report['findings'] if f['category'] == 'validation']
            self.assertEqual(len(findings), 1)
            aliases = findings[0]['instances'][0]['observations']
            self.assertEqual({a['scope'] for a in aliases}, {'a', 'b'})
            self.assertEqual({a['path'] for a in aliases}, {str(skill), str(alias)})
