"""Keep K502/K502D as one accepted product with source-specific lining variants."""
from collections import Counter
import argparse,copy,sys
import publish_reviewed_luqi as p

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 F=p.BASE/'K502准备';plan=p.load(F/'家族来源与页面计划.json');facts=p.load(F/'当前来源与色码核对.json');report=p.load(F/'verification.json');pid=p.pub.extract_product_id(p.load(F/'create_receipt.json')['response'])
 assert pid and report['id']==pid and report['state']=='FORMAL_FIELDS_SCORE_PASS' and not report['failed'] and str(report['actual_score'])=='5.00'
 assert plan['primary_style']=='K502' and plan['secondary_style']=='K502D' and facts['source_EU_combinations']==48
 assert facts['native_fact_photos_actually_viewed_by_source']=={'K502':[4,32,33,34],'K502D':[21,23,24,29,30,31]}
 proof=p.load(F/'05_AI候选/整组验收.json');assert proof['state']=='VISUAL_PASS_PENDING_PUBLISH_PREFLIGHT' and proof['group_actually_viewed']
 data=p.load(p.REG);before=copy.deepcopy(data);primary=next(x for x in data['products']if x['id']=='LQ-K502');secondary=next((x for x in data['products']if x['id']=='LQ-K502D'),None)
 if secondary is None:
  assert 'LQ-K502D'in primary['aliases'];print('ALREADY_ONE_CURRENT_FAMILY_NO_REPEAT');return
 assert secondary['source_state']=='CANDIDATE' and secondary['candidate_source_ids']==['src-f034c10e357d'] and primary['adopted_source_id']=='src-1c8a45b9566a'
 assert not any(l['product_id']=='LQ-K502D'for l in data['listings']) and not(p.BASE/'K502D准备/create_once.json').exists()
 listing=next(l for l in data['listings']if l['id']==pid);assert listing['product_id']=='LQ-K502' and listing['source_routes_by_color']==primary['source_routes_by_color']
 routes=primary['source_routes_by_color'];assert len(routes)==6 and sum(len(v['EU'])for v in routes.values())==48
 for label,route in routes.items():
  assert route['source_artno']==('K502D'if label.endswith('Standard')else'K502') and route['EU']==list(range(39,47))
 evidence=p.rel(F/'家族来源与页面计划.json');primary['aliases']=list(dict.fromkeys(primary['aliases']+secondary['aliases']));primary['related_source_ids']=list(dict.fromkeys(primary.get('related_source_ids',[])+secondary['candidate_source_ids']))
 primary['evidence']=list(dict.fromkeys(primary['evidence']+secondary.get('evidence',[])+[evidence]));primary.setdefault('notes',[]).append('K502/K502D六色内里选项合并一条48EU商品；K502加绒和K502D普通款按颜色选项分别对应原图及采购入口，不另建K502D。两来源图无共同SHA，依据逐图鞋型/内里核验，不声称图片完全相同。')
 primary['next_action']='普通/加绒六选项48EU已正式核验及实际5.00；两采购入口分别路由，继续其他实款，不重复创建。'
 data['products']=[x for x in data['products']if x['id']!='LQ-K502D']
 qfile=p.BASE/'质量复核_2026-10-09/全分类处理队列.json';q=p.load(qfile);row=next(x for x in q['rows']if x['style']=='K502D');row.update(publication_state='MERGED_SOURCE_FAMILY_K502_NO_EXTRA_CREATE',product_id=pid,canonical_style='K502',canonical_product='LQ-K502',family_evidence=evidence,local_issue='',next_action='普通版并入K502的Standard选项，保留K502D实拍和采购入口；不另建ID。');q['state_counts']=dict(Counter(x['publication_state']for x in q['rows']));q['observed_at']=p.now()
 sys.path.insert(0,str(p.ROOT/'08_工具链/06_工作区维护'));import build_product_workspace as w
 assert set(w.validate(data))<=set(w.validate(before));views=w.build(data);oldpath=(p.ROOT/'02_Alibaba运营/02_单品优化记录/商品档案/LQ-K502D/README.md').resolve();assert oldpath.is_relative_to(p.ROOT.resolve()) and oldpath.name=='README.md' and oldpath.parent.name=='LQ-K502D'
 if oldpath.exists():assert '此页由唯一台账生成'in oldpath.read_text(encoding='utf8') and 'CANDIDATE'in oldpath.read_text(encoding='utf8')
 assert oldpath not in {p.ROOT/path for path in views}
 if not args.apply:print('K502_FAMILY_MERGE_REVIEW_PASS',pid,'48EU');return
 p.save(p.REG,data);p.save(qfile,q)
 for path,body in views.items():w.write_generated(p.ROOT/path,body)
 if oldpath.exists():oldpath.unlink()
 p.save(F/'家族归并.json',{'at':p.now(),'state':'ONE_CANONICAL_PRODUCT_AND_CURRENT_DOSSIER','product_id':pid,'canonical_product':'LQ-K502','aliases':primary['aliases'],'source_proof':evidence,'related_source_ids':primary['related_source_ids'],'deleted_only_generated_duplicate_entry':p.rel(oldpath),'originals_and_receipts_preserved':True,'no_external_mutation':True,'source_routes_by_color':routes})
 plan.update(state='ONE_FAMILY_48EU_FORMAL_FIELDS_SCORE_PASS',product_id=pid,merge_evidence=p.rel(F/'家族归并.json'));p.save(F/'家族来源与页面计划.json',plan);print('K502_FAMILY_MERGED_NO_DUPLICATE',pid)

if __name__=='__main__':main()
