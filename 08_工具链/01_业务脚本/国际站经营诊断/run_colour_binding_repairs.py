"""Execute only reviewed exact-ID colour-image repairs, with durable once ledgers."""
from pathlib import Path
import argparse,sys,subprocess
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s

def main():
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode',choices=['execute','verify','sync']);a=ap.parse_args()
    indexfile=s.BASE/'颜色绑定修正.json';index=s.load(indexfile);logs=s.RAW/'颜色绑定批次日志';results=[]
    for group in index['groups']:
        folder=s.BASE/'配色与尺码修正'/group['key'];plan=s.load(folder/'计划.json')
        assert plan['reviewed']and plan['reviewer']=='active_agent'and set(group['ids'])<=set(plan['ids'])
        assert plan.get('rebind_images')and not plan.get('add')and not plan.get('restrict')
        ids=[pid for pid in group['ids']if(folder/'商品'/pid/'update_once.json').exists()]
        if a.mode=='execute':ids=[pid for pid in group['ids']if pid not in ids]
        if a.mode=='verify':ids=[pid for pid in ids if not(folder/'商品'/pid/'verification.json').exists()or s.load(folder/'商品'/pid/'verification.json')['state']!='FORMAL_FIELDS_SCORE_PASS']
        if a.mode=='sync':ids=[pid for pid in ids if(folder/'商品'/pid/'verification.json').exists()and s.load(folder/'商品'/pid/'verification.json')['state']=='FORMAL_FIELDS_SCORE_PASS']
        row={'key':group['key'],'at':s.now(),'ids':ids,'phases':[]};results.append(row)
        for mode in (['prepare','submit']if a.mode=='execute'else[a.mode]):
            if not ids:break
            cmd=[sys.executable,str(Path(__file__).parent/'repair_source_assortment.py'),mode,'--family',group['key'],'--ids',','.join(ids)]
            r=subprocess.run(cmd,cwd=s.ROOT,capture_output=True,timeout=900)
            logs.mkdir(parents=True,exist_ok=True);(logs/(group['key']+'_'+mode+'.stdout.txt')).write_bytes(r.stdout);(logs/(group['key']+'_'+mode+'.stderr.txt')).write_bytes(r.stderr)
            row['phases'].append({'mode':mode,'returncode':r.returncode,'state':'COMMAND_COMPLETED_READ_EVIDENCE'if r.returncode==0 else'ERROR_NO_AUTOMATIC_REPLAY'})
            index.setdefault('phase_runs',{})[a.mode]={'at':s.now(),'groups':results};s.save(indexfile,index)
            print(group['key'],mode,'rc',r.returncode,'ids',len(ids),flush=True)
            if r.returncode:break
    current=[]
    for group in index['groups']:
        for pid in group['ids']:
            f=s.BASE/'配色与尺码修正'/group['key']/'商品'/pid/'verification.json'
            r=s.load(f)if f.exists()else{'state':'NOT_VERIFIED'}
            current.append({'id':pid,'key':group['key'],'state':r['state'],'failed':r.get('failed',[]),'verification':s.rel(f)if f.exists()else None})
    index['current_ids']=current;index['at']=s.now();s.save(indexfile,index)

if __name__=='__main__':main()
