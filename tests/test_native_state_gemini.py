"""Gemini CLI native skill-switch observations (docs/34, read-only)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr import context
from skillsmgr import native_state, scopes
from skillsmgr.native_state import observe_native_state, observe_native_states

_SYSTEM_ENV = {
    'GEMINI_CLI_SYSTEM_DEFAULTS_PATH': 'system-defaults.json',
    'GEMINI_CLI_SYSTEM_SETTINGS_PATH': 'system-settings.json',
}


class GeminiNativeStateCase(unittest.TestCase):
    """Fresh HOME/project per test; the two system paths point into the tmpdir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.home = self.base / 'home'
        self.project = self.base / 'project'
        self.home.mkdir()
        self.project.mkdir()
        self.system_defaults = self.base / _SYSTEM_ENV['GEMINI_CLI_SYSTEM_DEFAULTS_PATH']
        self.system_settings = self.base / _SYSTEM_ENV['GEMINI_CLI_SYSTEM_SETTINGS_PATH']
        env = patch.dict(os.environ, {
            'GEMINI_CLI_SYSTEM_DEFAULTS_PATH': str(self.system_defaults),
            'GEMINI_CLI_SYSTEM_SETTINGS_PATH': str(self.system_settings),
        })
        env.start()
        self.addCleanup(env.stop)

    def write(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def user(self, value: object) -> None:
        self.write(self.home / '.gemini/settings.json', value)

    def observe(self, name: str = 'deploy') -> dict:
        return observe_native_state('gemini', name, home=self.home, project=self.project)

    @staticmethod
    def source(result: dict, name: str) -> dict:
        return next(entry for entry in result['sources'] if entry['source'] == name)


class GeminiDisableUnionTests(GeminiNativeStateCase):
    def test_user_list_disables(self):
        self.user({'skills': {'disabled': ['deploy']}})
        result = self.observe()
        self.assertEqual(self.source(result, 'user')['declared'], 'disabled')
        self.assertEqual(result['observed_setting'], 'disabled')
        self.assertEqual(result['effective_state'], 'unknown')
        self.assertTrue(result['partial'])

    def test_project_list_disables(self):
        self.write(self.project / '.gemini/settings.json', {'skills': {'disabled': ['deploy']}})
        result = self.observe()
        self.assertEqual(self.source(result, 'project')['declared'], 'disabled')
        self.assertEqual(result['observed_setting'], 'disabled')

    def test_system_defaults_list_disables_and_union_is_per_file(self):
        self.write(self.system_defaults, {'skills': {'disabled': ['deploy']}})
        result = self.observe('deploy')
        self.assertEqual(self.source(result, 'system-defaults')['declared'], 'disabled')
        self.assertEqual(self.source(result, 'user').get('declared'), None)
        self.assertEqual(result['observed_setting'], 'disabled')

    def test_exact_name_matching_only(self):
        self.user({'skills': {'disabled': ['Deploy', 'deploy-*', 'deploy']}})
        self.assertEqual(self.observe('deploy')['observed_setting'], 'disabled')
        self.user({'skills': {'disabled': ['Deploy', 'deploy-*']}})
        result = self.observe('deploy')
        self.assertEqual(result['observed_setting'], 'not disabled by the files read')
        self.assertNotIn('declared', self.source(result, 'user'))


class GeminiGlobalSwitchTests(GeminiNativeStateCase):
    def test_skills_enabled_false_disables_every_skill(self):
        self.user({'skills': {'enabled': False}})
        result = self.observe()
        self.assertFalse(result['skills_enabled'])
        self.assertEqual(result['observed_setting'], 'disabled')

    def test_admin_skills_disabled_disables_every_skill(self):
        self.user({'admin': {'skills': {'enabled': False}}})
        result = self.observe()
        self.assertFalse(result['admin_skills_enabled'])
        self.assertEqual(result['observed_setting'], 'disabled')

    def test_later_file_boolean_overrides_earlier(self):
        self.write(self.system_defaults, {'skills': {'enabled': False}})
        self.user({'skills': {'enabled': True}})
        result = self.observe()
        self.assertTrue(result['skills_enabled'])
        self.assertEqual(result['observed_setting'], 'not disabled by the files read')

        self.user({'skills': {'enabled': False}})
        self.assertEqual(self.observe()['observed_setting'], 'disabled')


class GeminiUnusableSourceTests(GeminiNativeStateCase):
    def test_malformed_duplicate_and_wrong_type_are_partial_and_not_claimed(self):
        user = self.home / '.gemini/settings.json'
        user.parent.mkdir(parents=True)
        cases = (
            '{',
            '{"skills": {"disabled": ["deploy"]}, "skills": {}}',
            json.dumps({'skills': {'disabled': ['deploy'], 'enabled': 'false'}}),
            json.dumps({'skills': {'disabled': 'deploy'}}),
            json.dumps({'admin': {'skills': {'enabled': 0}}}),
        )
        for text in cases:
            user.write_text(text)
            result = self.observe()
            entry = self.source(result, 'user')
            self.assertIn(entry['status'], ('unavailable', 'invalid'), text)
            self.assertNotIn('declared', entry)
            self.assertTrue(result['partial'])
            self.assertEqual(result['observed_setting'], 'not disabled by the files read')


class GeminiInputBoundsTests(GeminiNativeStateCase):
    def test_missing_files_are_fine(self):
        result = self.observe()
        self.assertEqual([entry['status'] for entry in result['sources']],
                         ['missing', 'missing', 'missing', 'missing'])
        self.assertEqual(result['observed_setting'], 'not disabled by the files read')
        self.assertEqual(result['effective_state'], 'unknown')
        self.assertTrue(result['partial'])

    def test_missing_project_context_is_unobserved(self):
        result = observe_native_state('gemini', 'deploy', home=self.home)
        self.assertEqual(self.source(result, 'project')['status'], 'unobserved')
        self.assertTrue(result['partial'])

    def test_non_regular_file_is_refused(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('mkfifo unavailable')
        user = self.home / '.gemini/settings.json'
        user.parent.mkdir(parents=True)
        os.mkfifo(user)
        self.assertEqual(self.source(self.observe(), 'user')['status'], 'unavailable')

    def test_oversize_file_is_refused(self):
        user = self.home / '.gemini/settings.json'
        user.parent.mkdir(parents=True)
        user.write_text(' ' * (native_state.MAX_CONFIG_BYTES + 2))
        self.assertEqual(self.source(self.observe(), 'user')['status'], 'unavailable')

    def test_disabled_array_is_bounded(self):
        names = [f'skill-{index}' for index in range(native_state.MAX_GEMINI_DISABLED + 1)]
        self.user({'skills': {'disabled': names}})
        result = self.observe('skill-0')
        self.assertEqual(self.source(result, 'user')['status'], 'unavailable')
        self.assertEqual(result['observed_setting'], 'not disabled by the files read')

    def test_each_file_is_loaded_once_per_batch(self):
        self.user({'skills': {'disabled': ['one']}})
        with patch.object(native_state, '_load', wraps=native_state._load) as loader:
            states = observe_native_states('gemini', ['one', 'two'],
                                           home=self.home, project=self.project)
        self.assertEqual(loader.call_count, 4)
        self.assertEqual(states['one']['observed_setting'], 'disabled')
        self.assertEqual(states['two']['observed_setting'],
                         'not disabled by the files read')

    def test_observation_writes_nothing(self):
        self.user({'skills': {'disabled': ['deploy']}})
        self.write(self.project / '.gemini/settings.json', {'skills': {'enabled': True}})

        def snapshot():
            return sorted(
                (path.relative_to(self.base).as_posix(), path.read_bytes())
                for path in self.base.rglob('*') if path.is_file()
            )

        before = snapshot()
        observe_native_states('gemini', ['deploy', 'other'],
                              home=self.home, project=self.project)
        self.assertEqual(snapshot(), before)


class GeminiScopeAttachmentTests(unittest.TestCase):
    """The scope layer attaches Gemini evidence only to Gemini-scope rows."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.home = base / 'home'
        self.project = base / 'project'
        self.home.mkdir()
        self.project.mkdir()
        self.system_defaults = base / 'system-defaults.json'
        self.system_settings = base / 'system-settings.json'
        env = patch.dict(os.environ, {
            'HOME': str(self.home),
            'SKILLS_MANAGER_DATA': str(base / 'data'),
            'GEMINI_CLI_SYSTEM_DEFAULTS_PATH': str(self.system_defaults),
            'GEMINI_CLI_SYSTEM_SETTINGS_PATH': str(self.system_settings),
        })
        env.start()
        self.addCleanup(env.stop)
        cwd = patch.object(scopes, '_cwd', lambda: self.project)
        cwd.start()
        self.addCleanup(cwd.stop)
        context.set_active_store(None)
        self.addCleanup(context.set_active_store, None)

    @staticmethod
    def skill(directory: Path, name: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'SKILL.md').write_text(
            f'---\nname: {name}\ndescription: A skill for tests.\n---\nbody\n',
            encoding='utf-8',
        )

    def test_gemini_row_gets_observation_and_claude_row_is_unchanged(self):
        self.skill(self.home / '.gemini/skills/gem-scout', 'gem-scout')
        self.skill(self.home / '.claude/skills/claude-scout', 'claude-scout')
        self.skill(self.home / '.gemini/skills/other-gem', 'other-gem')
        (self.home / '.gemini').mkdir(parents=True, exist_ok=True)
        (self.home / '.gemini/settings.json').write_text(
            json.dumps({'skills': {'disabled': ['gem-scout']}})
        )
        (self.home / '.claude').mkdir(parents=True, exist_ok=True)
        (self.home / '.claude/settings.json').write_text(
            json.dumps({'skillOverrides': {'claude-scout': 'off'}})
        )

        gemini = {row['name']: row for row in scopes.scan_scope('gemini')}
        claude = {row['name']: row for row in scopes.scan_scope('claude-code')}

        scout = gemini['gem-scout']['native_state']
        self.assertEqual(scout['consumer'], 'gemini')
        self.assertEqual(scout['observed_setting'], 'disabled')
        self.assertEqual(gemini['other-gem']['native_state']['observed_setting'],
                         'not disabled by the files read')

        expected = observe_native_state('claude-code', 'claude-scout',
                                        home=self.home, project=self.project)
        self.assertEqual(claude['claude-scout']['native_state'], expected)
        self.assertEqual(claude['claude-scout']['native_state']['observed_setting'], 'off')


if __name__ == '__main__':
    unittest.main()
