"""Read-only compact status for explicitly supplied local WorkBuddy task dirs."""
from pathlib import Path
import json,ctypes,time,sys
kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.restype=ctypes.c_void_p
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
def live(pid):
 h=kernel.OpenProcess(0x1000,False,pid)
 if not h:return {'pid':pid,'live':False,'observation':'process absent' if ctypes.get_last_error()==87 else 'not observable','winerror':ctypes.get_last_error()}
 c=ctypes.c_ulong();ok=kernel.GetExitCodeProcess(ctypes.c_void_p(h),ctypes.byref(c));kernel.CloseHandle(ctypes.c_void_p(h))
 return {'pid':pid,'live':bool(ok and c.value==259),'exitCode':c.value if ok else None}
for arg in sys.argv[1:]:
 d=Path(arg).resolve();resume=(d/'resume_started.json').exists();prefix='resume' if resume else 'runner'
 start=d/(prefix+'_started.json');finish=d/(prefix+'_finished.json');proc=d/(prefix+'_process.json');log=d/('resume_stream.jsonl' if resume else 'workbuddy_stream.jsonl')
 j={'task':d.name,'mode':prefix,'finished':read(finish) if finish.exists() else None}
 if start.exists():j['elapsedSeconds']=round(time.time()-read(start)['started_epoch'],1)
 if proc.exists():j['process']=live(read(proc)['pid'])
 events=[]
 if log.exists():
  for line in log.read_text(encoding='utf-8',errors='replace').splitlines():
   try:e=json.loads(line)
   except ValueError:continue
   if e.get('type')=='result':events.append({'type':'result','is_error':e.get('is_error'),'text':str(e.get('result',''))[-700:]})
   for c in e.get('message',{}).get('content',[]) if isinstance(e.get('message',{}).get('content'),list) else []:
    if c.get('type')=='tool_use':events.append({'type':'tool','name':c.get('name')})
  j['lastEvents']=events[-4:]
 j['outputs']=[f.name for f in d.iterdir() if f.is_file() and not f.name.startswith(('runner_','resume_','workbuddy_'))]
 print(json.dumps(j,ensure_ascii=False))
