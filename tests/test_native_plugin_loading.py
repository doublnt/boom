"""Opt-in real Claude CLI checks; isolated settings and no model requests."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('BOOM_TEST_REAL_CLAUDE'), 'set BOOM_TEST_REAL_CLAUDE to a native Claude executable')
class NativePluginLoading(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='boom-native-plugins-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'claude-config'
        self.config.mkdir()
        profiles = self.root / '.boom/claude/profiles'
        profiles.mkdir(parents=True)
        (profiles / 'official.json').write_text('{}')
        (profiles.parent / 'default').write_text('official\n')
        self.env = {'HOME': str(self.root), 'PATH': os.environ['PATH'],
                    'BOOM_HOME': str(self.root / '.boom'), 'CLAUDE_CONFIG_DIR': str(self.config),
                    'BOOM_REAL_CLAUDE': os.environ['BOOM_TEST_REAL_CLAUDE'],
                    'TMPDIR': str(self.root)}
        self.boom = os.environ.get('BOOM_UNDER_TEST', str(Path(__file__).resolve().parents[1] / 'boom'))

    def run_native(self, *args):
        return subprocess.run(['/bin/bash', self.boom, 'c', '--', *args],
                              env=self.env, cwd=self.root, capture_output=True, text=True, timeout=15)

    def test_user_skills_directory_plugin_is_loaded(self):
        plugin = self.config / 'skills/boom-fixture'
        manifest = plugin / '.claude-plugin/plugin.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'name': 'boom-fixture', 'version': '1.0.0'}))
        skill = plugin / 'skills/fixture/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: fixture\ndescription: Test plugin discovery.\n---\nFixture.\n')
        result = self.run_native('plugin', 'list', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        loaded = [p for p in json.loads(result.stdout) if p['id'] == 'boom-fixture@skills-dir']
        self.assertEqual(len(loaded), 1, result.stdout)
        self.assertTrue(loaded[0]['enabled'])
        self.assertEqual(Path(loaded[0]['installPath']), plugin)

    def test_user_api_settings_do_not_replace_official_auth(self):
        settings = self.config / 'settings.json'
        original = json.dumps({'env': {'ANTHROPIC_API_KEY': 'synthetic-not-a-secret',
                                      'ANTHROPIC_BASE_URL': 'https://example.invalid',
                                      'CLAUDE_CODE_USE_VERTEX': '1'},
                               'apiKeyHelper': '/usr/bin/false'})
        settings.write_text(original)
        result = self.run_native('auth', 'status', '--json')
        self.assertEqual(result.returncode, 1, result.stderr)
        status = json.loads(result.stdout)
        self.assertFalse(status['loggedIn'])
        self.assertEqual(status['authMethod'], 'none')
        self.assertEqual(status['apiProvider'], 'firstParty')
        self.assertEqual(settings.read_text(), original)


if __name__ == '__main__':
    unittest.main()
