"""Profile and usage regressions with synthetic credentials and disposable homes."""
import json
import subprocess
import tomllib
import unittest

import test_boom


class ProfileRegressions(unittest.TestCase):
    setUp = test_boom.BoomRegression.setUp
    write = test_boom.BoomRegression.write
    captured = test_boom.BoomRegression.captured

    def run_boom(self, *args, input=None):
        return subprocess.run(
            ['/bin/bash', str(test_boom.BOOM), *args], input=input,
            env=self.env, cwd=self.root, capture_output=True, text=True, timeout=10)

    def api_profile(self, name='api'):
        result = self.run_boom('x', 'add', name, '--api',
                               '--base-url', 'https://api.example.invalid/v1',
                               '--model', 'synthetic-model', input='synthetic-key\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.home / '.boom/codex/profiles' / name

    def test_codex_uses_path_without_an_override(self):
        (self.bin / 'codex').symlink_to(self.fake)
        del self.env['BOOM_REAL_CODEX']
        result = self.run_boom('x', '--no-profile', '--', '--version')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'capture.json').exists(), result.stdout)
        self.assertEqual(self.captured()['argv'], ['--version'])

    def assert_subscription_config(self, folder):
        config = tomllib.loads((folder / 'config.toml').read_text())
        self.assertEqual(config.get('model_provider', 'openai'), 'openai')
        self.assertNotIn('model', config)
        self.assertNotIn('profile', config)
        self.assertNotIn('forced_login_method', config)
        self.assertNotIn('model_providers', config)
        self.assertEqual(config['personality'], 'pragmatic')
        self.assertEqual(config['projects']['/fixture']['trust_level'], 'trusted')
        self.assertFalse((folder / 'api_key').exists())

    def test_subscription_does_not_inherit_default_api_routing(self):
        source = self.api_profile()
        config = source / 'config.toml'
        original = 'personality = "pragmatic"\nprofile = "api"\nforced_login_method = "api"\n' + config.read_text()
        original += '\n[projects."/fixture"]\ntrust_level = "trusted"\n'
        config.write_text(original)
        result = self.run_boom('x', 'add', 'subscription', '--no-login')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_subscription_config(source.parent / 'subscription')
        self.assertEqual(config.read_text(), original)

    def test_api_edit_preserves_other_providers_and_nested_settings(self):
        folder = self.api_profile()
        other = '''[model_providers.other]
name = "other"
base_url = "https://other.example.invalid/v1"
env_key = "OTHER_KEY"
'''
        custom = '''[model_providers.custom]
name = "custom"
base_url = "https://api.example.invalid/v1"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
request_max_retries = 7
[model_providers.custom.http_headers]
"X-Fixture" = "kept"
'''
        nested = '''[profiles.other]
model = "nested-model"
model_provider = "other"
'''
        for providers in (other + custom, custom + other):
            with self.subTest(providers=providers):
                config = folder / 'config.toml'
                config.write_text('model = "synthetic-model"\nmodel_provider = "custom"\n' + providers + nested)
                before = tomllib.loads(config.read_text())
                result = self.run_boom('x', 'edit', 'api', input='\n\n\nupdated-model\n')
                self.assertEqual(result.returncode, 0, result.stderr)
                after = tomllib.loads(config.read_text())
                self.assertEqual(after['model'], 'updated-model')
                self.assertEqual(after['model_providers']['custom']['base_url'],
                                 'https://api.example.invalid/v1')
                self.assertEqual(after['model_providers']['custom']['request_max_retries'], 7)
                self.assertEqual(after['model_providers']['custom']['http_headers'], {'X-Fixture': 'kept'})
                self.assertEqual(after['model_providers']['other'], before['model_providers']['other'])
                self.assertEqual(after['profiles'], before['profiles'])
                self.assertEqual((folder / 'api_key').read_text(), 'synthetic-key')
                self.assertEqual(config.stat().st_mode & 0o777, 0o600)

    def test_api_edit_respects_quoted_keys_comments_and_multiline_strings(self):
        folder = self.api_profile()
        original = '''"model" = 'synthetic-model' # keep-model
'model_provider' = "custom"
developer_instructions = ''' + "'''" + '''
[model_providers.custom]
model = "this is text, not a setting"
''' + "'''" + '''
["model_providers" . 'other']
base_url = "https://other.example.invalid/v1"
["model_providers" . 'custom']
'base_url' = 'https://api.example.invalid/v1#literal' # keep-url
env_key = "OPENAI_API_KEY"
wire_api = "responses"
'''
        config = folder / 'config.toml'
        config.write_text(original)
        before = tomllib.loads(original)
        result = self.run_boom('x', 'edit', 'api', input='\n\n\n\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        after = tomllib.loads(config.read_text())
        self.assertEqual(after['model'], before['model'])
        self.assertEqual(after['developer_instructions'], before['developer_instructions'])
        self.assertEqual(after['model_providers']['custom']['base_url'],
                         before['model_providers']['custom']['base_url'])
        self.assertEqual(after['model_providers']['other'], before['model_providers']['other'])

    def test_api_edit_fills_missing_provider_fields_without_a_final_newline(self):
        folder = self.api_profile()
        for body in ('[model_providers.custom]', '[model_providers]',
                     'model_providers.custom.base_url = "https://old.example.invalid"'):
            with self.subTest(body=body):
                config = folder / 'config.toml'
                config.write_text('model = "synthetic-model"\nmodel_provider = "custom"\n' + body)
                result = self.run_boom('x', 'edit', 'api',
                                       input='\nhttps://new.example.invalid/v1\n\n\n')
                self.assertEqual(result.returncode, 0, result.stderr)
                after = tomllib.loads(config.read_text())
                self.assertEqual(after['model'], 'synthetic-model')
                self.assertEqual(after['model_providers']['custom']['base_url'],
                                 'https://new.example.invalid/v1')
                self.assertEqual(after['model_providers']['custom']['env_key'], 'OPENAI_API_KEY')
                self.assertEqual(after['model_providers']['custom']['wire_api'], 'responses')

    def test_api_edit_rejects_inline_provider_tables_without_changing_files(self):
        folder = self.api_profile()
        original = '''model = "synthetic-model"
model_provider = "custom"
model_providers.custom = {base_url = "https://api.example.invalid", env_key = "OPENAI_API_KEY"}
'''
        config = folder / 'config.toml'
        config.write_text(original)
        result = self.run_boom('x', 'edit', 'api', input='\nhttps://new.example.invalid\nreplacement-key\nnew-model\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('inline tables', result.stderr)
        self.assertEqual(config.read_text(), original)
        self.assertEqual((folder / 'api_key').read_text(), 'synthetic-key')
        self.assertFalse(list(folder.glob('.config.tmp.*')))

    def test_api_edit_preserves_multiline_arrays_and_escaped_strings(self):
        folder = self.api_profile()
        original = '''model = "synthetic-model"
model_provider = "custom"
developer_instructions = """
model = "text"
[model_providers.custom]
An escaped quote: \\" and a backslash: \\\\.
"""
tools = [
    {name = "[model_providers.custom]", config = {model = "text"}}, # ignored comment ]
    {name = "fixture", values = [1, 2, 3]},
]
[model_providers.custom]
base_url = "https://api.example.invalid/v1"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
'''
        config = folder / 'config.toml'
        config.write_text(original)
        before = tomllib.loads(original)
        result = self.run_boom('x', 'edit', 'api', input='\n\n\nupdated-model\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        after = tomllib.loads(config.read_text())
        self.assertEqual(after['developer_instructions'], before['developer_instructions'])
        self.assertEqual(after['tools'], before['tools'])
        self.assertEqual(after['model'], 'updated-model')

    def test_claude_rename_moves_credentials_and_updates_default(self):
        result = self.run_boom('c', 'add', 'old',
                               input='https://api.example.invalid\nsynthetic-key\nsynthetic-model\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_boom('c', 'default', 'old').returncode, 0)
        result = self.run_boom('c', 'edit', 'old', input='new\n\n\nupdated-model\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        profiles = self.home / '.boom/claude/profiles'
        self.assertFalse((profiles / 'old.json').exists())
        updated = profiles / 'new.json'
        config = json.loads(updated.read_text())
        self.assertEqual(config['env']['ANTHROPIC_AUTH_TOKEN'], 'synthetic-key')
        self.assertEqual(config['env']['ANTHROPIC_MODEL'], 'updated-model')
        self.assertEqual(updated.stat().st_mode & 0o777, 0o600)
        self.assertEqual((profiles.parent / 'default').read_text(), 'new\n')
        self.assertEqual(self.run_boom('c', 'list').stdout.strip(), '* new (default)')

    def test_usage_counts_codex_cache_once_and_keeps_claude_cache(self):
        events = []
        for usage in ({'input_tokens': 100, 'cached_input_tokens': 80, 'output_tokens': 20},
                      {'input_tokens': 150, 'cached_input_tokens': 100, 'output_tokens': 35}):
            events.append({'type': 'event_msg', 'timestamp': '2026-10-12T00:00:00Z',
                           'payload': {'type': 'token_count', 'info': {'total_token_usage': usage}}})
        self.write(self.home / '.codex/sessions/fixture.jsonl',
                   ''.join(json.dumps(event) + '\n' for event in events))
        claude = {'type': 'assistant', 'timestamp': '2026-10-12T00:00:00Z', 'message': {
            'id': 'fixture', 'model': 'fixture', 'stop_reason': 'end_turn', 'usage': {
                'input_tokens': 100, 'output_tokens': 20,
                'cache_read_input_tokens': 80, 'cache_creation_input_tokens': 40}}}
        self.write(self.home / '.claude/projects/fixture/session.jsonl', json.dumps(claude) + '\n')
        result = self.run_boom('usage')
        self.assertEqual(result.returncode, 0, result.stderr)
        claude_output, codex_output = result.stdout.split('== Codex Usage ==')
        codex_output = codex_output.split('== Gemini Usage ==')[0]
        self.assertIn('All\n    total 185 tokens, 2 calls', codex_output)
        self.assertIn('in 50 | out 35', codex_output)
        self.assertIn('cache read 100 | write 0', codex_output)
        self.assertIn('All\n    total 240 tokens, 1 calls', claude_output)


if __name__ == '__main__':
    unittest.main()
