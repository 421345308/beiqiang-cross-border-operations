"""Run only the 43 reviewed exact-image repairs; never retry a write ledger."""
from pathlib import Path
import argparse,json,subprocess,sys
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s

def main():
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['execute','verify','sync']);ap.add_argument('--corrections',action='store_true');a=ap.parse_args();index=s.BASE/'EU尺码图执行.json';data=s.load(index);assert data['state']in('ALL_14_DATA_AND_VISUAL_REVIEWED','EXECUTION_RECORDED');script=Path(__file__).with_name('repair_reviewed_gallery.py');rows=[]
    selected=[{'key':r['key'],'ids':[r['id']]}for r in data.get('reviewed_followup_corrections',[])]if a.corrections else data['groups']
    for group in selected:
        key=group['key'];base=s.BASE/'图库重做'/key;plan=s.load(base/'计划.json');assert plan['reviewed']is True and plan['reviewer']=='active_agent';out=s.ROOT/'99_临时区/商品质量全店复核/历史尺码图/执行'/key;out.mkdir(parents=True,exist_ok=True)
        modes=['bank','prepare','submit']if a.mode=='execute'else[a.mode];row={'key':key,'at':s.now(),'phases':[]}
        for mode in modes:
            ids=plan['ids']
            if mode in('prepare','submit'):ids=[pid for pid in ids if not(base/'商品'/pid/'update_once.json').exists()]
            if mode=='submit':ids=[pid for pid in ids if(base/'商品'/pid/'prepared.json').exists()]
            if mode=='verify':ids=[pid for pid in ids if(base/'商品'/pid/'update_once.json').exists()]
            if mode=='sync':ids=[pid for pid in ids if(base/'商品'/pid/'verification.json').exists()and s.load(base/'商品'/pid/'verification.json')['state']=='FORMAL_FIELDS_SCORE_PASS']
            if mode!='bank'and not ids:row['phases'].append({'mode':mode,'state':'NO_UNATTEMPTED_OR_ACCEPTED_IDS'});continue
            cmd=[sys.executable,str(script),mode,'--family',key]
            if mode!='bank':cmd+=['--ids',','.join(ids)]
            result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf8');(out/(mode+'_stdout.txt')).write_text(result.stdout,encoding='utf8');(out/(mode+'_stderr.txt')).write_text(result.stderr,encoding='utf8');row['phases'].append({'mode':mode,'returncode':result.returncode,'ids':ids,'state':'COMMAND_COMPLETED_READ_EVIDENCE'if result.returncode==0 else'FAILED_NO_AUTOMATIC_RETRY'})
            if result.returncode:break
        rows.append(row);print(json.dumps({'key':key,'last_phase':row['phases'][-1]},ensure_ascii=False),flush=True)
    data['state']='EXECUTION_RECORDED';data.setdefault('phase_runs',{})[a.mode+('_corrections'if a.corrections else'')]={'at':s.now(),'rows':rows};summary=[];corrections={r['id']:r['key']for r in data.get('reviewed_followup_corrections',[])}
    for group in data['groups']:
        for pid in group['ids']:
            key=group['key']
            if pid in corrections and(s.BASE/'图库重做'/corrections[pid]/'商品'/pid/'update_once.json').exists():key=corrections[pid]
            folder=s.BASE/'图库重做'/key/'商品'/pid;v=folder/'verification.json';l=folder/'update_once.json';summary.append({'id':pid,'key':key,'state':s.load(v)['state']if v.exists()else s.load(l)['state']if l.exists()else'NOT_SUBMITTED','verification':s.rel(v)if v.exists()else None})
    data['current_ids']=summary;s.save(index,data)

if __name__=='__main__':main()
