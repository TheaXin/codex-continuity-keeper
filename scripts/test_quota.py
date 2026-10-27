#!/usr/bin/env python3
import json, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
import keeper, quota

def data(a=0,b=None,reset=None):
    return {'rateLimitsByLimitId':{'codex':{'primary':{'usedPercent':a,'resetsAt':reset},'secondary':{'usedPercent':b,'resetsAt':reset} if b is not None else None}}}

class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();keeper.init(self.root)
    def tearDown(self):self.temp.cleanup()
    def test_thresholds_any_window_and_null(self):
        for a,b,want in [(94.99,50,False),(94.999999,50,False),(95,50,True),(1,95,True),(100,20,True),(5,None,False)]:
            with self.subTest(a=a,b=b):
                r=quota.observe(self.root,data(a,b),now=100);self.assertEqual(r['low'],want)
        for x in [None,True,float('nan'),-1,101]:
            self.assertEqual(quota.windows_from(data(x)),[])
        self.assertEqual(quota.windows_from({'rateLimits':{'primary':None}}),[])
    def test_buckets_reset_and_unknown_do_not_fabricate(self):
        raw=data(20);raw['rateLimitsByLimitId']['special']={'primary':{'usedPercent':97,'resetsAt':200}}
        r=quota.observe(self.root,raw,now=100);self.assertTrue(r['low'])
        unknown=quota.observe(self.root,{},now=110);self.assertTrue(unknown['low']);self.assertEqual(unknown['status'],'unknown')
        self.assertFalse(quota.effective(unknown,now=201)['low'])
        self.assertTrue((keeper.state(self.root)/'QUOTA_HANDOFF.md').exists())
        self.assertFalse(quota.observe(self.root,data(10,10),now=202)['low'])
    def test_cache_and_real_api_failure(self):
        with patch.object(quota,'fetch_limits',return_value=data(96)) as f:
            self.assertTrue(quota.check(self.root)['low']);quota.check(self.root);self.assertEqual(f.call_count,1)
        with patch.object(quota,'fetch_limits',side_effect=TimeoutError):
            r=quota.check(self.root,force=True);self.assertTrue(r['low']);self.assertEqual(r['status'],'unknown')
        saved=json.loads((keeper.state(self.root)/'quota.json').read_text());self.assertNotIn('accountId',saved)
    def test_hook_saves_files_and_signals_final_handoff(self):
        (self.root/'result.txt').write_text('actual work')
        with patch.object(quota,'fetch_limits',return_value=data(95)):
            r=keeper.hook({'cwd':str(self.root),'hook_event_name':'PostToolUse','tool_name':'Bash'})
        self.assertIn('LOW_QUOTA_HANDOFF',r['hookSpecificOutput']['additionalContext'])
        m=keeper.load(keeper.state(self.root)/'latest.json');self.assertIn('result.txt',m['files'])
        self.assertNotIn('decision',r) # Allow the model to save semantic notes and issue its final reply.
        (self.root/'PROGRESS.md').write_text('Verified result.txt exists; unfinished: unit two')
        keeper.checkpoint(self.root,'low-quota-final')
        self.assertEqual(keeper.status_report(self.root)['drift'],[])
    def test_readonly_turn_zero_writes(self):
        transcript=self.root/'rollout.jsonl';transcript.write_text(json.dumps({'type':'event_msg','payload':{'type':'user_message','message':'只看进度'}})+'\n')
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch.object(quota,'fetch_limits') as f:
            for event in ['PostToolUse','Stop']:
                self.assertEqual(keeper.hook({'cwd':str(self.root),'hook_event_name':event,'transcript_path':str(transcript)}),{})
            f.assert_not_called()
        after={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()};self.assertEqual(before,after)
    def test_verified_upgrade_preserves_hooks_and_backs_up_old_skill(self):
        import hashlib, shutil
        from install import install
        source=Path(keeper.__file__).resolve().parents[1]
        old=self.root/'old-source';shutil.copytree(source,old,ignore=shutil.ignore_patterns('__pycache__'))
        (old/'SKILL.md').write_text((old/'SKILL.md').read_text()+'\nOld reviewed fixture.\n')
        home=self.root/'codex';install(home,old)
        dest=home/'skills'/'codex-continuity-keeper'
        hashes={p.relative_to(dest).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        manifest=self.root/'baseline.json';manifest.write_text(json.dumps({'files_sha256':hashes}))
        (home/'config.toml').write_text('[hooks.state.fixture]\ntrusted_hash = \"existing-trust\"\n')
        before=(home/'hooks.json').read_bytes()
        result=install(home,source,manifest)
        self.assertEqual(before,(home/'hooks.json').read_bytes())
        self.assertIn('existing-trust',(home/'config.toml').read_text())
        self.assertIn('Old reviewed fixture',(Path(result['backup'])/'skill'/'SKILL.md').read_text())
        self.assertEqual((dest/'SKILL.md').read_text(),(source/'SKILL.md').read_text())
    def test_native_tool_result_and_recorded_remaining(self):
        raw={'content':[{'type':'text','text':json.dumps(data(96))}]}
        self.assertEqual(quota.windows_from(raw)[0]['remainingPercent'],4)
        self.assertTrue(quota.observe(self.root,raw)['low'])
if __name__=='__main__': unittest.main(verbosity=2)
