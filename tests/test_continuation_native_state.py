import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from skillsmgr.native_state import observe_native_state, observe_native_states


class NativeStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home'
        self.project = Path(self.tmp.name) / 'project'
        self.home.mkdir()
        self.project.mkdir()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def observe(self, consumer, name='deploy'):
        return observe_native_state(consumer, name, home=self.home, project=self.project)

    def test_claude_precendence_and_unknown_effective(self):
        self.write(self.home / '.claude/settings.json', {'skillOverrides': {'deploy': 'off'}, 'secret': 'hidden'})
        self.write(self.project / '.claude/settings.json', {'skillOverrides': {'deploy': 'name-only'}})
        self.write(self.project / '.claude/settings.local.json', {'skillOverrides': {'deploy': 'on'}})
        result = self.observe('claude-code')
        self.assertEqual([entry['declared'] for entry in result['sources']], ['off', 'name-only', 'on'])
        self.assertEqual(result['observed_setting'], 'on')
        self.assertEqual(result['effective_state'], 'unknown')
        self.assertNotIn('hidden', str(result))

    def test_batch_reads_each_source_once_and_later_read_is_fresh(self):
        path = self.home / '.claude/settings.json'
        self.write(path, {'skillOverrides': {'first': 'off', 'second': 'on'}})
        corrupt = self.project / '.claude/settings.json'
        corrupt.parent.mkdir(parents=True)
        corrupt.write_text('{')
        from skillsmgr import native_state
        with patch.object(native_state, '_load', wraps=native_state._load) as loader:
            states = observe_native_states('claude-code', ['first', 'second'], home=self.home, project=self.project)
            self.assertEqual(loader.call_count, 3)
        self.assertEqual(states['first']['sources'][0]['declared'], 'off')
        self.assertEqual(states['second']['sources'][0]['declared'], 'on')
        self.assertEqual(states['first']['sources'][1]['status'], 'unavailable')
        self.assertEqual(states['second']['sources'][2]['status'], 'missing')
        self.write(path, {'skillOverrides': {'first': 'on'}})
        self.assertEqual(observe_native_states('claude-code', ['first'], home=self.home, project=self.project)['first']['sources'][0]['declared'], 'on')

    def test_opencode_rules_use_last_matching_per_file(self):
        self.write(self.home / '.config/opencode/opencode.json', {'permission': {'skill': {'*': 'deny', 'dep?oy': 'ask', 'deploy': 'allow'}}})
        self.write(self.project / 'opencode.json', {'permission': {'skill': 'deny'}})
        result = self.observe('opencode')
        self.assertEqual(result['sources'][0]['declared'], 'allow')
        self.assertEqual(result['sources'][0]['matched_pattern'], 'deploy')
        self.assertEqual(result['sources'][1]['declared'], 'deny')
        self.assertNotIn('observed_setting', result)
        self.assertEqual(result['effective_state'], 'unknown')

    def test_missing_corrupt_large_and_deep_are_partial_without_secrets(self):
        path = self.home / '.claude/settings.json'
        path.parent.mkdir(parents=True)
        for data in ('{"secret":"private",', '[]', '[' * 1500 + ']' * 1500, ' ' * (1024 * 1024 + 2)):
            path.write_text(data)
            result = self.observe('claude-code')
            self.assertEqual(result['sources'][0]['status'], 'unavailable')
            self.assertTrue(result['partial'])
            self.assertEqual(result['effective_state'], 'unknown')
            self.assertNotIn('private', str(result))
        path.unlink()
        self.assertEqual(self.observe('claude-code')['sources'][0]['status'], 'missing')

    def test_invalid_values_unsupported_and_no_project(self):
        self.write(self.home / '.claude/settings.json', {'skillOverrides': {'deploy': 'secret-value'}})
        result = self.observe('claude-code')
        self.assertEqual(result['sources'][0]['status'], 'invalid')
        self.assertNotIn('secret-value', str(result))
        self.assertTrue(result['partial'])
        result = observe_native_state('codex', 'deploy', home=self.home)
        self.assertEqual(result['effective_state'], 'unknown')
        self.assertTrue(result['partial'])
        # D-1 (2026-11-07): Codex TOML is read now; with no config file the
        # observation names its source and declares nothing.
        self.assertEqual(result['sources'], [{'source': 'user', 'status': 'missing'}])
        result = observe_native_state('shared', 'deploy', home=self.home)
        self.assertEqual(result['effective_state'], 'unknown')

    def test_invalid_null_duplicate_and_fifo_are_unavailable_or_invalid(self):
        path = self.home / '.config/opencode/opencode.json'
        self.write(path, {'permission': {'skill': None}})
        self.assertEqual(self.observe('opencode')['sources'][0]['status'], 'invalid')
        path.write_text('{"permission": {}, "permission": {}}')
        self.assertEqual(self.observe('opencode')['sources'][0]['status'], 'unavailable')
        path.unlink()
        if hasattr(os, 'mkfifo'):
            os.mkfifo(path)
            self.assertEqual(self.observe('opencode')['sources'][0]['status'], 'unavailable')

    def test_glob_brackets_are_literal_and_missing_project_uncertain(self):
        self.write(self.home / '.config/opencode/opencode.json', {'permission': {'skill': {'dep[lo]y': 'deny', 'dep*': 'ask'}}})
        result = observe_native_state('opencode', 'deploy', home=self.home)
        self.assertEqual(result['sources'][0]['declared'], 'ask')
        self.assertEqual(result['sources'][1]['status'], 'unobserved')
        self.assertEqual(result['effective_state'], 'unknown')

    def test_control_characters_in_matching_rule_are_escaped(self):
        self.write(self.home / '.config/opencode/opencode.json', {'permission': {'skill': {'*\u202e\u001b': 'deny'}}})
        result = self.observe('opencode', 'deploy\u202e\u001b')
        evidence = str(result)
        self.assertNotIn('\u202e', evidence)
        self.assertNotIn('\u001b', evidence)
        self.assertIn('\\\\u202e', evidence)

    def test_large_opencode_ruleset_is_bounded(self):
        rules = {f'pattern-{n}*': 'deny' for n in range(257)}
        self.write(self.home / '.config/opencode/opencode.json', {'permission': {'skill': rules}})
        result = self.observe('opencode')
        self.assertEqual(result['sources'][0]['status'], 'unavailable')
        self.assertTrue(result['partial'])
