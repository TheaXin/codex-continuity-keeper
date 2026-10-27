#!/usr/bin/env python3
import json, tempfile, unittest
from pathlib import Path
from doctor import diagnose
from install import install

class DeploymentTests(unittest.TestCase):
    def test_fresh_install_in_path_with_spaces_and_unicode(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)/'space 中文 home'
            install(home,Path(__file__).resolve().parents[1])
            d=diagnose(home)
            self.assertTrue(d['skill_installed']);self.assertTrue(d['quota_guard_installed']);self.assertTrue(d['hooks_configured'])
            self.assertIn('NOT VERIFIED',d['trust_status'])
    def test_empty_home_diagnosis_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)/'not-created';d=diagnose(home)
            self.assertFalse(home.exists());self.assertFalse(d['skill_installed'])
    def test_bad_config_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);p=home/'hooks.json';p.write_text('{bad',encoding='utf-8')
            d=diagnose(home);self.assertFalse(d['hooks_configured']);self.assertEqual(p.read_text(),'{bad')
    def test_uninstall_is_preview_then_selective_archive(self):
        from uninstall import uninstall
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);source=Path(__file__).resolve().parents[1];install(home,source)
            hp=home/'hooks.json';h=json.loads(hp.read_text(encoding='utf-8'));h['hooks']['Stop'].append({'hooks':[{'type':'command','command':'echo unrelated'}]});hp.write_text(json.dumps(h),encoding='utf-8')
            before=hp.read_bytes();preview=uninstall(home);self.assertEqual(preview['hooks_to_remove'],5);self.assertEqual(before,hp.read_bytes())
            done=uninstall(home,apply=True);self.assertFalse((home/'skills'/'codex-continuity-keeper').exists())
            self.assertEqual(json.loads(hp.read_text())['hooks']['Stop'][0]['hooks'][0]['command'],'echo unrelated')
            self.assertTrue((Path(done['backup'])/'skill'/'SKILL.md').exists())
if __name__=='__main__' :unittest.main(verbosity=2)
