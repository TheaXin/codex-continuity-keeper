#!/usr/bin/env python3
"""Verify ZIP bytes and all source entries without extracting or executing code."""
import argparse,hashlib,json,stat,zipfile
from pathlib import Path,PurePosixPath

def verify(archive,manifest):
    archive=Path(archive);m=json.loads(Path(manifest).read_text(encoding='utf-8'))
    if archive.name!=m['archive'] or hashlib.sha256(archive.read_bytes()).hexdigest()!=m['archive_sha256']:raise ValueError('Archive checksum mismatch')
    prefix='codex-continuity-keeper-'+m['version']+'/'
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist();names=[i.filename for i in entries]
        if len(names)!=len(set(names)) or sum(i.file_size for i in entries)>16*1024*1024:raise ValueError('Duplicate entries or excessive archive size')
        actual={}
        for i in entries:
            p=PurePosixPath(i.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in i.filename or not i.filename.startswith(prefix):raise ValueError('Unsafe archive path')
            if stat.S_ISLNK(i.external_attr>>16) or i.flag_bits&1:raise ValueError('Symlink or encrypted entry')
            rel=i.filename[len(prefix):];actual[rel]=hashlib.sha256(z.read(i)).hexdigest()
        if actual!=m['files_sha256']:raise ValueError('Source content manifest mismatch')
    return {'status':'PASS','version':m['version'],'verified_files':len(actual),'integrity_only':'Checksums do not substitute for reviewing or authenticating the publisher'}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive');p.add_argument('--manifest',required=True);a=p.parse_args();print(json.dumps(verify(a.archive,a.manifest),indent=2))
