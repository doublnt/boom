"""Offline regression tests: disposable HOME, fake CLIs and fake HTTP only."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

BOOM = Path(__file__).resolve().parents[1] / 'boom'


class BoomRegression(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='boom-regression-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'; self.home.mkdir()
        self.bin = self.root / 'bin'; self.bin.mkdir()
        for name in ['node', 'python3']:
            (self.bin / name).symlink_to(shutil.which(name))
        self.fake = self.write(self.bin / 'capture', '''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
args=sys.argv[1:]
record={'argv':args,'global':(Path(os.environ['HOME'])/'.claude/settings.json').read_text() if (Path(os.environ['HOME'])/'.claude/settings.json').exists() else None}
if '--settings' in args:
    p=Path(args[args.index('--settings')+1]); record.update(settings=json.loads(p.read_text()),temp=str(p),mode=p.stat().st_mode & 0o777)
Path(os.environ['CAPTURE']).write_text(json.dumps(record))
if os.environ.get('WAIT'): time.sleep(60)
sys.exit(int(os.environ.get('EXIT_CODE','0')))
'''); self.fake.chmod(0o755)
        self.env = {'HOME':str(self.home),'BOOM_HOME':str(self.home / '.boom'),
                    'PATH':str(self.bin)+':/usr/bin:/bin','TMPDIR':str(self.root),
                    'BOOM_REAL_CLAUDE':str(self.fake),'BOOM_REAL_CODEX':str(self.fake),
                    'CAPTURE':str(self.root/'capture.json'),'NO_COLOR':'1'}

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text); return path

    def run_boom(self, *args):
        return subprocess.run(['/bin/bash',str(BOOM),*args],env=self.env,cwd=self.root,capture_output=True,text=True,timeout=10)

    def captured(self): return json.loads((self.root/'capture.json').read_text())

    def official(self):
        self.write(self.home/'.boom/claude/profiles/official.json','{}')
        self.write(self.home/'.boom/claude/common.json','{"model":"old-provider","env":{"ANTHROPIC_API_KEY":"synthetic-secret"},"theme":"dark"}')

    def test_default_safe_and_explicit_unsafe(self):
        for kind,flag in [('c','--dangerously-skip-permissions'),('x','--dangerously-bypass-approvals-and-sandbox')]:
            for wrapper_flags,unsafe in [([],False),(['--safe'],False),(['--unsafe'],True)]:
                p=self.run_boom(kind,'--no-profile',*wrapper_flags,'--','--version')
                self.assertEqual(p.returncode,0,p.stderr)
                self.assertEqual(flag in self.captured()['argv'],unsafe)

    def test_official_never_swaps_global_settings(self):
        self.official(); sentinel='{"sentinel":"unchanged"}'
        settings=self.write(self.home/'.claude/settings.json',sentinel)
        p=self.run_boom('c','official','--','--version'); self.assertEqual(p.returncode,0,p.stderr)
        data=self.captured(); self.assertEqual(data['global'],sentinel); self.assertEqual(settings.read_text(),sentinel)
        self.assertEqual(data['mode'],0o600); self.assertFalse(Path(data['temp']).exists())
        self.assertNotIn('ANTHROPIC_API_KEY',data['settings'].get('env',{}))
        self.assertEqual(data['settings']['theme'],'dark')

    def test_failed_cli_and_bad_json_do_not_leak_temp(self):
        self.official(); self.env['EXIT_CODE']='42'
        p=self.run_boom('c','official','--','-p','fixture'); self.assertEqual(p.returncode,42,p.stderr)
        self.assertFalse(list(self.root.glob('boom-claude-*')))
        self.write(self.home/'.boom/claude/common.json','{invalid')
        p=self.run_boom('c','official','--','-p','fixture'); self.assertNotEqual(p.returncode,0)
        self.assertFalse(list(self.root.glob('boom-claude-*')))

    def test_official_preserves_explicit_model_aliases_without_common_env(self):
        self.write(self.home/'.boom/claude/profiles/official.json','{"env":{"ANTHROPIC_MODEL":"sonnet","CLAUDE_CODE_SUBAGENT_MODEL":"haiku"}}')
        p=self.run_boom('c','official','--','--version'); self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(self.captured()['settings']['env']['ANTHROPIC_MODEL'],'sonnet')
        self.assertEqual(self.captured()['settings']['env']['CLAUDE_CODE_SUBAGENT_MODEL'],'haiku')

    def test_official_keeps_native_user_plugin_discovery(self):
        self.official()
        p=self.run_boom('c','official','--','plugin','list','--json')
        self.assertEqual(p.returncode,0,p.stderr)
        args=self.captured()['argv']
        if '--setting-sources' in args:
            self.assertIn('user',args[args.index('--setting-sources')+1].split(','))
        self.assertNotIn('--safe-mode',args)
        self.assertNotIn('--disable-slash-commands',args)

    def test_official_masks_user_provider_settings_without_editing_them(self):
        self.official()
        config=self.root/'custom claude'; self.env['CLAUDE_CONFIG_DIR']=str(config)
        user={'apiKeyHelper':'/usr/bin/false','env':{'ANTHROPIC_API_KEY':'synthetic-user-key',
              'ANTHROPIC_BASE_URL':'https://example.invalid','CLAUDE_CODE_USE_VERTEX':'1',
              'ANTHROPIC_MODEL':'old-provider'},'enabledPlugins':{'kept@fixture':True}}
        settings=self.write(config/'settings.json',json.dumps(user))
        self.write(self.home/'.boom/claude/profiles/official.json','{"env":{"ANTHROPIC_MODEL":"sonnet"}}')
        p=self.run_boom('c','official','--','auth','status','--json')
        self.assertEqual(p.returncode,0,p.stderr)
        merged=self.captured()['settings']
        self.assertEqual(merged.get('apiKeyHelper'),'')
        for key in ['ANTHROPIC_API_KEY','ANTHROPIC_BASE_URL','CLAUDE_CODE_USE_VERTEX']:
            self.assertEqual(merged.get('env',{}).get(key),'',key)
        self.assertEqual(merged['env']['ANTHROPIC_MODEL'],'sonnet')
        self.assertEqual(json.loads(settings.read_text()),user)

    def test_termination_cleans_owned_temp(self):
        self.official(); self.env['WAIT']='1'
        p=subprocess.Popen(['/bin/bash',str(BOOM),'c','official','--','-p','fixture'],env=self.env,cwd=self.root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        try:
            end=time.monotonic()+3
            while not (self.root/'capture.json').exists() and time.monotonic()<end: time.sleep(.02)
            self.assertTrue((self.root/'capture.json').exists()); p.terminate()
            p.communicate(timeout=3); self.assertEqual(p.returncode,143)
            self.assertFalse(Path(self.captured()['temp']).exists())
        finally:
            try: os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            p.communicate(timeout=3)

    def test_read_only_commands_do_not_create_layout(self):
        for args in [('help',),('c','list'),('x','list'),('c','--no-profile','--','--version')]:
            p=self.run_boom(*args); self.assertEqual(p.returncode,0,p.stderr)
        self.assertFalse((self.home/'.boom').exists())

    def test_dot_profile_cannot_delete_parent(self):
        keep=self.write(self.home/'.boom/codex/keep','protected')
        for name in ['.','..','../escape']:
            p=self.run_boom('x','remove',name); self.assertNotEqual(p.returncode,0)
            self.assertTrue(keep.exists())

    def test_clean_preserves_backups_and_staging_by_default(self):
        backup=self.write(self.home/'.boom/claude/common.json.bak.fixture','protected')
        staged=self.write(self.home/'.boom/codex/profiles/official/.tmp/live','protected')
        p=self.run_boom('clean','--dry-run'); self.assertEqual(p.returncode,0,p.stderr)
        self.assertNotIn(str(backup),p.stdout); self.assertNotIn(str(staged.parent),p.stdout)
        self.assertTrue(backup.exists()); self.assertTrue(staged.exists())

    def test_clean_handles_newlines_and_ignores_profile_symlinks(self):
        outside=self.write(self.root/'outside/logs_2.sqlite','protected')
        profiles=self.home/'.boom/codex/profiles'; profiles.mkdir(parents=True)
        (profiles/'linked').symlink_to(outside.parent,target_is_directory=True)
        odd=self.write(self.home/'.boom/odd\nname/.DS_Store','disposable fixture')
        p=self.run_boom('clean','--yes'); self.assertEqual(p.returncode,0,p.stderr)
        self.assertFalse(odd.exists()); self.assertEqual(outside.read_text(),'protected')

    def status_fixture(self, body):
        self.write(self.home/'.claude/.credentials.json','{"claudeAiOauth":{"accessToken":"synthetic"}}')
        security=self.write(self.bin/'security','#!/bin/sh\nexit 1\n'); security.chmod(0o755)
        mock=self.write(self.root/'fetch.cjs', 'global.fetch=async (url)=>{if(url!=="https://api.anthropic.com/api/oauth/usage")throw new Error("unexpected endpoint");return {ok:true,status:200,text:async()=>'+json.dumps(json.dumps(body))+'};};\n')
        self.env['NODE_OPTIONS']='--require='+str(mock)

    def test_claude_only_status_dynamic_windows_and_null_unknown(self):
        self.status_fixture({'five_hour':{'utilization':None},'seven_day_fable':{'utilization':20}})
        p=self.run_boom('status','--claude','--official'); self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('7d fable: 80% left',p.stdout); self.assertNotIn('100% left',p.stdout)
        self.assertNotIn('Codex',p.stdout)

    def test_status_errors_nonzero(self):
        self.status_fixture({})
        p=self.run_boom('status','--claude','--official'); self.assertNotEqual(p.returncode,0)
        self.assertIn('unknown',p.stdout)

    def test_codex_primary_window_is_not_assumed_five_hours(self):
        self.write(self.home/'.codex/auth.json','{"auth_mode":"chatgpt","tokens":{"access_token":"synthetic"}}')
        body={'plan_type':'pro','rate_limit':{'primary_window':{'used_percent':37,'limit_window_seconds':604800},'secondary_window':{'used_percent':None}}}
        mock=self.write(self.root/'fetch-codex.cjs','global.fetch=async (url)=>{if(url!=="https://chatgpt.com/backend-api/wham/usage")throw new Error("unexpected endpoint");return {ok:true,status:200,text:async()=>'+json.dumps(json.dumps(body))+'};};\n')
        self.env['NODE_OPTIONS']='--require='+str(mock)
        p=self.run_boom('status','--codex','--official'); self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('weekly: 63% left',p.stdout); self.assertNotIn('5h:',p.stdout); self.assertNotIn('100% left',p.stdout)

    def test_shared_usage_counts_session_and_file_once(self):
        session=self.write(self.home/'.boom/codex/shared/sessions/fixture.jsonl',json.dumps({'type':'event_msg','timestamp':'2026-09-29T00:00:00Z','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':100,'output_tokens':20,'cached_input_tokens':80}}}})+'\n')
        for profile in ('one','two'):
            folder=self.home/'.boom/codex/profiles'/profile; folder.mkdir(parents=True)
            (folder/'sessions').symlink_to(session.parent,target_is_directory=True)
        p=self.run_boom('usage'); self.assertEqual(p.returncode,0,p.stderr)
        codex=p.stdout.split('== Codex Usage ==')[1].split('== Gemini Usage ==')[0]
        self.assertIn('Files scanned: 1',codex); self.assertNotIn('2 calls',codex)
        self.assertIn('1 calls',codex)

    def test_termination_bounds_child_ignoring_term(self):
        self.official(); self.env['WAIT']='1'
        text=self.fake.read_text().replace('if os.environ.get(\'WAIT\'): time.sleep(60)',"if os.environ.get('WAIT'):\n    import signal\n    signal.signal(signal.SIGTERM,signal.SIG_IGN)\n    time.sleep(60)")
        self.fake.write_text(text)
        p=subprocess.Popen(['/bin/bash',str(BOOM),'c','official','--','-p','fixture'],env=self.env,cwd=self.root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        try:
            end=time.monotonic()+3
            while not (self.root/'capture.json').exists() and time.monotonic()<end: time.sleep(.02)
            self.assertTrue((self.root/'capture.json').exists()); p.send_signal(signal.SIGINT)
            p.communicate(timeout=4); self.assertEqual(p.returncode,130)
            self.assertFalse(Path(self.captured()['temp']).exists())
        finally:
            try: os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            p.communicate(timeout=3)


if __name__ == '__main__': unittest.main()
