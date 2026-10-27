#!/usr/bin/env python3
"""Selective, backed-up uninstall. Preview by default; never delete project state."""
import argparse,json,os,shlex,sys,time
from pathlib import Path
from keeper import atomic,encoded,locked
from install import RULE,QUOTA_RULE

def uninstall(home,apply=False):
    home=Path(home).expanduser().resolve(); dest=home/'skills'/'codex-continuity-keeper'; hp=home/'hooks.json'; ap=home/'AGENTS.md'
    target=str(dest/'scripts'/'keeper.py')
    for p in [dest,hp,ap]:
        if p.is_symlink():raise ValueError('Refusing symlink: '+str(p))
    hooks=json.loads(hp.read_text(encoding='utf-8')) if hp.exists() else {'hooks':{}}
    removed=0
    for event,groups in list(hooks.get('hooks',{}).items()):
        kept=[]
        for group in groups:
            handlers=[]
            for h in group.get('hooks',[]):
                # Match a quoted argument exactly; do not remove unrelated commands containing the same substring.
                try: args=shlex.split(h.get('command',''))
                except ValueError:args=[]
                if target in args and args[-1:] == ['hook']:removed+=1
                else:handlers.append(h)
            if handlers:kept.append({**group,'hooks':handlers})
        if kept:hooks['hooks'][event]=kept
        else:hooks['hooks'].pop(event,None)
    original=ap.read_text(encoding='utf-8') if ap.exists() else ''; text=original
    for block in [RULE,QUOTA_RULE]:text=text.replace(block,'')
    result={'apply':apply,'hooks_to_remove':removed,'skill_to_archive':dest.exists(),'project_checkpoints':'untouched','edited_rule_blocks':'Preserved if they differ from exact installer text'}
    if not apply:return result
    with locked(home/'continuity-keeper-install'):
        backup=home/'continuity-keeper-install'/('uninstall-'+str(time.time_ns()));backup.mkdir(mode=0o700)
        for p in [hp,ap]:
            if p.exists():atomic(backup/p.name,p.read_bytes())
        if hp.exists() and removed:atomic(hp,encoded(hooks))
        if ap.exists() and text!=original:atomic(ap,text.encode('utf-8'))
        if dest.exists():os.rename(dest,backup/'skill')
        result['backup']=str(backup)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--home',default=os.environ.get('CODEX_HOME',str(Path.home()/'.codex')));p.add_argument('--apply',action='store_true');a=p.parse_args()
    print(json.dumps(uninstall(a.home,a.apply),ensure_ascii=False,indent=2))
