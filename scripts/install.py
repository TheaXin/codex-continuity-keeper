#!/usr/bin/env python3
"""Reviewed first-party local installer. No downloads, shell eval, trust bypass or config replacement."""
import argparse, hashlib, json, os, shlex, shutil, subprocess, sys, time, tomllib
from pathlib import Path
from keeper import atomic, encoded, locked

RULE='''<!-- continuity-keeper-2:begin -->
For substantive long tasks, use codex-continuity-keeper: initialize a project checkpoint before edits; persist real files, verified PROGRESS.md and CONTINUITY_TASKS.md after each useful small unit. User task requirements take priority. On “继续”, read progress, actual files and Git differences; first report 已完成、正在进行、未完成、阻碍、下一步, then continue authorized unfinished work. “只看进度” is strictly read-only. Never infer completion from snapshots or rely on a final shutdown hook. Preserve user changes; no automatic reset/clean, whole-tree staging or remote push. Skill: ~/.codex/skills/codex-continuity-keeper/SKILL.md (or the active CODEX_HOME equivalent).
<!-- continuity-keeper-2:end -->
'''

QUOTA_RULE='<!-- continuity-quota-guard:begin -->\nDuring substantive long tasks, use Continuity Keeper Quota Guard at task start, after small work units, and before expensive operations. If any actual included quota window has <=5% remaining, stop starting implementation work, save real artifacts, briefly reconcile verified progress/task states, checkpoint, and immediately deliver existing artifact paths, unfinished/unverified work, and how to resume after quota resets. Prefer get_usage_limits when available; record only real tool results via keeper.py quota-record. Unknown quota is not sufficient quota. Do not auto-redeem resets. “只看进度” remains strictly read-only.\n<!-- continuity-quota-guard:end -->\n'

def install(home,source,upgrade_from=None):
    home=home.resolve(); source=source.resolve(); dest=home/'skills'/'codex-continuity-keeper'
    if home.is_symlink(): raise ValueError('refusing symlink home')
    home.mkdir(parents=True,exist_ok=True)
    with locked(home/'continuity-keeper-install'):
        config=home/'config.toml'; cfg=tomllib.loads(config.read_text(encoding='utf-8')) if config.exists() else {}
        if set(cfg.get('hooks',{}))-{'state'}: raise ValueError('Existing inline hooks: preserve configuration; merge manually after review')
        hp=home/'hooks.json'; old=hp.read_bytes() if hp.exists() else None
        hooks=json.loads(old) if old is not None else {'hooks':{}}
        if not isinstance(hooks.get('hooks'),dict): raise ValueError('invalid existing hooks')
        ap=home/'AGENTS.md'; agent_old=ap.read_bytes() if ap.exists() else None
        text=agent_old.decode() if agent_old is not None else ''
        if '<!-- continuity-keeper-2:begin -->' in text and RULE.strip() not in text: raise ValueError('Existing continuity rules differ; review before merging')
        if '<!-- continuity-quota-guard:begin -->' in text and QUOTA_RULE.strip() not in text: raise ValueError('Existing quota rules differ; review before merge')
        for p in [hp,ap,dest,home/'skills']:
            if p.is_symlink(): raise ValueError('Refusing symlink '+str(p))
        if dest.exists():
            # Idempotent only: no overwrite of a previous or user-edited skill.
            a={p.relative_to(source).as_posix():p.read_bytes() for p in source.rglob('*') if p.is_file() and not any(x in p.relative_to(source).parts for x in ['__pycache__','.git','.continuity-keeper','work','.venv'])}
            b={p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file() and not any(x in p.relative_to(dest).parts for x in ['__pycache__','.git','.continuity-keeper','work','.venv'])}
            if a!=b:
                if not upgrade_from: raise ValueError('Existing skill differs; preserve it and review upgrade explicitly')
                baseline=json.loads(Path(upgrade_from).read_text(encoding='utf-8-sig')).get('files_sha256',{})
                actual={k:hashlib.sha256(v).hexdigest() for k,v in b.items()}
                if not baseline or actual!=baseline: raise ValueError('Installed files differ from reviewed upgrade baseline; preserve user edits')
        command=shlex.quote(sys.executable)+' '+shlex.quote(str(dest/'scripts'/'keeper.py'))+' hook'
        for event in ['SessionStart','UserPromptSubmit','PostToolUse','PreCompact','Stop']:
            group={'hooks':[{'type':'command','command':command,'timeout':15,'statusMessage':'Saving continuity checkpoint','additionalContextLimit':1500}]}
            if os.name == 'nt': group['hooks'][0]['commandWindows']=subprocess.list2cmdline([sys.executable,'-X','utf8',str(dest/'scripts'/'keeper.py'),'hook'])
            if event in ['PreCompact','Stop']: group['hooks'][0].pop('additionalContextLimit')
            if event=='PostToolUse': group['matcher']='^(Bash|apply_patch|Edit|Write)$'
            groups=hooks['hooks'].setdefault(event,[])
            if group not in groups: groups.append(group)
        backup=home/'continuity-keeper-install'/('backup-'+str(time.time_ns()))
        backup.mkdir(mode=0o700)
        for n,b in [('hooks.json',old),('AGENTS.md',agent_old)]:
            if b is not None: atomic(backup/n,b)
        atomic(backup/'manifest.json',encoded({'time':time.time(),'absent_before':[n for n,b in [('hooks.json',old),('AGENTS.md',agent_old)] if b is None],'config_toml':'untouched','skill_existed':dest.exists()}))
        replacing=dest.exists() and a!=b
        if not dest.exists() or replacing:
            dest.parent.mkdir(parents=True,exist_ok=True)
            stage=dest.parent/('.continuity-stage-'+str(time.time_ns()))
            shutil.copytree(source,stage,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git','.continuity-keeper','work','.venv'))
            for p in (stage/'scripts').glob('*.py'): p.chmod(0o700)
            if replacing: os.rename(dest,backup/'skill')
            try: os.rename(stage,dest)
            except OSError:
                if replacing: os.rename(backup/'skill',dest)
                raise
        atomic(hp,encoded(hooks))
        if RULE.strip() not in text: text=(text.rstrip()+'\n\n'+RULE).lstrip()
        if QUOTA_RULE.strip() not in text: text=text.rstrip()+'\n\n'+QUOTA_RULE
        atomic(ap,text.encode())
        return {'skill':str(dest),'hooks':str(hp),'rules':str(ap),'backup':str(backup),'trust':'Review exact definitions using /hooks in a fresh Codex session; trust not forged','python':sys.executable}
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--home',default=os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))); p.add_argument('--upgrade-from',help='SHA-256 baseline JSON from the previously verified installation'); a=p.parse_args()
    print(json.dumps(install(Path(a.home),Path(__file__).resolve().parents[1],a.upgrade_from),ensure_ascii=False,indent=2))
