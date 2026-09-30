"""Local plugin startup contract, isolated homes and no model calls."""
import json
import os
from pathlib import Path
import subprocess
import signal
import time
import unittest

import test_boom


class LocalPluginRegression(unittest.TestCase):
    setUp = test_boom.BoomRegression.setUp
    write = test_boom.BoomRegression.write
    run_boom = test_boom.BoomRegression.run_boom
    captured = test_boom.BoomRegression.captured
    def source(self):
        source = self.root / 'local skills with spaces'
        self.write(source / '.claude-plugin/plugin.json', json.dumps({'name': 'fixture-plugin'}))
        self.write(source / 'SKILL.md', 'original')
        self.write(source / 'scripts/sync-local-plugins.py', '''import argparse,json,os,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--target');p.add_argument('--ensure',action='store_true');a=p.parse_args()
home=Path(os.environ['CODEX_HOME' if a.target=='codex' else 'CLAUDE_CONFIG_DIR'])
source=Path(__file__).resolve().parents[1]
with open(os.environ['SYNC_LOG'],'a') as log:log.write(json.dumps({'tool':a.target,'home':str(home),'real_claude':os.environ.get('BOOM_REAL_CLAUDE'),'real_codex':os.environ.get('BOOM_REAL_CODEX')})+'\\n')
if os.environ.get('FAIL_SYNC'):sys.exit(7)
if os.environ.get('WAIT_SYNC'):
 import time
 Path(os.environ['SYNC_STARTED']).touch();time.sleep(60)
home.mkdir(parents=True,exist_ok=True);state=home/'fixture-version';version=(source/'SKILL.md').read_text()
updated=not state.exists() or state.read_text()!=version
if updated:state.write_text(version)
print(json.dumps({'schema_version':1,'status':'ready','updated':updated,'version':version}))
''')
        self.env['SYNC_LOG'] = str(self.root / 'sync.jsonl')
        return source

    def register(self):
        source = self.source()
        result = self.run_boom('plugins', 'add', str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        return source

    def sync_records(self):
        return [json.loads(line) for line in (self.root / 'sync.jsonl').read_text().splitlines()]

    def test_registered_source_updates_next_launch_only_in_selected_environment(self):
        source = self.register()
        for name in ('one', 'two'):
            self.write(self.home / '.boom/codex/profiles' / name / 'config.toml', 'model="keep"\n')
        result = self.run_boom('x', 'one', '--', 'exec', 'fixture')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('updated', result.stderr)
        one = self.home / '.boom/codex/profiles/one'
        two = self.home / '.boom/codex/profiles/two'
        self.assertEqual((one / 'fixture-version').read_text(), 'original')
        self.assertFalse((two / 'fixture-version').exists())
        self.assertFalse((self.home / '.codex').exists())
        self.assertEqual(self.sync_records()[0]['home'], str(one))
        self.assertEqual(self.sync_records()[0]['real_codex'], str(self.fake))
        self.write(source / 'SKILL.md', 'changed')
        result = self.run_boom('x', 'one', '--', 'exec', 'fixture')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((one / 'fixture-version').read_text(), 'changed')
        result = self.run_boom('x', 'one', '--', 'exec', 'fixture')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('updated', result.stderr)
        self.assertEqual(self.captured()['argv'], ['exec', 'fixture'])

    def test_native_routes_and_custom_claude_home_are_respected(self):
        self.register()
        self.env['CODEX_HOME'] = str(self.root / 'native codex')
        self.env['CLAUDE_CONFIG_DIR'] = str(self.root / 'native claude')
        for tool, args in [('x', ['exec', 'fixture']), ('c', ['-p', 'fixture'])]:
            result = self.run_boom(tool, '--no-profile', '--', *args)
            self.assertEqual(result.returncode, 0, result.stderr)
        records = self.sync_records()
        self.assertEqual(records[0]['home'], self.env['CODEX_HOME'])
        self.assertEqual(records[1]['home'], self.env['CLAUDE_CONFIG_DIR'])
        self.assertEqual(self.captured()['argv'], ['-p', 'fixture'])

    def test_utility_commands_and_explicit_opt_out_do_not_sync(self):
        self.register()
        self.env['FAIL_SYNC'] = '1'
        for args in [('x', '--no-profile', '--', '--version'),
                     ('x', '--no-profile', '--', 'plugin', 'list', '--json'),
                     ('x', '--no-profile', '--', 'login', 'status'),
                     ('c', '--no-profile', '--', 'auth', 'status'),
                     ('x', '--no-profile', '--', 'exec', '--ignore-user-config', 'fixture'),
                     ('x', '--no-profile', '--no-plugin-sync', '--', 'exec', 'fixture')]:
            result = self.run_boom(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('--no-plugin-sync', self.captured()['argv'])
        self.assertFalse((self.root / 'sync.jsonl').exists())

    def test_sync_failure_stops_launch_without_corrupting_registration(self):
        self.register(); self.env['FAIL_SYNC'] = '1'
        registry = self.home / '.boom/local-plugins.json'
        original = registry.read_bytes()
        result = self.run_boom('x', '--no-profile', '--', 'exec', 'fixture')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sync', result.stderr)
        self.assertFalse((self.root / 'capture.json').exists())
        self.assertEqual(registry.read_bytes(), original)
        self.assertEqual(self.run_boom('plugins', 'remove', 'fixture-plugin').returncode, 0)
        self.assertEqual(self.run_boom('x', '--no-profile', '--', 'exec', 'fixture').returncode, 0)

    def test_registration_rejects_missing_adapter_and_source_identity_changes(self):
        source = self.register()
        self.write(source / '.claude-plugin/plugin.json', json.dumps({'name': 'renamed'}))
        result = self.run_boom('c', '--no-profile', '--', '-p', 'fixture')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'capture.json').exists())
        (source / 'scripts/sync-local-plugins.py').unlink()
        result = self.run_boom('plugins', 'add', str(source))
        self.assertNotEqual(result.returncode, 0)

    def test_cancelling_startup_terminates_only_its_sync_process_group(self):
        source = self.register()
        script = source / 'scripts/sync-local-plugins.py'
        script.write_text('''import os,signal,subprocess,sys,time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
Path(os.environ['SYNC_STARTED']).write_text(str(child.pid))
time.sleep(60)
''')
        marker = self.root / 'sync-started'; self.env['SYNC_STARTED'] = str(marker)
        process = subprocess.Popen(['/bin/bash', str(test_boom.BOOM), 'x', '--no-profile', '--', 'exec', 'fixture'],
                                   env=self.env, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pid = None
        try:
            deadline = time.monotonic() + 4
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(marker.exists())
            pid = int(marker.read_text()); process.terminate()
            process.communicate(timeout=5)
            self.assertEqual(process.returncode, 143)
            self.assertFalse((self.root / 'capture.json').exists())
            # A reparented killed child can briefly be a zombie on Unix.
            state = subprocess.run(['ps', '-p', str(pid), '-o', 'stat='], capture_output=True, text=True)
            self.assertTrue(state.returncode != 0 or state.stdout.strip().startswith('Z'), state.stdout)
        finally:
            if process.poll() is None:
                process.kill(); process.communicate()
            if pid:
                try: os.kill(pid, signal.SIGKILL)
                except ProcessLookupError: pass
