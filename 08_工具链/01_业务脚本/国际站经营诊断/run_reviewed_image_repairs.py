"""Run a reviewed image index with per-ID once ledgers and serial local sync."""
from pathlib import Path
import argparse,subprocess,sys,json
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s

def main():
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['execute','verify','sync']);ap.add_argument('--index',required=True);a=ap.parse_args()
    index=s.load(s.ROOT/a.index);groups=index['groups'];logs=s.RAW/'图片批次日志';logs.mkdir(parents=True,exist_ok=True);results=[]
    def run(family,mode,ids=None):
        args=[sys.executable,str(Path(__file__).parent/'repair_reviewed_gallery.py'),mode,'--family',family]
        if ids:args+=['--ids',','.join(ids)]
        stem=family+'_'+mode
        with (logs/(stem+'.stdout.txt')).open('a',encoding='utf8')as out,(logs/(stem+'.stderr.txt')).open('a',encoding='utf8')as err:
            done=subprocess.run(args,stdout=out,stderr=err)
        print(family,mode,done.returncode,flush=True);return done.returncode
    for group in groups:
        family=group['family'];folder=s.BASE/'图库重做'/family;plan=s.load(folder/'计划.json');ids=group.get('ids',plan['ids']);assert set(ids)<=set(plan['ids']);rc=0
        if a.mode=='execute':
            unattempted=[pid for pid in ids if not(folder/'商品'/pid/'update_once.json').exists()]
            if unattempted:
                rc=run(family,'bank')
                if not rc:rc=run(family,'prepare',unattempted)
                if not rc:rc=run(family,'submit',unattempted)
        else:
            selected=[]
            for pid in ids:
                target=folder/'商品'/pid;proof=s.load(target/'verification.json')if(target/'verification.json').exists()else{}
                if a.mode=='verify'and(target/'update_once.json').exists()and proof.get('state')!='FORMAL_FIELDS_SCORE_PASS':selected.append(pid)
                if a.mode=='sync'and proof.get('state')=='FORMAL_FIELDS_SCORE_PASS':selected.append(pid)
            if selected:rc=run(family,a.mode,selected)
        states={pid:s.load(folder/'商品'/pid/'verification.json').get('state')if(folder/'商品'/pid/'verification.json').exists()else'NOT_VERIFIED'for pid in ids}
        results.append({'family':family,'returncode':rc,'states':states})
    index.setdefault('phase_runs',{})[a.mode]={'at':s.now(),'results':results};s.save(s.ROOT/a.index,index)
    print(json.dumps({'mode':a.mode,'groups':len(results),'failures':[r['family']for r in results if r['returncode']]},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
