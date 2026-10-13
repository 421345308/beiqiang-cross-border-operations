"""Consolidate two evidence-confirmed duplicate identities without removing originals."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REGISTRY=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
OLD='01_产品资产/02_可发布素材/00_最终上传/BQ063_7212'
NEW='01_产品资产/02_可发布素材/00_最终上传/BQ028_BISCUIT/历史准备_原BQ063'
REPORT=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/素材位置调整.json'

def hashes(folder):
    return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    data=json.loads(REGISTRY.read_text(encoding='utf-8-sig'));products={p['id']:p for p in data['products']}
    if 'BQ063' not in products and 'HR039' not in products:print('Already consolidated');return
    # Exact source, original model, factual preparation and historical successful
    # HR039 copy-identity evidence all corroborate the two pairs.
    a,b=products['BQ028'],products['BQ063']
    if a.get('reference_source_id')!=b.get('reference_source_id'):raise ValueError('Source conflict')
    raw=ROOT/b['raw_packages'][0]/'source.json'
    source=json.loads(raw.read_text(encoding='utf-8-sig'))
    if source.get('artno')!='7212' or source.get('detail_url')!='https://bqgcd.sooxie.com/detail/2046059':raise ValueError('Original evidence changed')
    form=ROOT/a['local_assets']['current_fields_file']
    if '7212' not in form.read_text(encoding='utf-8-sig'):raise ValueError('Old model unverified')
    hr=ROOT/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR系列货源发货与图片总表.md'
    if '原平台型号 `BQ036 / 8025` 是复制已核实 8025 商品结构' not in hr.read_text(encoding='utf-8-sig'):raise ValueError('8025 identity proof missing')
    src=(ROOT/OLD).resolve();dst=(ROOT/NEW).resolve();boundary=Path('E:/贝强大文件/01_产品资产/02_可发布素材/00_最终上传').resolve()
    for path in (src,dst):
        if not path.is_relative_to(boundary):raise ValueError('Resolved path outside exact asset boundary')
    if src.is_symlink() or any(src.rglob('.git')):raise ValueError('Unexpected linked/nested repository')
    before=hashes(src)
    print(json.dumps({'source':str(src),'target':str(dst),'files':len(before),'action':'move preparation into existing BQ028; raw packages untouched'},ensure_ascii=False),flush=True)
    if not args.apply:return
    if dst.exists():raise ValueError('Destination already exists; no overwrite')
    src.rename(dst)
    if hashes(dst)!=before:raise ValueError('Moved file hash verification failed')
    note=dst/'00_上架填写表.md'
    note.write_text('> 历史准备资料：原BQ063经原始货号7212、同一来源及颜色尺码核对，属于BQ028。仅作可追溯备选素材，禁止按新鞋型再次发布；当前资料以BQ028商品档案为准。\n\n'+note.read_text(encoding='utf-8-sig'),encoding='utf-8')
    # Repoint references in project business text; don't rewrite raw packages,
    # historical API receipts, hashed imported evidence or other tasks.
    changed=[]
    for top in ['00_总控台','02_Alibaba运营','08_工具链']:
        for path in (ROOT/top).rglob('*'):
            if path.suffix not in {'.md','.py','.json','.csv','.html'} or path in {REGISTRY,REPORT,Path(__file__).resolve()}:continue
            if '目录对账/当前平台目录/商品' in path.as_posix():continue
            try:text=path.read_text(encoding='utf-8-sig')
            except (UnicodeError,OSError):continue
            if OLD in text:
                path.write_text(text.replace(OLD,NEW),encoding='utf-8');changed.append(path.relative_to(ROOT).as_posix())
    # Registry paths are updated recursively, including imported reference metadata.
    data=json.loads(json.dumps(data,ensure_ascii=False).replace(OLD,NEW));products={p['id']:p for p in data['products']}
    for canonical,alias in [('BQ028','BQ063'),('BQ036','HR039')]:
        keep,extra=products[canonical],products[alias]
        for field in ['aliases','raw_packages','evidence','candidate_source_ids','notes']:
            keep[field]=list(dict.fromkeys(keep.get(field,[])+extra.get(field,[])))
        keep['notes'].append(f'{alias}为同一来源、原货号与实物结构的历史内部别名；已合为{canonical}唯一身份，既有商品ID各自保留字段及验收。')
        if alias=='BQ063':keep.setdefault('historical_asset_roots',[]).append(NEW)
        if alias=='HR039':keep['evidence'].append(hr.relative_to(ROOT).as_posix())
        keep['next_action']='从统一档案核每个现有ID正式字段、实物来源和公开呈现；内部别名不再作为新增鞋型。'
        for listing in data['listings']:
            if listing['product_id']==alias:listing['product_id']=canonical
        data['products']=[p for p in data['products'] if p['id']!=alias]
    data.setdefault('identity_consolidation',[]).extend([{'canonical':'BQ028','aliases':['BQ063'],'source_id':'src-32ae508d4363','evidence':[raw.relative_to(ROOT).as_posix(),form.relative_to(ROOT).as_posix(),NEW+'/00_上架填写表.md']},{'canonical':'BQ036','aliases':['HR039'],'source_id':'src-a4697dab9e6e','evidence':[hr.relative_to(ROOT).as_posix()]}])
    REGISTRY.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    old_report=json.loads(REPORT.read_text(encoding='utf-8'))
    old_report.setdefault('alias_consolidation_moves',[]).append({'at':datetime.now(timezone.utc).isoformat(),'source':OLD,'target':NEW,'hashes_before':before,'hashes_after_move':before,'files':len(before),'note_added_after_hash_check':NEW+'/00_上架填写表.md','references_repaired':changed})
    REPORT.write_text(json.dumps(old_report,ensure_ascii=False,indent=2),encoding='utf-8')
    for alias,canonical in [('BQ063','BQ028'),('HR039','BQ036')]:
        path=ROOT/'02_Alibaba运营/02_单品优化记录/商品档案'/alias/'README.md'
        path.write_text(f'# {alias} 历史别名\n\n本编号归并到[{canonical}唯一商品档案](../{canonical}/README.md)。本页只跳转，不维护第二份商品资料或独立鞋型。\n',encoding='utf-8')
    print(json.dumps({'products':len(data['products']),'aliases_preserved':64,'moved_files':len(before),'references_repaired':changed},ensure_ascii=False))

if __name__=='__main__':main()
