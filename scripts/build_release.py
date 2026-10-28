#!/usr/bin/env python3
"""Build a deterministic source ZIP and integrity manifest from a strict allowlist."""
import argparse,hashlib,json,re,stat,zipfile
from pathlib import Path
ROOT_FILES={'README.md','SKILL.md','DESIGN_AND_PROMPTS.zh-CN.md','LICENSE','VERSION','.gitignore','CHANGELOG.md'}
SOURCE_DIRS={'scripts','agents','references','docs','.github'}
def source_files(root):
    root=Path(root).resolve();result={}
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root)
        if p.is_symlink():
            if rel.parts[0] in SOURCE_DIRS or rel.as_posix() in ROOT_FILES:raise ValueError('Refuse symlink source: '+rel.as_posix())
            continue
        if not p.is_file() or '__pycache__' in rel.parts:continue
        if rel.as_posix() not in ROOT_FILES and not (rel.parts[0] in SOURCE_DIRS and p.suffix in {'.py','.md','.yaml','.yml'}):continue
        data=p.read_bytes();data.decode('utf-8')
        result[rel.as_posix()]=data
    for name in ['VERSION','SKILL.md','LICENSE','scripts/install.py','scripts/quota.py','scripts/acceptance.py','scripts/demo_recovery.py']:
        if name not in result:raise ValueError('Required release source missing: '+name)
    return result

def build(root,output):
    root=Path(root).resolve();files=source_files(root);version=files['VERSION'].decode().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('VERSION must be numeric major.minor.patch')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    prefix='codex-continuity-keeper-'+version;archive=output/(prefix+'.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
        for rel,data in files.items():
            info=zipfile.ZipInfo(prefix+'/'+rel,date_time=(2020,1,1,0,0,0));info.create_system=3
            info.external_attr=(stat.S_IFREG|0o644)<<16;info.compress_type=zipfile.ZIP_STORED
            z.writestr(info,data,compress_type=zipfile.ZIP_STORED)
    manifest={'version':version,'archive':archive.name,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in files.items()}}
    mp=output/'release-manifest.json';mp.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    (output/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in [archive,mp]),encoding='utf-8')
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(build(a.source,a.output),indent=2))
