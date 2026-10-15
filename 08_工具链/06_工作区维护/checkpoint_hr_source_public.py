"""Freeze this HR/source and company-public-QA task on a separate Git index.

Does not alter HEAD, the shared index, unrelated registry fields or other work.
Only text, public source facts and bounded verification records are exported.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[2]
HR = '02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
FACTORY = '02_Alibaba运营/06_图片与检查记录/共享工厂详情'
REG = '02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
LUQI = '02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08'
CURRENT_LUQI_STYLES=('995','2576','1712','2418','868','822','2579','2575','2505','931','02412','0922','923','323','909','1628','2772','2132','9705','1680','0323F','117-1','2509','026')
PRIVATE = {'owner_member','owner_member_display_name','owner_member_id',
           'access_token','refresh_token','app_secret','client_secret',
           'chatToken','buyer_email','buyer_phone','buyer_address',
           'receiver_mobile','login_cookie'}
SECRET = re.compile(r'(?:access_token|refresh_token|app_secret|chatToken|_signature)=',re.I)


def git(*args, **kwargs):
    return subprocess.check_output(['git', *args], cwd=ROOT, **kwargs)


def safe(value):
    if isinstance(value, dict):
        for key, child in value.items():
            assert key not in PRIVATE or child in (None,'',[],{}), key
            safe(child)
    elif isinstance(value,list):
        for child in value:
            safe(child)


def public_selection_copy(value):
    """Keep public source/cost decisions; internal seller metrics stay local."""
    if isinstance(value, dict):
        out = {k: public_selection_copy(v) for k, v in value.items()}
        if isinstance(out.get('selection_review'), dict):
            review = out['selection_review']
            review['reason'] = '依已确认的后台经营数据政策逐款选择；具体曝光、点击、询盘/TM数据及原始表只保留本地。公开本款真实来源、成本、差异和当前字段。'
        protected=out.get('protected_fields')
        if isinstance(protected,dict):
            names=[k for k in ('owner_member','owner_member_display_name','owner_member_id') if k in protected]
            if names:
                assert all(type(protected[k]) is bool for k in names), 'Only preservation-check booleans can be exported under neutral seller-identity label'
                values=[protected.pop(k) for k in names]
                preserved=all(values)
                protected['seller_identity_fields_preserved']=preserved
        return out
    if isinstance(value, list):
        return [public_selection_copy(v) for v in value]
    return value


def load(path):
    return json.loads((ROOT/path).read_text(encoding='utf8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--branch', default='codex/hr-source-replacement')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    assert args.branch == 'codex/hr-source-replacement'
    assert git('remote','get-url','origin').decode().strip() == 'https://github.com/421345308/beiqiang-cross-border-operations.git'
    head = git('rev-parse','HEAD').decode().strip()
    original_index = git('write-tree').decode().strip()
    base = git('rev-parse',args.base+'^{commit}').decode().strip()
    live = load(REG)
    scope = load(HR+'/scope.json')
    replacement_ids = {pid for ids in scope['targets'].values() for pid in ids.values()}
    profiles = load(HR+'/已有实款对应.json')['families']
    binding_ids = {pid for p in profiles for pid in p['ids']}
    history = load(HR+'/当前进度.json').get('historical_unreturned_families',[])
    historical_ids = {pid for row in history for pid in row['ids']}
    hr_ids = replacement_ids | binding_ids | historical_ids
    luqi_audit=LUQI+'/质量复核_2026-10-09/材料字段复核'
    luqi_repairs=load(luqi_audit+'/修正清单.json')['rows']
    luqi_ids={str(row['id']) for row in luqi_repairs}
    assert len(luqi_ids)==8
    new_luqi_ids=set()
    for style in CURRENT_LUQI_STYLES:
        new_luqi_ledger=ROOT/LUQI/(style+'准备/create_once.json')
        if new_luqi_ledger.exists():
            created=load(new_luqi_ledger.relative_to(ROOT).as_posix())
            if created.get('product_id'):
                assert created['model']=='BQ-LQ'+style and str(created['product_id']).isdigit()
                new_luqi_ids.add(str(created['product_id']))
    luqi_ids |= new_luqi_ids
    luqi_families={ll['product_id'] for ll in live['listings'] if ll['id'] in luqi_ids}
    families = set(scope['targets']) | {p['family'] for p in profiles} | {p['family']for p in history}
    paths = [HR+'/'+name for name in ('README.md','scope.json','当前进度.json','质量修正计划.json','已有实款对应.json','双改与货源一致性核验.json')]
    paths += [p.relative_to(ROOT).as_posix()for p in (ROOT/HR).glob('*公开报价比较.json')]
    paths += [HR+'/商品/'+pid+'/historical_presence_get.json'for pid in historical_ids]
    # Independent preparation is authorized while HR awaits review; no Luqi
    # publication state is advanced. Only public sources/text/SHA records enter Git.
    queue_path=LUQI+'/质量复核_2026-10-09/全分类处理队列.json'
    queue=load(queue_path)
    assert len(queue['rows'])==107
    paths += [queue_path,LUQI+'/README.md',LUQI+'/本批正式商品汇总.json',LUQI+'/待补资料与局部问题.json','08_工具链/01_业务脚本/国际站扩品/collect_luqi_pending_sources.py','08_工具链/06_工作区维护/product_dossiers.py']
    paths += ['08_工具链/01_业务脚本/国际站扩品/'+name for name in ('repair_luqi_material_roles.py','expand_luqi_2583_family.py')]
    paths += ['08_工具链/01_业务脚本/国际站扩品/publish_reviewed_luqi.py']
    paths += ['08_工具链/01_业务脚本/国际站扩品/repair_luqi_price_rounding.py']
    paths += ['08_工具链/01_业务脚本/国际站扩品/'+name for name in ('merge_reviewed_luqi_0323_family.py','review_luqi_category_routes.py')]
    paths += [LUQI+'/0323F准备/家族归并.json']
    # The JSON receipt already retains the exact Schema string. Its raw XML
    # companion stays local, preserving platform whitespace without Git noise.
    paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/LUQI/'质量复核_2026-10-09/类目适配核对').glob('*.json')]
    paths += [LUQI+'/2409准备/'+name for name in ('实际评分回读.json','发布后字段核验.json')]
    paths += [LUQI+'/1628准备/标识形状比较/当前形状核对.json']
    for style in CURRENT_LUQI_STYLES:
        prefix=LUQI+'/'+style+'准备'
        paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/prefix).glob('*.json') if p.name in ('当前来源与色码核对.json','当前来源刷新核对.json','物流标签回读诊断.json','prepared.json','manifest.json','图片银行公开映射.json','create_once.json','create_receipt.json','verification.json','score.json','双改核验.json','来源款式近似候选.json','发布前差异化审查.json')]
        paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/prefix/'05_AI候选').glob('*.json')]
        paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/prefix/'价格取整修正').glob('*.json') if p.name in ('prepared.json','manifest.json','update_once.json','update_receipt.json','current_expected_overlay.json','verification.json')]
        paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/prefix/'价格取整修正').glob('*.xml') if p.name=='payload.xml']
    paths += [luqi_audit+'/'+name for name in ('修正清单.json','当前正式材料.json','prepare_汇总.json','submit_汇总.json','verify_汇总.json','双改核验.json') if (ROOT/luqi_audit/name).exists()]
    for row in luqi_repairs:
        paths.append(row['source_facts'])
        folder=ROOT/luqi_audit/'商品'/str(row['id'])
        paths += [p.relative_to(ROOT).as_posix() for p in folder.glob('*.json') if p.name in ('prepared.json','manifest.json','update_once.json','update_receipt.json','verification.json','score.json')]
    prefix=LUQI+'/2583-1准备/家族扩色'
    paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/prefix).glob('*.json') if p.name in ('家族来源与页面计划.json','图片银行公开映射.json','prepared.json','manifest.json','update_once.json','update_receipt.json','verification.json','score.json','当前状态.json','双改核验.json','本地素材绑定核验.json')]
    prefix=LUQI+'/2583准备'
    paths += [prefix+'/'+name for name in ('当前来源与色码核对.json','来源现状复核.json','05_AI候选/AI主图审核.json','05_AI候选/AI新增颜色完整提示词.json','05_AI候选/AI新增颜色审核.json','05_AI候选/AI家族详情完整提示词.json','05_AI候选/AI家族详情审核.json','标识形状比较/官方图形来源.json')]
    for row in queue['rows']:
        if row['publication_state']!='PENDING_STYLE_AND_QUALITY_REVIEW':continue
        prefix=LUQI+'/'+row['style']+'准备'
        index=ROOT/prefix/'01_产品来源原图/当前来源图像索引.json'
        if index.exists()and load(index.relative_to(ROOT).as_posix()).get('collection')=='PUBLIC_HTTPS_NORMAL_TLS_PRODUCT_ONLY':
            paths.append(index.relative_to(ROOT).as_posix())
            for name in ('当前来源与色码核对.json','05_AI候选/AI颜色图审核.json','05_AI候选/AI主图审核.json','05_AI候选/AI选款图审核.json','05_AI候选/AI结构图审核.json','05_AI候选/AI详情与穿着完整提示词.json','05_AI候选/AI详情与穿着审核.json','05_AI候选/整组验收.json'):
                file=ROOT/prefix/name
                if file.exists():paths.append(file.relative_to(ROOT).as_posix())
    for family in scope['targets']:
        paths += [HR+'/'+family+'/'+name for name in ('事实与页面计划.json','当前状态.json','来源事实.json','素材清单.json','图片银行公开映射.json')]
        paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/HR/family).glob('*.json') if p.name in ('AI主图审核.json','AI色码图审核.json','AI生成提示词.json','目标店内分组回读.json')]
    for profile in profiles:
        paths += [HR+'/'+profile['family']+'/来源与正式绑定核验.json']
        for key in ('approved_bank','approved_visual','source_fact_file'):
            if profile.get(key,'').startswith(HR+'/') and profile[key].endswith('.json'):paths.append(profile[key])
    for pid in replacement_ids:
        paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/HR/'商品'/pid).glob('*.json')
                  if p.name in ('verification.json','public_verification.json','public_product_verification.json','score.json',
                                'update_once.json','update_receipt.json',
                                'attribute_repair_once.json','attribute_repair_receipt.json',
                                'gallery_repair_once.json','gallery_repair_receipt.json',
                                'public_style_once.json','public_style_receipt.json',
                                'hero_quality_once.json','hero_quality_receipt.json',
                                'business_correction_once.json','business_correction_receipt.json',
                                'optional_attribute_clear_once.json','optional_attribute_clear_receipt.json',
                                'title_repair_once.json','title_repair_receipt.json',
                                'title_quality_once.json','title_quality_receipt.json',
                                'group_quality_once.json','group_quality_receipt.json',
                                'company_quality_once.json','company_quality_receipt.json',
                                '审核退回诊断.json')]
    paths += ['08_工具链/01_业务脚本/国际站扩品/'+name for name in
              ('replace_hr_real_sources.py','verify_hr_real_sources.py',
               'repair_hr_source_quality.py','sync_hr_real_sources.py',
               'prepare_hr054_assets.py','prepare_hr020_assets.py','build_hr_replacement_scope.py',
               'sync_hr_source_media.py','reconcile_hr_existing_sources.py','audit_hr_source_consistency.py',
               'prepare_hr_source_images.py','freeze_hr_source_package.py',
               'collect_hr_source_targets.py','repair_hr_rejected_profile.py',
               'collect_sooxie_public_package.py','analyze_hr_operating_selection.py',
               'retire_unsubmitted_hr_candidate.py','clear_optional_hr_attribute.py',
               'schema_publish_contract.py','repair_hr_changed_title.py',
               'run_hr_reviewed_pipeline.py','read_only_catalog.py','collect_hr_category_tree.py')]
    paths += ['02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md',FACTORY+'/README.md']
    paths += ['08_工具链/01_业务脚本/国际站扩品/README.md']
    paths += ['08_工具链/01_业务脚本/商品图片与审计/ingest_company_public_observations.py',
              '08_工具链/06_工作区维护/checkpoint_hr_source_public.py']
    paths += [FACTORY+'/V8/'+name for name in ('当前替换.json','公开验收参考.json','双改同步.json')]
    public_ids = set()
    for path in (ROOT/FACTORY/'商品').glob('*/V8/public_verification.json'):
        proof = json.loads(path.read_text(encoding='utf8'))
        if proof.get('localized_reference') == 'V8/公开验收参考.json':
            public_ids.add(proof['product_id'])
            paths += [path.relative_to(ROOT).as_posix(),path.with_name('verification.json').relative_to(ROOT).as_posix()]
    frozen = {}
    retired_source_ids = set()
    for family in scope['targets']:
        file = ROOT/HR/family/'候选取舍.json'
        if not file.exists():continue
        proof = json.loads(file.read_text(encoding='utf8'))
        public = {'family':family,'retired_candidates':[],'scope':'未提交候选完整归档保留，当前计划与回执分列；媒体留本地。'}
        for candidate in proof['retired_candidates']:
            retired_source_ids.add('src-hr-'+family.lower()+'-'+candidate['source_artno'].lower())
            public['retired_candidates'].append({k:copy.deepcopy(candidate[k])for k in ('state','reason','source_artno','source_url','raw_package_retained','archive_documents','derivative_path_state')})
        frozen[HR+'/'+family+'/候选归档引用.json']=(json.dumps(public,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    for path in sorted(set(paths)):
        raw = (ROOT/path).read_bytes().replace(b'\r\n',b'\n')
        text = raw.decode('utf8')
        assert not SECRET.search(text), path
        if path.endswith('.json'):
            payload = public_selection_copy(json.loads(text))
            safe(payload)
            raw = (json.dumps(payload,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        frozen[path] = raw
    # The shared SOP can contain other active tasks' edits. Export only the
    # owner's exact current-batch acceptance change onto this branch's base.
    sop='02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md'
    live_sop=(ROOT/sop).read_text(encoding='utf8')
    section=re.search(r'^### 本轮 HR 全量替换及后续路崎上架的验收调整[^\n]*\n[\s\S]+?写入授权边界。\n',live_sop,re.M).group(0)
    base_sop=git('show',base+':'+sop).decode('utf8')
    old=re.search(r'^### 本轮 HR 全量替换及后续路崎上架的验收调整[^\n]*\n[\s\S]+?写入授权边界。\n',base_sop,re.M)
    if old:base_sop=base_sop[:old.start()]+section+base_sop[old.end():]
    else:
        assert base_sop.count('## 8. 单款验收回执')==1
        base_sop=base_sop.replace('## 8. 单款验收回执','## 8. 单款验收回执\n\n'+section.strip(),1)
    frozen[sop]=base_sop.replace('\r\n','\n').encode('utf8')
    # Add only this task's independently proven Snow Boot type4 create entry.
    # Other central capability edits in the shared checkout remain untouched.
    caps='08_工具链/01_业务脚本/国际站扩品/schema_capabilities.json'
    base_caps=json.loads(git('show',base+':'+caps));live_caps=load(caps)
    snow=[x for x in live_caps['evidence'] if x.get('operation')=='create' and x.get('detail_type')=='4' and x.get('category_id')=='202248402' and x.get('product_id')=='1601975285993']
    assert len(snow)==1 and snow[0]['level']=='business_submission'
    entry=snow[0];receipt=load(entry['source']);assert receipt['method']=='alibaba.icbu.product.schema.add' and receipt['status']=='submitted_needs_readback'
    from xml.etree import ElementTree as E
    payload=E.parse(ROOT/entry['payload_source']).getroot()
    assert payload.find("./field[@id='catId']/value").text=='202248402'
    assert payload.find("./field[@id='productDescType']/value").text=='4'
    if entry not in base_caps['evidence']:base_caps['evidence'].append(copy.deepcopy(entry))
    safe(base_caps);frozen[caps]=(json.dumps(base_caps,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    for path in (entry['source'],entry['payload_source'],entry['current_category_evidence']):
        raw=(ROOT/path).read_bytes().replace(b'\r\n',b'\n');assert not SECRET.search(raw.decode('utf8'))
        if path.endswith('.json'):safe(json.loads(raw))
        frozen[path]=raw
    general=[x for x in live_caps['evidence'] if x.get('operation')=='create' and x.get('detail_type')=='4' and x.get('category_id')=='32299' and x.get('product_id')=='1601980840117']
    if general:
        assert len(general)==1 and general[0]['level']=='business_submission'
        entry=general[0];receipt=load(entry['source']);assert receipt['method']=='alibaba.icbu.product.schema.add' and receipt['status']=='submitted_needs_readback'
        payload=E.parse(ROOT/entry['payload_source']).getroot();assert payload.find("./field[@id='catId']/value").text=='32299' and payload.find("./field[@id='productDescType']/value").text=='4'
        if entry not in base_caps['evidence']:base_caps['evidence'].append(copy.deepcopy(entry))
        safe(base_caps);frozen[caps]=(json.dumps(base_caps,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        for path in (entry['source'],entry['payload_source'],entry['current_category_evidence']):
            raw=(ROOT/path).read_bytes().replace(b'\r\n',b'\n');assert not SECRET.search(raw.decode('utf8'))
            if path.endswith('.json'):safe(json.loads(raw))
            frozen[path]=raw
    merged = json.loads(git('show',base+':'+REG))
    baseline = copy.deepcopy(merged)
    original_other_sources = {x['id']:copy.deepcopy(x) for x in merged['sources']}
    lp = {x['id']:x for x in live['products']}
    ll = {x['id']:x for x in live['listings']}
    source_ids = {ll[pid]['optimization']['source_replacement']['source_id'] for pid in replacement_ids} | {p['source_id'] for p in profiles} | retired_source_ids
    sources = {x['id']:x for x in live['sources'] if x['id'] in source_ids}
    merged['sources'] = [x for x in merged['sources'] if x['id'] not in source_ids] + list(copy.deepcopy(sources).values())
    assert all(x == original_other_sources[x['id']] for x in merged['sources'] if x['id'] not in source_ids)
    for i, product in enumerate(merged['products']):
        if product['id'] in families:
            merged['products'][i] = copy.deepcopy(lp[product['id']])
        elif product['id'] in luqi_families:
            # Exact source-evidenced Luqi correction, not a sweep of all active
            # workspace changes. Preserve unrelated family fields from base.
            for key in ('source_state','adopted_source_id','candidate_source_ids','local_assets','material_role_review','family_color_expansion','source_routes_by_color','related_source_ids','next_action','notes','aliases','evidence','raw_packages','dossier_path'):
                if key in lp[product['id']]:product[key]=copy.deepcopy(lp[product['id']][key])
            if product['id'] in {'LQ-'+style for style in CURRENT_LUQI_STYLES}:product['classification']=copy.deepcopy(lp[product['id']]['classification'])
    family_phase=ll['1601976101204'].get('optimization',{}).get('family_color_expansion',{})
    if family_phase.get('state') in ('FORMAL_FIELDS_SCORE_PASS','FORMAL_FIELDS_PASS_PENDING_SCORE') and 'LQ-2583' not in lp:
        assert not any(l['product_id']=='LQ-2583' for l in merged['listings'])
        merged['products']=[p for p in merged['products'] if p['id']!='LQ-2583']
    if 'LQ-0323-1' not in lp:
        family_proof=load(LUQI+'/0323F准备/家族归并.json')
        accepted=load(LUQI+'/0323F准备/verification.json')
        assert accepted['id']==family_proof['product_id']=='1601980406877' and accepted['state']=='FORMAL_FIELDS_SCORE_PASS' and not accepted['failed'] and str(accepted['actual_score'])=='5.00'
        assert family_proof['state']=='ONE_CANONICAL_PRODUCT_AND_CURRENT_DOSSIER' and 'LQ-0323-1' in lp['LQ-0323F']['aliases']
        assert not any(l['product_id']=='LQ-0323-1' for l in merged['listings'])
        merged['products']=[p for p in merged['products'] if p['id']!='LQ-0323-1']
    for listing in merged['listings']:
        pid = listing['id']
        if pid in hr_ids:
            for key in ('bound_source_id','source_relation','observation','current_platform_fields',
                        'catalog_fields','formal_fields','local_sync','url','record_type','notes','platform_group'):
                if key in ll[pid]:
                    listing[key] = copy.deepcopy(ll[pid][key])
            if pid in replacement_ids or pid in binding_ids:
                field = 'source_replacement' if pid in replacement_ids else 'source_binding_reconciliation'
                listing.setdefault('optimization',{})[field] = copy.deepcopy(ll[pid]['optimization'][field])
            if pid in historical_ids:
                for key in ('catalog_presence','catalog_evidence','evidence'):
                    if key in ll[pid]:listing[key]=copy.deepcopy(ll[pid][key])
            current = ROOT / ll[pid].get('formal_fields',{}).get('file','missing')
            if current.is_file() and load(str(current.relative_to(ROOT))).get('sanitized_fields'):
                raw = current.read_bytes().replace(b'\r\n',b'\n')
                safe(json.loads(raw))
                frozen[current.relative_to(ROOT).as_posix()] = raw
        if pid in public_ids:
            for key in ('company_bundle','factory_gallery'):
                listing.setdefault('optimization',{})[key] = copy.deepcopy(ll[pid]['optimization'][key])
        if pid in luqi_ids:
            for key in ('observation','current_platform_fields','catalog_fields','formal_fields','local_sync','source_routes_by_color','url','notes','current_repair_phase','evidence'):
                if key in ll[pid]:listing[key]=copy.deepcopy(ll[pid][key])
                elif key=='current_repair_phase':listing.pop(key,None)
            for key in ('material_role_repair','family_color_expansion'):
                if key in ll[pid].get('optimization',{}):listing.setdefault('optimization',{})[key]=copy.deepcopy(ll[pid]['optimization'][key])
            current=ROOT/ll[pid]['formal_fields']['file']
            payload=load(current.relative_to(ROOT).as_posix());assert payload.get('sanitized_fields');safe(payload)
            frozen[current.relative_to(ROOT).as_posix()]=(json.dumps(payload,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    # Exact 2409 score recovery only; retain all other base fields.
    recovered=next(x for x in merged['listings'] if x['id']=='1601976084873')
    current_score=ll['1601976084873'].get('observation',{})
    if current_score.get('score_evidence')==LUQI+'/2409准备/实际评分回读.json':
        assert load(current_score['score_evidence'])['result']['final_score']=='5.00'
        recovered.setdefault('observation',{}).update({k:current_score[k] for k in ('score','score_at','score_evidence')})
        recovered['evidence']=list(dict.fromkeys(recovered.get('evidence',[])+[LUQI+'/2409准备/'+n for n in ('实际评分回读.json','发布后字段核验.json')]))
    for pid in new_luqi_ids:
        assert pid not in {l['id'] for l in baseline['listings']} or next(l for l in baseline['listings'] if l['id']==pid)['model']==ll[pid]['model']
        merged['listings']=[l for l in merged['listings'] if l['id']!=pid]+[copy.deepcopy(ll[pid])]
        source_id=lp[ll[pid]['product_id']].get('adopted_source_id') or next(iter(lp[ll[pid]['product_id']].get('candidate_source_ids',[])),None)
        assert source_id
        source=next(s for s in live['sources'] if s['id']==source_id)
        expected_sources={ll[known]['model']:load(LUQI+'/'+ll[known]['model'].removeprefix('BQ-LQ')+'准备/当前来源与色码核对.json')['source'] for known in new_luqi_ids}
        assert source['url']==expected_sources[ll[pid]['model']]
        merged['sources']=[s for s in merged['sources'] if s['id']!=source_id]+[copy.deepcopy(source)]
    task = next(x for x in live['workstreams'] if x['name']=='HR缺货源实款替换')
    merged['workstreams'] = [x for x in merged['workstreams'] if x['name']!=task['name']] + [copy.deepcopy(task)]
    luqi_work=next(x for x in live['workstreams'] if x['name']=='路崎宽头/户外全分类')
    merged['workstreams']=[x for x in merged['workstreams'] if x['name']!=luqi_work['name']]+[copy.deepcopy(luqi_work)]
    merged['updated_on'] = live['updated_on']
    safe(merged)
    frozen[REG] = (json.dumps(merged,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    # Full media cache remains local per the repository media boundary. Export
    # exact per-object official-bank maps and SHA binding proofs above instead
    # of publishing a misleading partial global cache or unrelated assets.
    sys.path.insert(0,str(Path(__file__).parent))
    import build_product_workspace as workspace
    errors = workspace.validate(merged)
    baseline_errors = workspace.validate(baseline)
    assert set(errors) <= set(baseline_errors), errors
    assert not any(pid in error for pid in hr_ids for error in errors), errors
    current_views=workspace.build(merged)
    retired_views={path.as_posix() for path in workspace.build(baseline) if path not in current_views}
    assert all(path.endswith(('/LQ-2583/README.md','/LQ-0323-1/README.md')) for path in retired_views), 'Only the exact merged candidate generated entry may be removed'
    retired_views.add('08_工具链/01_业务脚本/国际站扩品/publish_reviewed_luqi_995.py')
    for path, raw in current_views.items():
        relative = path.relative_to(ROOT) if path.is_absolute() else path
        frozen[relative.as_posix()] = raw
    with tempfile.TemporaryDirectory(prefix='hr-public-git-',dir=ROOT/'99_临时区/HR实源替换') as temporary:
        env = dict(os.environ,GIT_INDEX_FILE=str(Path(temporary)/'index'))
        git('read-tree',base,env=env)
        for path in sorted(retired_views):git('update-index','--force-remove','--',path,env=env)
        rows = list(frozen.items())
        files = []
        for i, (path, raw) in enumerate(rows):
            target = Path(temporary)/str(i)
            target.write_bytes(raw)
            files.append(target.as_posix())
        hashes = git('hash-object','-w','--no-filters','--stdin-paths',
                     input=('\n'.join(files)+'\n').encode('utf8')).decode().splitlines()
        assert len(hashes) == len(rows)
        entries = []
        for (path, raw), blob in zip(rows,hashes):
            assert blob == hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            assert not any(c in path for c in '\n\r\t')
            entries.append('100644 '+blob+'\t'+path+'\n')
        git('update-index','--index-info',input=''.join(entries).encode('utf8'),env=env)
        tree = git('write-tree',env=env).decode().strip()
        assert not git('diff','--check',base,tree)
        changed = [p for p in git('diff','--name-only','-z',base,tree).decode().split('\0') if p]
        assert set(changed) <= set(frozen)|retired_views
        assert git('rev-parse','HEAD').decode().strip() == head
        assert git('write-tree').decode().strip() == original_index
        if args.check_only:
            print('EXACT_TASK_PUBLIC_SCOPE_PASS',len(changed),'HR IDs',len(hr_ids),'PUBLIC IDs',len(public_ids),'BASELINE_ONLY_ALIAS_ISSUES',len(baseline_errors))
            return
        message = b'feat: publish reviewed Luqi real-source offers and synchronize supply records\n'
        commit = git('commit-tree',tree,'-p',base,input=message).decode().strip()
        ref = 'refs/heads/'+args.branch
        exists = subprocess.run(['git','show-ref','--verify','--quiet',ref],cwd=ROOT).returncode == 0
        previous = git('rev-parse',ref).decode().strip() if exists else '0'*40
        assert not exists or previous == base, 'Existing task branch requires its current tip as base'
        git('update-ref',ref,commit,previous)
        proof = {'branch':args.branch,'base':base,'commit':commit,'files':changed,
                 'hr_ids':sorted(hr_ids),'public_ids':sorted(public_ids),
                 'root_HEAD_and_index_unchanged':True,'raw_accounts_sessions_and_media_excluded':True}
        (ROOT/HR/'Git阶段提交.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(json.dumps({'commit':commit,'branch':args.branch,'changed':len(changed)},ensure_ascii=False))


if __name__ == '__main__':
    main()
