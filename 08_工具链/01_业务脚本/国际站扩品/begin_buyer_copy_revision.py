"""Start an explicitly reviewed copy revision after the previous write was verified.

Local operation only. Keep formal evidence by exact ID, with one current copy.
Unknown outcomes cannot be advanced. Known non-target differences stay recorded;
new wording uses a fresh baseline rather than restoring another changed field.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, importlib.util, json, shutil, sys

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化/商品'
ARTIFACTS=('copy.json','before_get.json','before_render.json','current_schema.xml',
 'payload.xml','manifest.json','prepared.json','reviewed_baseline.json',
 'immediate_prewrite_get.json','update_once.json','update_receipt.json',
 'after_get.json','after_render.json','after_schema.xml','verification.json',
 'public_text_verification.json','public_read_attempt.json','non_target_difference.json')

def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def advance(pid, candidate):
    spec=importlib.util.spec_from_file_location('buyer_copy',Path(__file__).with_name('refresh_buyer_copy.py'))
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    assert pid not in helper.PROTECTED_IDS,'Protected source link'
    folder=BASE/pid
    assert folder.resolve().is_relative_to(ROOT.resolve()),'Unexpected file target'
    old=load(folder/'copy.json');new=load(candidate)
    assert old['product_id']==new['product_id']==pid and old['model']==new['model']
    assert new['reviewed'] is True and new['reviewer']=='active_agent' and new['claim_review']
    assert old['source_evidence']==new['source_evidence'],'This revision must retain exact shoe evidence'
    assert (old['highlights'],old['faq'])!=(new['highlights'],new['faq'])
    prior=load(folder/'update_once.json');receipt=load(folder/'update_receipt.json')
    assert prior['status']==receipt['status']=='submitted_needs_readback','Unresolved previous write'
    v=load(folder/'verification.json');actual=load(folder/'after_get.json')['product']
    assert (v['status']=='FORMAL_PASS' or v.get('target_copy_status')=='TARGET_FORMAL_PASS') and actual['status']=='approved' and actual['display']=='Y'
    assert v['schema_target_fields_match']
    # A new wording revision uses the observed current product as its baseline.
    # Any earlier non-target difference remains an unresolved historical issue;
    # this operation neither accepts nor restores that changed field.
    if not v['unsubmitted_fields_preserved']:
        assert (folder/'non_target_difference.json').exists(),'Record exact non-target differences first'
    assert helper.apostrophe_equivalent(helper.formal_copy(actual)['highlights'],old['highlights'])
    assert helper.faq_pairs_equivalent(helper.formal_copy(actual)['faq'],old['faq'])
    baseline=load(folder/'reviewed_baseline.json')
    assert baseline['copy_sha256']==hashlib.sha256((folder/'copy.json').read_bytes()).hexdigest()
    history=load(folder/'revision_history.json') if (folder/'revision_history.json').exists() else {'current_revision':1,'previous':[]}
    archive=folder/'revisions'/str(history['current_revision']).zfill(4)
    assert not archive.exists(),'Revision already started: inspect evidence, never replay'
    archive.mkdir(parents=True)
    files=[name for name in ARTIFACTS if (folder/name).exists()]
    proof={'started_at':datetime.now(timezone.utc).isoformat(),'product_id':pid,
      'previous_verification':v,'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),
      'scope':['textDesc','companyFaqDesc'],'no_platform_write':True,'archived_files':files}
    # Copy and verify all historical evidence before retiring the old current files.
    for name in files:
        shutil.copyfile(folder/name,archive/name)
        assert (folder/name).read_bytes()==(archive/name).read_bytes()
    save(archive/'revision_gate.json',proof)
    for name in files:
        if name!='copy.json':(folder/name).unlink()
    save(folder/'copy.json',new)
    history['previous'].append({'revision':history['current_revision'],'evidence':archive.relative_to(ROOT).as_posix(),'reason':'Remove internal evidence wording from buyer copy; shoe facts unchanged'})
    history['current_revision']+=1;save(folder/'revision_history.json',history)
    return {'product_id':pid,'status':'LOCAL_REVIEWED_REVISION_STARTED','revision':history['current_revision']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ids',required=True);ap.add_argument('--candidates',required=True);a=ap.parse_args()
    sys.stdout.reconfigure(encoding='utf8');ids=a.ids.split(',')
    assert len(ids)==len(set(ids)) and all(x.isdigit() for x in ids)
    candidates=Path(a.candidates)
    for pid in ids:print(json.dumps(advance(pid,candidates/(pid+'.json')),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
