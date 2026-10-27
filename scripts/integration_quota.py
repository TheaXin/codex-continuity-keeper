import os,sys,tempfile,subprocess,json,threading,queue,time,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import keeper, quota, shlex
from install import install
from http.server import BaseHTTPRequestHandler,HTTPServer
request_count=0
class Fixture(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_POST(self):
  global request_count
  body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0)))); request_count+=1
  names=[t.get('name') for t in body.get('tools',[])]; out['model_tool_names']=names
  out['hook_reminder_in_model_request']='Continuity Keeper active' in json.dumps(body)
  if request_count==1 and 'exec_command' in names:
   program="import sys,pathlib; sys.path.insert(0,"+repr(str(pathlib.Path(keeper.__file__).parent))+"); import quota; p=pathlib.Path.cwd(); (p/'host-tool.txt').write_text('verified local artifact'); quota.observe(p,{'rateLimits':{'limitId':'codex','primary':{'usedPercent':95}}},source='ISOLATED_TEST_FIXTURE')"
   item={'type':'function_call','id':'fc_ck2','call_id':'call_ck2','name':'exec_command','arguments':json.dumps({'cmd':shlex.quote(sys.executable)+' -c '+shlex.quote(program),'max_output_tokens':100})}
  elif request_count==2:
   out['low_handoff_reached_model']='LOW_QUOTA_HANDOFF' in json.dumps(body)
   program="import sys,pathlib; sys.path.insert(0,"+repr(str(pathlib.Path(keeper.__file__).parent))+"); import keeper; p=pathlib.Path.cwd(); (p/'PROGRESS.md').write_text('Verified: host-tool.txt exists. Unfinished: unit two. Next: resume unit two after quota reset.'); (p/'CONTINUITY_TASKS.md').write_text('- [x] verified local artifact\\n- [ ] unit two\\n'); keeper.checkpoint(p,'low-quota-final')"
   item={'type':'function_call','id':'fc_save','call_id':'call_save','name':'exec_command','arguments':json.dumps({'cmd':shlex.quote(sys.executable)+' -c '+shlex.quote(program),'max_output_tokens':100})}
  else:
   item={'type':'message','id':'msg_ck2','role':'assistant','status':'completed','content':[{'type':'output_text','text':'已有成果：host-tool.txt。未完成：unit two。恢复方法：额度恢复后在原项目说继续。','annotations':[]}]}
  result={'id':'resp_ck2_'+str(request_count),'object':'response','status':'completed','output':[item],'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}
  events=[{'type':'response.output_item.done','output_index':0,'item':item},{'type':'response.completed','response':result}]
  data=''.join('data: '+json.dumps(e)+'\n\n' for e in events).encode()
  self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
pathlib.Path('work').mkdir(exist_ok=True)
out={}
server=HTTPServer(('127.0.0.1',0),Fixture); threading.Thread(target=server.serve_forever,daemon=True).start()
with tempfile.TemporaryDirectory(prefix='ck2-host-') as temp:
 base=pathlib.Path(temp).resolve(); home=pathlib.Path(os.environ.get('CODEX_HOME',str(pathlib.Path.home()/'.codex'))); project=base/'project'; project.mkdir(); keeper.init(project)
 quota.observe(project,{'rateLimits':{'primary':{'usedPercent':10}}},source='ISOLATED_TEST_FIXTURE')
 # Installed definitions were reviewed and trusted through official /hooks TUI.
 (project/'host-proof.txt').write_text('written before real SessionStart\n')
 env={**os.environ,'CODEX_HOME':str(home)}
 log=open('work/quota-host-stderr.txt','w')
 p=subprocess.Popen(['codex','app-server','--stdio'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,env=env)
 q=queue.Queue(); messages=[]
 def read():
  for line in p.stdout:
   try:q.put(json.loads(line))
   except ValueError:pass
 threading.Thread(target=read,daemon=True).start()
 def send(method,params,ident=None):
  d={'jsonrpc':'2.0','method':method,'params':params}
  if ident is not None:d['id']=ident
  p.stdin.write(json.dumps(d)+'\n');p.stdin.flush()
 def receive(ident):
  until=time.monotonic()+30
  while time.monotonic()<until:
   try:d=q.get(timeout=1)
   except queue.Empty:continue
   messages.append(d)
   if d.get('id')==ident:return d
  raise TimeoutError(str(ident))
 try:
  send('initialize',{'clientInfo':{'name':'continuity-integration-test','version':'2.0'},'capabilities':{'experimentalApi':True}},1); receive(1)
  send('initialized',{})
  send('hooks/list',{'cwds':[str(project)]},2); hooks=receive(2)
  out['hooks_list']=hooks
  send('thread/start',{'cwd':str(project),'ephemeral':True,'approvalPolicy':'never','sandbox':'workspace-write','model':'ck2-fixture','modelProvider':'ck2local','config':{'model_providers.ck2local':{'name':'Local test fixture','base_url':'http://127.0.0.1:'+str(server.server_port)+'/v1','wire_api':'responses','requires_openai_auth':False}}},3); result=receive(3)
  out['thread_start_ok']='result' in result
  if 'error' in result: out['start_error']=result['error']
  thread_id=result.get('result',{}).get('thread',{}).get('id')
  if thread_id:
   send('turn/start',{'threadId':thread_id,'input':[{'type':'text','text':'Run only the local integration fixture.'}]},4); receive(4)
  end=time.monotonic()+25
  while time.monotonic()<end:
   try:
    d=q.get(timeout=.1); messages.append(d)
    if d.get('method')=='turn/completed':break
   except queue.Empty:pass
   time.sleep(.1)
  out['actual_session_start_captured_file']='host-proof.txt' in keeper.load(project/keeper.STATE/'latest.json')['files']
  out['actual_tool_write_captured']='host-tool.txt' in keeper.load(project/keeper.STATE/'latest.json')['files']
  out['emergency_index_exists']=(project/keeper.STATE/'QUOTA_HANDOFF.md').is_file()
  out['semantic_handoff_saved']='Unfinished: unit two' in (project/'PROGRESS.md').read_text()
  out['handoff_in_snapshot']='PROGRESS.md' in keeper.load(project/keeper.STATE/'latest.json')['files']
  out['latest_event']=keeper.load(project/keeper.STATE/'latest.json')['event']
  out['hook_notifications']=[x for x in messages if 'hook' in x.get('method','').lower()]
 finally:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill()
  log.close()
pathlib.Path('work/quota-host-result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({'low_handoff_reached_model':out.get('low_handoff_reached_model'),'semantic_handoff_saved':out.get('semantic_handoff_saved'),'emergency_index_exists':out.get('emergency_index_exists'),'thread_start_ok':out.get('thread_start_ok'),'actual_session_start_captured_file':out.get('actual_session_start_captured_file'),'latest_event':out.get('latest_event'),'actual_tool_write_captured':out.get('actual_tool_write_captured'),'hook_reminder_in_model_request':out.get('hook_reminder_in_model_request'),'hook_events':[x.get('params',{}).get('eventName',x.get('method')) for x in out.get('hook_notifications',[])],'start_error':out.get('start_error'),'hooks':[{k:h.get(k) for k in ['eventName','enabled','trustStatus']} for d in out.get('hooks_list',{}).get('result',{}).get('data',[]) for h in d.get('hooks',[])],'warnings':[d.get('warnings') for d in out.get('hooks_list',{}).get('result',{}).get('data',[])]},ensure_ascii=False,indent=2))

assert out.get('actual_session_start_captured_file') and out.get('actual_tool_write_captured') and out.get('hook_reminder_in_model_request'), 'Host integration did not pass'

assert out.get('low_handoff_reached_model') and out.get('semantic_handoff_saved') and out.get('emergency_index_exists'), 'Quota handoff integration did not pass'
