"""Reconcile newest exact-ID evidence; never count accepted writes as completion."""
from pathlib import Path
from collections import Counter
import json,sys
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s

def main():
    sys.stdout.reconfigure(encoding='utf8');plan=s.load(s.PLAN_FILE);rows=[]
    for cp in plan['items']:
        for pid in cp['ids']:
            if pid in cp['exclusions']:
                rows.append({'id':pid,'family':cp['family'],'state':'EXCLUDED_PRESERVE_STATE'});continue
            candidates=[]
            if cp.get('handled_by_specific_revision'):
                paths=[s.BASE/'M001/verification.json']
            else:
                paths=[s.BASE/'商品'/pid/'verification.json']+[s.BASE/x/'商品'/pid/'verification.json'for x in ('结构与标题纠正','正式差异收尾')]
            for path in paths:
                if path.exists():candidates.append((s.load(path),path))
            if not candidates:
                rows.append({'id':pid,'family':cp['family'],'state':'NOT_VERIFIED'});continue
            # A late read of the original payload cannot supersede an explicit
            # later corrective request whose target intentionally changed.
            report,path=candidates[-1];state=report['state']
            # Dedicated M001 and initial copy share raw/<ID>; named corrections
            # have their own raw/<phase>/<ID> provenance.
            raw=s.RAW/pid if path.parent.name=='M001'or path.parents[2]==s.BASE else s.RAW/path.parents[2].name/pid
            actual=s.load(raw/'after_get.json')['product']if(raw/'after_get.json').exists()else{}
            expected_title=cp['title_by_id'].get(pid)
            desired={'title':expected_title is None or actual.get('subject')==expected_title,'highlights':actual.get('struct_detail',{}).get('product_summary','').replace('\u2019',"'")==cp['highlights'].replace('\u2019',"'")}
            if state=='FORMAL_FIELDS_SCORE_PASS'and not all(desired.values()):state='CURRENT_PLAN_NOT_YET_VERIFIED'
            rows.append({'id':pid,'family':cp['family'],'state':state,'at':report['at'],'score':report.get('score'),'failed':report.get('failed',[]),'current_plan_matches':desired,'verification':s.rel(path)})
    result={'at':s.now(),'current_catalog_unique_ids':488,'families':246,'writable_ids':479,'generic_copy_ids':478,'by_state':dict(Counter(r['state']for r in rows)),'copy_scope':'Title/functional highlights only; source matrix and image acceptance independent. Latest reviewed plan must match, not merely an older successful payload.','public_status':'No per-ID browser acceptance per user. API acceptance does not prove public visual presentation.','rows':rows}
    s.save(s.BASE/'当前核验.json',result);print(json.dumps({k:v for k,v in result.items()if k!='rows'},ensure_ascii=False))

if __name__=='__main__':main()
