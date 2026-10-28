#!/usr/bin/env python3
import hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from build_release import build,source_files
from verify_release import verify
from acceptance import run_acceptance
SOURCE=Path(__file__).resolve().parents[1]
class ReleaseTests(unittest.TestCase):
    def test_reproducible_archive_and_full_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=build(SOURCE,Path(tmp)/'a');b=build(SOURCE,Path(tmp)/'b')
            self.assertEqual(a,b)
            self.assertEqual(verify(Path(tmp)/'a'/a['archive'],Path(tmp)/'a/release-manifest.json')['status'],'PASS')
    def test_corrupt_download_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=build(SOURCE,Path(tmp)/'out');p=Path(tmp)/'out'/m['archive'];p.write_bytes(p.read_bytes()+b'corruption')
            with self.assertRaises(ValueError):verify(p,p.parent/'release-manifest.json')
    def test_path_traversal_rejected_even_with_matching_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);p=base/'bad.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('codex-continuity-keeper-1.0.0/../escape','bad')
            m={'version':'1.0.0','archive':'bad.zip','archive_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'files_sha256':{}}
            f=base/'manifest.json';f.write_text(json.dumps(m),encoding='utf-8')
            with self.assertRaises(ValueError):verify(p,f)
    def test_release_allowlist_excludes_runtime_and_private_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['VERSION','SKILL.md','LICENSE','scripts/install.py','scripts/quota.py','scripts/acceptance.py','scripts/demo_recovery.py']:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('1.0.0' if name=='VERSION' else 'fixture',encoding='utf-8')
            for name in ['.env','auth.json','config.toml','.continuity-keeper/latest.json','work/account.json','dist/old.zip']:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('private fixture',encoding='utf-8')
            self.assertEqual(len(source_files(root)),7)
    def test_persistent_demo_refuses_source_checkout(self):
        with self.assertRaises(ValueError):run_acceptance(SOURCE,SOURCE/'nested-demo')
if __name__=='__main__':unittest.main(verbosity=2)
