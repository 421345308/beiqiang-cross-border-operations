"""Reconcile current image repair indexes from exact per-ID formal evidence."""
from pathlib import Path
from collections import Counter
import sys
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s


def main():
    sys.stdout.reconfigure(encoding='utf8');summary={};updated=set();binding_proofs={}
    for filename,category in [('颜色绑定修正.json','配色与尺码修正'),('配色图执行.json','图库重做'),('旧报价图执行.json','图库重做'),('报价图正式纠正执行.json','图库重做'),('首图修复执行.json','图库重做'),('补充尺码图执行.json','图库重做'),('专款配色详情执行.json','图库重做'),('功能详情精修执行.json','图库重做'),('模板清理执行.json','图库重做'),('规格照片精修执行.json','配色与尺码修正'),('详情图组收尾执行.json','图库重做')]:
        file=s.BASE/filename
        if not file.exists():continue
        index=s.load(file);observations={}
        for group in index['groups']:
            key=group.get('key',group['family']);folder=s.BASE/category/key;states={}
            for pid in group['ids']:
                proof=folder/'商品'/pid/'verification.json';row=s.load(proof)if proof.exists()else{}
                if filename=='旧报价图执行.json'and(pid in ('11000037600317','1601943501378')):
                    newer=s.BASE/'图库重做'/(group['family'].replace('_旧报价图替换','_旧报价图正式纠正'))/'商品'/pid/'verification.json'
                    if newer.exists()and s.load(newer).get('at','')>row.get('at',''):proof=newer;row=s.load(proof)
                if filename=='补充尺码图执行.json'and pid=='10000043725883':
                    newer=s.BASE/'图库重做/BQ011_功能图正式精修/商品'/pid/'verification.json'
                    if newer.exists()and s.load(newer).get('state')=='FORMAL_FIELDS_SCORE_PASS':proof=newer;row=s.load(proof)
                if filename=='首图修复执行.json'and pid=='10000043763325':
                    newer=s.BASE/'图库重做/BQ013_功能图正式精修/商品'/pid/'verification.json'
                    if newer.exists()and s.load(newer).get('state')=='FORMAL_FIELDS_SCORE_PASS':proof=newer;row=s.load(proof)
                if filename=='规格照片精修执行.json':
                    newer=folder/'商品'/pid/'current_colour_verification.json'
                    if newer.exists()and s.load(newer).get('state')=='FORMAL_FIELDS_SCORE_PASS':proof=newer;row=s.load(proof)
                state=row.get('state','REVIEWED_NOT_SUBMITTED');states[pid]={'state':state,'proof':s.rel(proof)if proof.exists()else None,'at':row.get('at')}
                if state=='FORMAL_FIELDS_SCORE_PASS':updated.add(pid)
                if filename=='颜色绑定修正.json'and state=='FORMAL_FIELDS_SCORE_PASS':binding_proofs.setdefault(group['family'],[]).append(s.rel(proof))
                previous=observations.get(pid)
                if not previous or(row.get('at')or'')>(previous.get('at')or''):observations[pid]=states[pid]
            group['current_states']=states;group['state']='FORMAL_FIELDS_SCORE_PASS'if all(r['state']=='FORMAL_FIELDS_SCORE_PASS'for r in states.values())else'IMAGE_WORK_PENDING';group['reconciled_at']=s.now()
        s.save(file,index);summary[filename]={'ids':len(observations),'states':dict(Counter(v['state']for v in observations.values()))}
    audit=s.load(s.BASE/'颜色绑定复核.json')
    for family in ('BQ044','BQ051'):
        proof=s.BASE/'配色与尺码修正'/(family+'_规格图纠正')/'商品'
        for file in proof.glob('*/verification.json'):
            if s.load(file)['state']=='FORMAL_FIELDS_SCORE_PASS':binding_proofs.setdefault(family,[]).append(s.rel(file))
    for finding in audit['visual_review']['findings']:
        if finding['family']in binding_proofs:finding.update(state='SOURCE_REVIEWED_BINDING_CORRECTED_FORMAL_PASS',current_evidence=binding_proofs[finding['family']])
    audit['visual_review']['state']='EXACT_BINDING_REPAIRS_COMPLETE_NAMING_REVIEW_PENDING';audit['visual_review']['reconciled_at']=s.now();s.save(s.BASE/'颜色绑定复核.json',audit)
    s.save(s.BASE/'图片当前核验.json',{'at':s.now(),'scope':'Per-ID formal image repair evidence; scopes overlap and counts must not be added. Whole-store coverage is separately checked in 全店图片终检.json. This is not universal native-resolution photographic acceptance.','unique_ids_with_verified_repairs_in_these_indexes':len(updated),'indexes':summary,'whole_store_closure':'全店图片终检.json'})
    print('RECONCILED',len(summary),'INDEXES',len(updated),'UNIQUE_VERIFIED_IDS')

if __name__=='__main__':main()
