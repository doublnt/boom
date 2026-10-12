"""Opt-in native Codex configuration checks; synthetic auth and no model calls."""
import json
import os
import unittest

import test_boom
import test_profile_regressions


@unittest.skipUnless(os.environ.get('BOOM_TEST_REAL_CODEX'),
                     'set BOOM_TEST_REAL_CODEX to a native Codex executable')
class NativeCodexProfiles(unittest.TestCase):
    write = test_boom.BoomRegression.write
    run_boom = test_profile_regressions.ProfileRegressions.run_boom
    api_profile = test_profile_regressions.ProfileRegressions.api_profile

    def setUp(self):
        test_boom.BoomRegression.setUp(self)
        self.env['BOOM_REAL_CODEX'] = os.environ['BOOM_TEST_REAL_CODEX']

    def test_native_codex_accepts_edited_multi_provider_config(self):
        folder = self.api_profile()
        config = folder / 'config.toml'
        original = config.read_text().replace('[model_providers.custom]', '''[model_providers.other]
name = "other"
base_url = "https://other.example.invalid/v1"
env_key = "OTHER_KEY"
wire_api = "responses"

[model_providers.custom]''')
        config.write_text(original)
        result = self.run_boom('x', 'edit', 'api', input='\n\n\nupdated-model\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write(folder / 'auth.json', json.dumps({'auth_mode': 'apikey', 'OPENAI_API_KEY': 'synthetic-key'}))
        result = self.run_boom('x', 'api', '--', 'login', 'status')
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
