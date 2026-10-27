#!/usr/bin/env python3
"""Read-only deployment diagnostics. No auth reads, config writes, or model calls."""
import argparse, json, os, platform, shutil, subprocess, sys
from pathlib import Path

def diagnose(home):
    home=Path(home).expanduser().resolve(); cli=os.environ.get('CODEX_CLI_PATH') or shutil.which('codex')
    issues=[]; skill=home/'skills'/'codex-continuity-keeper'
    result={'python':platform.python_version(),'python_supported':sys.version_info>=(3,11),'platform':platform.system(),'codex_cli_found':bool(cli),'skill_installed':(skill/'SKILL.md').is_file(),'quota_guard_installed':(skill/'scripts'/'quota.py').is_file(),'hooks_configured':False,'hook_events':[],'issues':issues}
    if sys.version_info<(3,11):issues.append('Use Python 3.11+ to run the installer.')
    if not cli:issues.append('Install the official Codex CLI and put it on PATH or set CODEX_CLI_PATH.')
    hooks_path=home/'hooks.json'
    try:
        cfg=json.loads(hooks_path.read_text(encoding='utf-8'))
        for event,groups in cfg.get('hooks',{}).items():
            if any('codex-continuity-keeper' in str(h.get('command','')) for g in groups for h in g.get('hooks',[])):result['hook_events'].append(event)
        result['hooks_configured']=set(['SessionStart','UserPromptSubmit','PostToolUse','PreCompact','Stop'])<=set(result['hook_events'])
    except FileNotFoundError:issues.append('No hooks.json found. Run scripts/install.py first.')
    except (ValueError,TypeError,AttributeError):issues.append('hooks.json is malformed; preserve it and repair before installation.')
    if not result['skill_installed']:issues.append('Skill is not installed in the selected Codex home.')
    result['trust_status']='NOT VERIFIED: use Codex /hooks to review exact definitions. Configuration presence does not prove execution.'
    result['quota_support']='Requires an account-supported rate-limit read. API-key-only, third-party providers, offline sessions or managed policy may make it unknown. File checkpoints remain usable.'
    result['cloud_support']='Local command hooks do not imply cloud-orchestrated hook support. Deploy on the actual local execution host; verify its /hooks output.'
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--home',default=os.environ.get('CODEX_HOME',str(Path.home()/'.codex')));a=p.parse_args()
    print(json.dumps(diagnose(a.home),ensure_ascii=False,indent=2))
