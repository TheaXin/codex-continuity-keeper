#!/usr/bin/env python3
"""Offline acceptance of an installed copy. Never changes the real Codex home."""
import argparse, hashlib, json, os, platform, subprocess, sys, tempfile
from pathlib import Path
from install import install
from manifest import manifest

def run_acceptance(source=None, workspace=None):
    source=Path(source or Path(__file__).resolve().parents[1]).resolve()
    if workspace is None:
        with tempfile.TemporaryDirectory(prefix='ck-acceptance-') as temp:
            return _run(source,Path(temp).resolve(),retained=False)
    workspace=Path(workspace).expanduser().resolve()
    if workspace==source or source in workspace.parents:
        raise ValueError('Choose a NEW workspace outside the source checkout')
    workspace.mkdir(parents=True,exist_ok=False)
    return _run(source,workspace,retained=True)

def _run(source,base,retained):
    steps=[]; home=base/'isolated codex home'; project=base/'demo project'; project.mkdir()
    def passed(name,evidence):steps.append({'name':name,'status':'PASS','evidence':evidence})
    # Seed unrelated configuration to check preservation, rather than installing into a blank home only.
    home.mkdir();(home/'AGENTS.md').write_text('Acceptance fixture: preserve this rule.\n',encoding='utf-8')
    (home/'config.toml').write_text('model = "acceptance-fixture"\n',encoding='utf-8')
    before=(home/'config.toml').read_bytes()
    installed=install(home,source)
    skill=Path(installed['skill']); keeper=skill/'scripts/keeper.py'
    assert manifest(skill)==manifest(source)
    assert (home/'config.toml').read_bytes()==before
    assert (home/'AGENTS.md').read_text(encoding='utf-8').startswith('Acceptance fixture: preserve this rule.')
    passed('isolated_install','Installed source hashes match; quota.py included; existing config/rule preserved')
    def cli(*args,input_data=None):
        r=subprocess.run([sys.executable,'-X','utf8',str(keeper),'--root',str(project),*args],input=json.dumps(input_data) if input_data is not None else None,capture_output=True,text=True,encoding='utf-8',timeout=30,env={**os.environ,'PYTHONUTF8':'1'})
        if r.returncode:raise RuntimeError('Installed CLI failed: '+r.stderr[-1000:])
        return json.loads(r.stdout)
    initial=cli('init');assert initial['changed']
    passed('initial_checkpoint','Installed CLI initialized progress, tasks and a readable initial snapshot')
    # A small real task, with explicit fixture-authored semantic notes. No model claims are fabricated.
    artifact=project/'result.json';artifact.write_text(json.dumps({'completed':['stage-one'],'total':2}),encoding='utf-8')
    (project/'PROGRESS.md').write_text('Verified stage one: result.json total=2.\nUnfinished: add 3 in stage two.\nNext: inspect result.json then run stage two.\n',encoding='utf-8')
    (project/'CONTINUITY_TASKS.md').write_text('- [x] stage one: total=2 verified\n- [ ] stage two: total=5\n',encoding='utf-8')
    cp=cli('checkpoint');assert cp['changed']
    saved=json.loads((project/'.continuity-keeper/latest.json').read_text(encoding='utf-8'))
    assert 'result.json' in saved['files']
    expected=artifact.read_bytes();obj=project/'.continuity-keeper/objects'/saved['files']['result.json']['sha256']
    assert obj.read_bytes()==expected
    passed('unit_saved','Actual artifact bytes match the content-addressed snapshot')
    assert not cli('checkpoint')['changed']
    passed('deduplication','Unchanged files create no additional snapshot')
    # Each cli() is a NEW OS process; no Python in-memory state is shared across recovery.
    before_status={p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}
    status=cli('status')
    after_status={p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}
    assert before_status==after_status and status['drift']==[]
    assert 'stage two' in status['documents']['progress']
    passed('fresh_process_read_only_resume','Fresh process reads the pending step and status makes zero file-content changes')
    artifact.unlink() # Simulated loss ONLY inside this newly created fixture workspace.
    recovered=base/'exported snapshot';cli('export',cp['id'],str(recovered))
    assert not artifact.exists() and (recovered/'result.json').read_bytes()==expected
    passed('non_overwriting_recovery','Snapshot exports to a NEW directory; the live missing file is not silently overwritten')
    artifact.write_bytes((recovered/'result.json').read_bytes())
    continuation=project/'continue_demo.py'
    continuation.write_text("import json,pathlib\np=pathlib.Path('result.json')\nd=json.loads(p.read_text(encoding='utf-8'))\nassert d['total']==2\nd['total']+=3; d['completed'].append('stage-two')\np.write_text(json.dumps(d),encoding='utf-8')\n",encoding='utf-8')
    subprocess.run([sys.executable,'-X','utf8',str(continuation)],cwd=project,check=True,timeout=10)
    assert json.loads(artifact.read_text(encoding='utf-8'))['total']==5
    (project/'PROGRESS.md').write_text('Verified stage one and stage two: actual result.json total=5.\nNo unfinished demo work.\n',encoding='utf-8')
    (project/'CONTINUITY_TASKS.md').write_text('- [x] stage one verified\n- [x] stage two total=5 verified\n',encoding='utf-8')
    final_cp=cli('checkpoint');assert cli('status')['drift']==[]
    passed('continued_and_verified','A separate continuation process finishes total=5; verified notes and final checkpoint saved')
    # Simulated quota is confined to this isolated project; does not query or mutate a real account.
    low=cli('quota-record',input_data={'rateLimits':{'limitId':'codex','primary':{'usedPercent':95}}})
    assert low['low'] and (project/'.continuity-keeper/QUOTA_HANDOFF.md').is_file()
    feedback=cli('hook',input_data={'cwd':str(project),'hook_event_name':'PostToolUse','tool_name':'Bash'})
    assert 'LOW_QUOTA_HANDOFF' in feedback['hookSpecificOutput']['additionalContext']
    passed('quota_guard_boundary','Simulated 95% used -> 5% remaining produces emergency index and model-visible handoff instruction')
    unknown=cli('quota-record',input_data={});assert unknown['status']=='unknown'
    passed('quota_unknown','An unavailable read is explicitly unknown, never fabricated sufficient quota')
    report={'version':(source/'VERSION').read_text(encoding='utf-8').strip(),'platform':platform.system(),'python':platform.python_version(),'status':'PASS','steps':steps,'final_artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'runtime_hooks_trust':'NOT TESTED: review /hooks on the real execution host','live_quota_account':'NOT TESTED: isolated simulated fixture, no account or model calls','semantic_notes':'Written and verified by deterministic test fixture; not a remote-model compliance test','workspace_retained':retained}
    if retained:report['workspace']=str(base)
    return report

def save_report(path,report):
    path=Path(path)
    with path.open('x',encoding='utf-8') as f:f.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report');a=p.parse_args()
    report=run_acceptance()
    if a.report:save_report(a.report,report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
