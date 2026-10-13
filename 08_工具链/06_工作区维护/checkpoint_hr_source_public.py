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
    hr_ids = replacement_ids | binding_ids
    families = set(scope['targets']) | {p['family'] for p in profiles}
    paths = [HR+'/'+name for name in ('README.md','scope.json','当前进度.json','质量修正计划.json','已有实款对应.json','双改与货源一致性核验.json')]
    paths += [p.relative_to(ROOT).as_posix()for p in (ROOT/HR).glob('*公开报价比较.json')]
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
                                'title_repair_once.json','title_repair_receipt.json')]
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
            safe(json.loads(text))
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
    for listing in merged['listings']:
        pid = listing['id']
        if pid in hr_ids:
            for key in ('bound_source_id','source_relation','observation','current_platform_fields',
                        'catalog_fields','formal_fields','local_sync','url','record_type','notes','platform_group'):
                if key in ll[pid]:
                    listing[key] = copy.deepcopy(ll[pid][key])
            field = 'source_replacement' if pid in replacement_ids else 'source_binding_reconciliation'
            listing.setdefault('optimization',{})[field] = copy.deepcopy(ll[pid]['optimization'][field])
            current = ROOT / ll[pid].get('formal_fields',{}).get('file','missing')
            if current.is_file() and load(str(current.relative_to(ROOT))).get('sanitized_fields'):
                raw = current.read_bytes().replace(b'\r\n',b'\n')
                safe(json.loads(raw))
                frozen[current.relative_to(ROOT).as_posix()] = raw
        if pid in public_ids:
            for key in ('company_bundle','factory_gallery'):
                listing.setdefault('optimization',{})[key] = copy.deepcopy(ll[pid]['optimization'][key])
    task = next(x for x in live['workstreams'] if x['name']=='HR缺货源实款替换')
    merged['workstreams'] = [x for x in merged['workstreams'] if x['name']!=task['name']] + [copy.deepcopy(task)]
    merged['updated_on'] = live['updated_on']
    safe(merged)
    frozen[REG] = (json.dumps(merged,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    sys.path.insert(0,str(Path(__file__).parent))
    import build_product_workspace as workspace
    errors = workspace.validate(merged)
    baseline_errors = workspace.validate(baseline)
    assert set(errors) <= set(baseline_errors), errors
    assert not any(pid in error for pid in hr_ids for error in errors), errors
    for path, raw in workspace.build(merged).items():
        relative = path.relative_to(ROOT) if path.is_absolute() else path
        frozen[relative.as_posix()] = raw
    with tempfile.TemporaryDirectory(prefix='hr-public-git-',dir=ROOT/'99_临时区/HR实源替换') as temporary:
        env = dict(os.environ,GIT_INDEX_FILE=str(Path(temporary)/'index'))
        git('read-tree',base,env=env)
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
        assert set(changed) <= set(frozen)
        assert git('rev-parse','HEAD').decode().strip() == head
        assert git('write-tree').decode().strip() == original_index
        if args.check_only:
            print('EXACT_TASK_PUBLIC_SCOPE_PASS',len(changed),'HR IDs',len(hr_ids),'PUBLIC IDs',len(public_ids),'BASELINE_ONLY_ALIAS_ISSUES',len(baseline_errors))
            return
        message = b'feat: synchronize actual HR sources with approved products and prevent duplicate replacements\n'
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
