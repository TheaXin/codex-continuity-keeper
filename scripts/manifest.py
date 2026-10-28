#!/usr/bin/env python3
"""Create a reviewable hash baseline for an installed skill; does not update it."""
import argparse,hashlib,json,os
from pathlib import Path
IGNORED={'__pycache__','.git','.continuity-keeper','work','.venv','dist','build'}
def manifest(skill):
    skill=Path(skill).expanduser().resolve()
    if not (skill/'SKILL.md').is_file():raise ValueError('Select an existing skill containing SKILL.md')
    files={}
    for p in sorted(skill.rglob('*')):
        if p.is_file() and not any(x in p.relative_to(skill).parts for x in IGNORED):
            if p.is_symlink():raise ValueError('Review symlink before creating baseline')
            files[p.relative_to(skill).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return {'files_sha256':files}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--skill',default=str(Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'/'codex-continuity-keeper'));a=p.parse_args()
    print(json.dumps(manifest(a.skill),indent=2))
