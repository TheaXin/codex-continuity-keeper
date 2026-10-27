#!/usr/bin/env python3
"""Observable isolation, crash-resume, concurrency, filtering and installer tests."""
import concurrent.futures, hashlib, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
import keeper
from unittest.mock import patch
from install import install
SCRIPT=Path(keeper.__file__).resolve()

class KeeperTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='ck2-test-'); self.base=Path(self.tmp.name).resolve(); self.root=self.base/'project'; self.root.mkdir()
    def tearDown(self): self.tmp.cleanup()
    def run_cli(self,*args,payload=None):
        result=subprocess.run([sys.executable,str(SCRIPT),'--root',str(self.root),*args],input=json.dumps(payload) if payload else None,text=True,capture_output=True,check=True)
        return json.loads(result.stdout)
    def tree_hash(self):
        return {str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
    def test_end_to_end_fresh_process_resume_export(self):
        self.run_cli('init')
        f=self.root/'task.txt'; f.write_text('unit one verified\nunit two pending\n')
        (self.root/'PROGRESS.md').write_text('已完成: unit one; evidence task.txt\n正在进行: unit two\n下一步: finish unit two\n')
        keeper.atomic(self.root/keeper.STATE/'quota.json',keeper.encoded({'checkedAt':__import__('time').time(),'status':'known','windows':[]}))
        cp=self.run_cli('hook',payload={'cwd':str(self.root),'hook_event_name':'PostToolUse','tool_name':'Bash','tool_input':{'command':'write task'}})
        self.assertEqual(cp,{})
        ident=self.run_cli('list')[-1]['id']
        self.assertIn('task.txt',keeper.load(self.root/keeper.STATE/'snapshots'/(ident+'.json'))['files'])
        # A new OS process has no previous Python memory; simulates a new session after abrupt exit.
        status=self.run_cli('status'); self.assertIn('unit two',status['documents']['progress']); self.assertEqual(status['drift'],[])
        start=self.run_cli('hook',payload={'cwd':str(self.root),'hook_event_name':'SessionStart','session_id':'new-session','source':'startup'})
        self.assertIn('下一步',start['hookSpecificOutput']['additionalContext'])
        f.unlink() # simulate loss after interruption; recover only via non-overwriting export
        out=self.base/'recovered'; self.run_cli('export',ident,str(out))
        self.assertFalse(f.exists()); self.assertIn('unit two pending',(out/'task.txt').read_text())
        f.write_text((out/'task.txt').read_text().replace('unit two pending','unit two verified'))
        (self.root/'PROGRESS.md').write_text('已完成: unit one and unit two; verified exact task.txt content\n下一步: none\n')
        self.assertIn('unit two verified',f.read_text()); self.run_cli('checkpoint')
        self.assertEqual(self.run_cli('status')['drift'],[])
    def test_dedup_read_only_and_mode_change(self):
        keeper.init(self.root); before=self.tree_hash()
        for _ in range(4): self.run_cli('status')
        self.run_cli('hook',payload={'cwd':str(self.root),'hook_event_name':'UserPromptSubmit','prompt':'只看进度'})
        self.assertEqual(before,self.tree_hash())
        a=self.run_cli('checkpoint'); self.assertFalse(a['changed'])
        f=self.root/'a.py'; f.write_text('print(1)\n'); keeper.checkpoint(self.root)
        f.chmod(0o700)
        if os.name!='nt': self.assertTrue(keeper.checkpoint(self.root)['changed'])
    def test_filter_and_symlink(self):
        keeper.init(self.root)
        (self.root/'.env').write_text('do not copy')
        (self.root/'ordinary.txt').write_text('api'+'_key = '+('X'*30))
        (self.root/'binary.bin').write_bytes(b'abc\0def')
        (self.root/'large.txt').write_bytes(b'x'*(keeper.MAX_FILE+1))
        external=self.base/'outside'; external.write_text('outside private')
        linked=True
        try: (self.root/'link').symlink_to(external)
        except OSError: linked=False
        (self.root/'private').mkdir(); (self.root/'private'/'note.txt').write_text('private')
        keeper.atomic(self.root/keeper.STATE/'policy.json',keeper.encoded({'exclude':['private/**']}))
        keeper.checkpoint(self.root)
        m=keeper.load(self.root/keeper.STATE/'latest.json')
        for n in ['.env','ordinary.txt','binary.bin','large.txt','private/note.txt']+(['link'] if linked else []): self.assertNotIn(n,m['files']); self.assertIn(n,m['skipped'])
    def test_symlink_refused_without_os_nofollow(self):
        external=self.base/'outside'; external.write_bytes(b'private outside content')
        link=self.root/'link'
        try: link.symlink_to(external)
        except OSError: self.skipTest('OS does not permit creating test symlinks')
        with patch.object(keeper.os,'O_NOFOLLOW',0,create=True):
            self.assertIsNone(keeper.read_safe(link))
        external.unlink()
        self.assertIsNone(keeper.read_safe(link))
    def test_binary_read_preserves_crlf_and_unicode(self):
        expected='line one\r\n中文\r\n'.encode('utf-8')
        p=self.root/'line-endings.txt';p.write_bytes(expected)
        self.assertEqual(keeper.read_safe(p),expected)
    def test_concurrent_hooks_and_crash_orphan(self):
        keeper.init(self.root); (self.root/'a').write_text('saved')
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:self.run_cli('checkpoint'),range(16)))
        self.assertEqual(sum(r['changed'] for r in results),1)
        for p in keeper.manifests(self.root/keeper.STATE):
            for v in keeper.load(p)['files'].values(): self.assertTrue((self.root/keeper.STATE/'objects'/v['sha256']).is_file())
        orphan=self.root/keeper.STATE/'objects'/('0'*64); orphan.write_bytes(b'orphan')
        self.run_cli('prune'); self.assertFalse(orphan.exists())
        # OS process dies with the lock: kernel releases it.
        subprocess.run([sys.executable,'-c',"import sys,os; sys.path.insert(0,sys.argv[1]); import keeper; ctx=keeper.locked(keeper.state(__import__('pathlib').Path(sys.argv[2]))); ctx.__enter__(); os._exit(9)",str(SCRIPT.parent),str(self.root)])
        self.assertFalse(self.run_cli('checkpoint')['changed'])
    def test_preserve_existing_and_isolate_nested(self):
        (self.root/'PROGRESS.md').write_text('user content')
        (self.root/'CONTINUITY_TASKS.md').write_text('user tasks')
        keeper.init(self.root); self.assertEqual((self.root/'PROGRESS.md').read_text(),'user content')
        nested=self.root/'sub'; nested.mkdir(); keeper.init(nested)
        self.assertEqual(keeper.root_at(nested),nested)
        self.assertEqual(keeper.load(nested/keeper.STATE/'project.json')['root'],str(nested))
        other=self.base/'other'; other.mkdir(); self.assertEqual(keeper.hook({'cwd':str(other),'hook_event_name':'Stop'}),{}); self.assertFalse((other/keeper.STATE).exists())
    def test_retention_and_export_safety(self):
        keeper.init(self.root); first=keeper.manifests(self.root/keeper.STATE)[0]
        for i in range(55): (self.root/'file').write_text(str(i)); keeper.checkpoint(self.root)
        self.assertTrue(first.exists()); self.assertLessEqual(len(keeper.manifests(self.root/keeper.STATE)),51)
        latest=keeper.load(self.root/keeper.STATE/'latest.json')['id']
        with self.assertRaises(ValueError): keeper.export(self.root,latest,str(self.root/'bad'))
        with self.assertRaises(ValueError): keeper.export(self.root,'../../bad',str(self.base/'bad'))
    def test_installer_preserves_config_and_is_idempotent(self):
        home=self.base/'codex'; home.mkdir(); (home/'AGENTS.md').write_text('existing rules\n'); (home/'config.toml').write_text('model = "existing"\n')
        original={'hooks':{'Stop':[{'hooks':[{'type':'command','command':'echo existing'}]}]}}
        (home/'hooks.json').write_text(json.dumps(original))
        source=SCRIPT.parents[1]; install(home,source); install(home,source)
        self.assertEqual((home/'config.toml').read_text(),'model = "existing"\n')
        self.assertTrue((home/'AGENTS.md').read_text().startswith('existing rules'))
        h=json.loads((home/'hooks.json').read_text()); self.assertEqual(len(h['hooks']['Stop']),2); self.assertEqual(h['hooks']['Stop'][0],original['hooks']['Stop'][0])
        installed=home/'skills'/'codex-continuity-keeper'/'SKILL.md'; installed.write_text('user modified')
        with self.assertRaises(ValueError): install(home,source)
        self.assertEqual(installed.read_text(),'user modified')
    def test_hooks_all_events_and_errors(self):
        keeper.init(self.root)
        keeper.atomic(self.root/keeper.STATE/'quota.json',keeper.encoded({'checkedAt':__import__('time').time(),'status':'known','windows':[]}))
        for event in ['SessionStart','UserPromptSubmit','PostToolUse','PreCompact','Stop']:
            response=self.run_cli('hook',payload={'cwd':str(self.root),'hook_event_name':event,'tool_name':'apply_patch'})
            self.assertNotIn('decision',response)
        (self.root/keeper.STATE/'project.json').write_text('{invalid')
        error=self.run_cli('hook',payload={'cwd':str(self.root),'hook_event_name':'Stop'})
        self.assertIn('failed',error['systemMessage'])
if __name__=='__main__': unittest.main(verbosity=2)
