"""Merge the exact 0323F/0323-1 source family after formal API acceptance.

Keeps all source originals/receipts and one current generated product entry.
No Alibaba write or deletion is performed.
"""
from pathlib import Path
from collections import Counter
import argparse,copy,sys
import publish_reviewed_luqi as p

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    F=p.BASE/'0323F准备';proof=p.load(F/'来源款式近似候选.json');report=p.load(F/'verification.json');receipt=p.load(F/'create_receipt.json');pid=p.pub.extract_product_id(receipt['response'])
    assert proof['common_photo_sha256_count']>=18 and proof['primary_style']=='0323F' and proof['alternate_style']=='0323-1'
    assert report['id']==pid=='1601980406877' and report['state']=='FORMAL_FIELDS_SCORE_PASS' and not report['failed'] and str(report['actual_score'])=='5.00'
    data=p.load(p.REG);before=copy.deepcopy(data);primary=next(x for x in data['products']if x['id']=='LQ-0323F');secondary=next((x for x in data['products']if x['id']=='LQ-0323-1'),None)
    if secondary is None:
        assert 'LQ-0323-1'in primary['aliases'];print('ALREADY_ONE_CURRENT_FAMILY_NO_REPEAT');return
    assert not any(l['product_id']=='LQ-0323-1'for l in data['listings']) and secondary['source_state']=='CANDIDATE'
    assert secondary['candidate_source_ids']==['src-32e04c6b8acf'] and primary['adopted_source_id']=='src-5b52a6d61cf2'
    main=p.load(F/'当前来源与色码核对.json');assert main['source_EU_combinations']==20
    evidence=p.rel(F/'来源款式近似候选.json');primary['aliases']=list(dict.fromkeys(primary['aliases']+secondary['aliases']));primary['related_source_ids']=list(dict.fromkeys(primary.get('related_source_ids',[])+secondary['candidate_source_ids']))
    primary['raw_packages']=list(dict.fromkeys(primary.get('raw_packages',[])+[p.rel(p.BASE/'0323-1准备/01_产品来源原图')]))
    primary['evidence']=list(dict.fromkeys(primary['evidence']+secondary['evidence']+[evidence]));primary.setdefault('notes',[]).append('0323F与0323-1当前两内里选项/欧码/价格一致，18张来源图SHA完全相同；原ID1601980406877为唯一当前商品，两原始来源保留，0323-1不重复创建。')
    primary['next_action']='同一家族20EU已正式5.00通过；采购优先0323F，0323-1保留同款备用入口，不重复上品。'
    data['products']=[x for x in data['products']if x['id']!='LQ-0323-1']
    qfile=p.BASE/'质量复核_2026-10-09/全分类处理队列.json';q=p.load(qfile);row=next(x for x in q['rows']if x['style']=='0323-1');row.update(publication_state='MERGED_SOURCE_FAMILY_0323F_NO_EXTRA_CREATE',product_id=pid,canonical_style='0323F',canonical_product='LQ-0323F',family_evidence=evidence,local_issue='',next_action='同款并入0323F；不另建ID，来源原件保留。');q['state_counts']=dict(Counter(x['publication_state']for x in q['rows']));q['observed_at']=p.now()
    sys.path.insert(0,str(p.ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as w
    assert set(w.validate(data))<=set(w.validate(before))
    views=w.build(data);oldpath=(p.ROOT/'02_Alibaba运营/02_单品优化记录/商品档案/LQ-0323-1/README.md').resolve();assert oldpath.is_relative_to(p.ROOT.resolve()) and oldpath.name=='README.md' and oldpath.parent.name=='LQ-0323-1'
    if oldpath.exists():assert '此页由唯一台账生成'in oldpath.read_text(encoding='utf8') and 'CANDIDATE'in oldpath.read_text(encoding='utf8')
    assert oldpath not in {p.ROOT/path for path in views}
    if not args.apply:print('EXACT_SOURCE_FAMILY_MERGE_REVIEW_PASS',pid,'20EU','18photoSHA');return
    p.save(p.REG,data);p.save(qfile,q)
    for path,body in views.items():w.write_generated(p.ROOT/path,body)
    if oldpath.exists():oldpath.unlink()
    p.save(F/'家族归并.json',{'at':p.now(),'state':'ONE_CANONICAL_PRODUCT_AND_CURRENT_DOSSIER','product_id':pid,'canonical_product':'LQ-0323F','aliases':primary['aliases'],'source_proof':evidence,'related_source_ids':primary['related_source_ids'],'deleted_only_generated_duplicate_entry':p.rel(oldpath),'originals_and_receipts_preserved':True,'no_external_mutation':True})
    print('0323F_FAMILY_MERGED_NO_DUPLICATE',pid)

if __name__=='__main__':main()
