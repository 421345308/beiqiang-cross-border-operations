"""Retire a replaced local candidate, retaining raw source and official bank receipts."""
from pathlib import Path
import argparse,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def main():
    parser=argparse.ArgumentParser();parser.add_argument('family');parser.add_argument('--reason',required=True);parser.add_argument('--rejected-business-source',action='store_true');args=parser.parse_args()
    folder=BASE/args.family;plan=load(folder/'事实与页面计划.json')
    rejected=[]
    for pid in plan['target_ids'].values():
        product_folder=BASE/'商品'/pid;ledger=product_folder/'update_once.json'
        if args.rejected_business_source:
            assert ledger.exists()and load(ledger)['state']=='BUSINESS_REJECTED','Never retire an accepted or outcome-unknown write'
            response=load(product_folder/'update_receipt.json')
            assert response.get('biz_success')is False and 'PUB_BIZCHECK_CAT_PUB_RESTRICT'in response.get('msg_code',''),'Only explicit business-category rejection supported'
            unchanged=load(product_folder/'rejected_candidate_unchanged_get.json')
            assert unchanged['source_artno']==plan['source_artno']and unchanged['response']['product']==load(product_folder/'prewrite_get.json')['product'],'Latest full get must prove original product unchanged'
            rejected.append(pid)
        else:assert not ledger.exists(),'Never retire a submitted source as a local draft'
    bank=load(folder/'图片银行.json');manifest=load(folder/'素材清单.json')
    current_root=(ROOT/'01_产品资产/02_可发布素材'/args.family).resolve()
    assert current_root.is_relative_to((ROOT/'01_产品资产/02_可发布素材').resolve())
    images=[]
    for key,item in manifest['items'].items():
        if key=='M6':continue
        path=(ROOT/item['path']).resolve();assert path.is_relative_to(current_root)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
        assert bank['items'][key]['state']=='UPLOADED'and bank['items'][key]['sha256']==item['sha256']
        images.append(path)
    archive_root=current_root/'候选证据'/plan['source_artno']
    archive_docs=folder/'候选证据'/plan['source_artno']
    assert archive_root.resolve().is_relative_to(current_root) and not archive_root.exists()
    assert archive_docs.resolve().is_relative_to(folder.resolve()) and not archive_docs.exists()
    archive_root.mkdir(parents=True);archive_docs.mkdir(parents=True)
    for pid in rejected:
        original=BASE/'商品'/pid;target=archive_docs/'商品'/pid;target.mkdir(parents=True)
        for name in ['before_get.json','before_render.json','prepared.json','prewrite_get.json','update_once.json','update_receipt.json','rejected_candidate_unchanged_get.json']:
            old=original/name;assert old.is_file()
            exact_sha=hashlib.sha256(old.read_bytes()).hexdigest();shutil.move(str(old),str(target/name));assert hashlib.sha256((target/name).read_bytes()).hexdigest()==exact_sha
    archived_images=[]
    for path in images:
        target=archive_root/path.relative_to(current_root)
        assert target.resolve().is_relative_to(archive_root.resolve()) and not target.exists()
        target.parent.mkdir(parents=True,exist_ok=True)
        original_sha=hashlib.sha256(path.read_bytes()).hexdigest()
        shutil.move(str(path),str(target))
        assert hashlib.sha256(target.read_bytes()).hexdigest()==original_sha
        archived_images.append({'original_path':str(path),'retained_path':str(target),'sha256':original_sha})
    sheet=current_root/'审核总览.jpg'
    if sheet.is_file():
        assert sheet.resolve().is_relative_to(current_root)
        shutil.move(str(sheet),str(archive_root/'审核总览.jpg'))
    # Preserve intact source plans, material manifests and upload receipts.
    for name in ['事实与页面计划.json','来源事实.json']:
        if(folder/name).is_file():shutil.copy2(folder/name,archive_docs/name)
    for name in ['图片银行.json','图片银行公开映射.json','素材清单.json']:
        path=folder/name
        if path.is_file():shutil.move(str(path),str(archive_docs/name))
    proof=folder/'候选取舍.json';data=load(proof)if proof.exists()else{'family':args.family,'retired_candidates':[]}
    assert not any(x['source_artno']==plan['source_artno']for x in data['retired_candidates'])
    data['retired_candidates'].append({'state':'EXPLICIT_BUSINESS_CATEGORY_REJECTION_ORIGINAL_UNCHANGED'if rejected else'UNSUBMITTED_CANDIDATE_SUPERSEDED','rejected_original_ids':rejected,'reason':args.reason,'source_artno':plan['source_artno'],'source_url':plan['source_url'],'raw_package_retained':plan['source_assets_root'],'past_draft_plan_for_rebuilding_formal_upload_evidence_only':plan,'official_image_bank_receipts_preserved':bank,'reviewed_manifest':manifest,'archived_images':archived_images,'archive_documents':archive_docs.relative_to(ROOT).as_posix(),'derivative_path_state':'All current candidate derivatives and intact bank/material evidence retained in source-artno-specific candidate evidence paths. Original path in historical manifest refers to pre-archive state; archived_images provides verified current locations. No live product was updated with this candidate.'})
    proof.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    assert load(proof)['retired_candidates'][-1]['official_image_bank_receipts_preserved']==bank
    print(args.family,'REJECTED_SOURCE_ARCHIVED_ORIGINAL_UNCHANGED'if rejected else'UNSUBMITTED_CANDIDATE_ARCHIVED_ALL_MATERIALS_AND_RECEIPTS_RETAINED')
if __name__=='__main__':main()
