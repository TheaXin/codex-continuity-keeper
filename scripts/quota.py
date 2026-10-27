#!/usr/bin/env python3
"""Read-only official account API, bounded polling, no credentials/transcripts persisted."""
import json, math, os, queue, shutil, subprocess, threading, time
from pathlib import Path
from keeper import atomic, encoded, load, locked, state, stamp

INTERVAL=30
TIMEOUT=7
THRESHOLD=5

def windows_from(raw,now=None):
    now=time.time() if now is None else now
    if not isinstance(raw,dict): return []
    if isinstance(raw.get('result'),dict): raw=raw['result']
    if isinstance(raw.get('content'),list):
        for item in raw['content']:
            if item.get('type')=='text':
                try: return windows_from(json.loads(item['text']),now)
                except (ValueError,TypeError): pass
        return []
    buckets=raw.get('rateLimitsByLimitId')
    if not isinstance(buckets,dict) or not buckets:
        one=raw.get('rateLimits'); buckets={str(one.get('limitId') or 'codex'):one} if isinstance(one,dict) else {}
    out=[]
    for bucket,limit in buckets.items():
        if not isinstance(limit,dict): continue
        for name in ['primary','secondary']:
            w=limit.get(name)
            if not isinstance(w,dict): continue
            used=w.get('usedPercent'); reset=w.get('resetsAt')
            if isinstance(used,bool) or not isinstance(used,(int,float)) or not math.isfinite(used) or not 0<=used<=100: continue
            if reset is not None and (isinstance(reset,bool) or not isinstance(reset,(int,float)) or not math.isfinite(reset) or reset<=now): continue
            out.append({'bucket':str(bucket)[:80],'window':name,'remainingPercent':100-used,'resetsAt':reset,'windowDurationMins':w.get('windowDurationMins')})
    return out

def fetch_limits(timeout=TIMEOUT):
    """Spawn an account-only stdio client; never start a thread or model turn."""
    executable=os.environ.get('CODEX_CLI_PATH') or shutil.which('codex')
    if not executable: raise RuntimeError('codex executable unavailable')
    argv=[executable,'app-server','--stdio']
    if os.name=='nt' and Path(executable).suffix.lower() in {'.cmd','.bat'}:
        argv=[os.environ.get('COMSPEC','cmd.exe'),'/d','/s','/c',subprocess.list2cmdline(argv)]
    p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
    q=queue.Queue(maxsize=64); deadline=time.monotonic()+timeout
    def reader():
        try:
            for line in p.stdout:
                try: item=json.loads(line)
                except ValueError: continue
                try:q.put_nowait(item)
                except queue.Full: break
        except (OSError,ValueError): pass
    t=threading.Thread(target=reader,daemon=True); t.start()
    def send(i,method,params):
        message={'method':method,'params':params}
        if i is not None: message['id']=i
        p.stdin.write(json.dumps(message)+'\n'); p.stdin.flush()
    def receive(i):
        while time.monotonic()<deadline:
            try: item=q.get(timeout=min(.15,max(.01,deadline-time.monotonic())))
            except queue.Empty:
                if p.poll() is not None: raise RuntimeError('account server exited')
                continue
            if item.get('id')==i:
                if 'error' in item: raise RuntimeError('account read unavailable')
                return item.get('result',{})
        raise TimeoutError('account read timed out')
    try:
        send(1,'initialize',{'clientInfo':{'name':'continuity-quota-guard','version':'2.1'}}); receive(1)
        send(None,'initialized',{})
        send(2,'account/rateLimits/read',{})
        return receive(2)
    finally:
        p.terminate()
        try:p.wait(timeout=.5)
        except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=.5)
        for stream in [p.stdin,p.stdout]:
            try:stream.close()
            except (OSError,ValueError):pass

def effective(record,now=None):
    now=time.time() if now is None else now
    out=dict(record)
    valid=[w for w in record.get('windows',[]) if w.get('resetsAt') is None or w['resetsAt']>now]
    out['lowWindows']=[w for w in valid if w['remainingPercent']<=THRESHOLD]
    out['low']=bool(out['lowWindows'])
    out['stale']=now-record.get('observedAt',0)>INTERVAL
    return out

def observe(root,raw,now=None,source='official-account-read'):
    """Persist only normalized percentages and timestamps, never raw account payloads."""
    now=time.time() if now is None else now
    s=state(root)
    with locked(s): return _store(s,raw,now,source)

def _store(s,raw,now,source):
    old=load(s/'quota.json',{}); windows=windows_from(raw,now)
    if windows:
        # Missing windows do not prove a previously low window has recovered.
        keys={(w['bucket'],w['window']) for w in windows}
        windows += [w for w in effective(old,now).get('lowWindows',[]) if (w['bucket'],w['window']) not in keys]
        record={'version':1,'observedAt':now,'checkedAt':now,'source':source,'status':'known','windows':windows}
    else:
        record={**old,'checkedAt':now,'status':'unknown','reason':'No valid usage windows available'}
    record=effective(record,now)
    atomic(s/'quota.json',encoded(record))
    if record['low']:
        atomic(s/'QUOTA_HANDOFF.md',('# Low quota emergency index\n\nDetected: '+stamp()+'\n\nOne or more observed quota windows have <=5% remaining.\nThis is a mechanical index, NOT a semantic completion report.\n\n- Actual artifacts: inspect the project files and outputs/ if present.\n- Verified progress: ../PROGRESS.md (may lag the last operation).\n- Unfinished work: ../CONTINUITY_TASKS.md.\n- File checkpoint: latest.json and snapshots/ (filtered files are not protected).\n- Recovery: after quota resets, say 继续 in this project; inspect current files and Git differences before resuming.\n- Do not start a new implementation unit. Save a short verified handoff and deliver paths/results now.\n').encode())
    return record

def check(root,force=False):
    s=state(root)
    if not (s/'project.json').is_file(): return {'status':'disabled','low':False}
    # Separate lock so network waits never hold the snapshot lock.
    with locked(s/'quota-guard'):
        old=load(s/'quota.json',{}); now=time.time()
        if not force and 0<=now-old.get('checkedAt',0)<INTERVAL: return effective(old,now)
        try: raw=fetch_limits()
        except (OSError,RuntimeError,TimeoutError,subprocess.SubprocessError): raw={}
        return observe(root,raw)

def read_only_request(payload):
    if payload.get('prompt','').strip()=='只看进度': return True
    command=payload.get('tool_input',{}).get('command','') if isinstance(payload.get('tool_input'),dict) else ''
    if isinstance(command,str) and 'keeper.py' in command and re_status(command): return True
    # Read only a bounded transcript tail to honor a status-only turn. Never store its text.
    path=payload.get('transcript_path')
    if not path: return False
    try:
        with open(path,'rb') as f:
            f.seek(0,2); f.seek(max(0,f.tell()-131072)); lines=f.read(131072).splitlines()
        for line in reversed(lines):
            try: item=json.loads(line)
            except ValueError: continue
            p=item.get('payload',{})
            if not isinstance(p,dict): continue
            if item.get('type')=='event_msg' and p.get('type')=='user_message': return str(p.get('message','')).strip()=='只看进度'
            if p.get('role')=='user':
                parts=p.get('content',[])
                text=''.join(v.get('text','') for v in parts if isinstance(v,dict)) if isinstance(parts,list) else str(parts)
                return text.strip()=='只看进度'
    except (OSError,TypeError): pass
    return False

def re_status(command):
    import re
    return bool(re.search(r'\bstatus\s*(?:$|[|;])',command))

def feedback(record):
    if record.get('low'):
        values=', '.join(w['bucket']+'/'+w['window']+' remaining '+str(w['remainingPercent'])+'%' for w in record['lowWindows'])
        return 'LOW_QUOTA_HANDOFF: '+values+'. Stop starting implementation units now. Immediately save current real artifacts, briefly update verified PROGRESS.md and CONTINUITY_TASKS.md, checkpoint, then FINAL reply with 已有成果(absolute paths), 未完成/未验证, and 恢复方法(额度恢复后在原项目说继续). Do not launch lengthy tests, new agents, automatic resets, or extra research. Do not claim unfinished work is done. Snapshot index: .continuity-keeper/QUOTA_HANDOFF.md.'
    if record.get('status')=='unknown':
        return 'Quota Guard: usage could not be read; do not assume quota is sufficient. Before the next expensive operation, use get_usage_limits if available and record its real result via keeper.py quota-record. Continue normal small durable checkpoints; no repeated polling loop.'
    return ''
