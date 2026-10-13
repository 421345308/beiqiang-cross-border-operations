"""Reuse verified existing current bytes instead of keeping a second CDN cache copy."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
AREA=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    media=json.loads((AREA/'当前素材清单.json').read_text(encoding='utf-8'))
    audit=json.loads((AREA/'本地资产唯一性.json').read_text(encoding='utf-8'))
    reusable={x['sha256']:x['canonical'] for x in audit['items']}
    boundary=Path('E:/贝强大文件/01_产品资产/05_平台当前素材').resolve()
    replacements={}
    for asset in media['assets'].values():
        sha=asset.get('sha256');canonical=reusable.get(sha)
        if not canonical or asset.get('file')==canonical:continue
        source=(ROOT/asset['file']).resolve();target=(ROOT/canonical).resolve()
        if not source.is_relative_to(boundary) or source.is_symlink():raise ValueError('Unexpected cache deletion target')
        expected=Path('E:/贝强大文件/01_产品资产/02_可发布素材/00_最终上传').resolve()
        if not target.is_relative_to(expected):raise ValueError('Unexpected reusable current path')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=sha or hashlib.sha256(target.read_bytes()).hexdigest()!=sha:raise ValueError('Hash mismatch')
        replacements[asset['file']]={'canonical':canonical,'sha256':sha,'bytes':source.stat().st_size}
    print(json.dumps({'verified_duplicate_files':len(replacements),'cache_boundary':str(boundary),'bytes':sum(x['bytes'] for x in replacements.values())},ensure_ascii=False),flush=True)
    if not args.apply:return
    # Publish updated references before deleting duplicate cached bytes.
    for asset in media['assets'].values():
        if asset.get('file') in replacements:
            asset['file']=replacements[asset['file']]['canonical'];asset['reuses_verified_current_asset']=True
    (AREA/'当前素材清单.json').write_text(json.dumps(media,ensure_ascii=False,indent=2),encoding='utf-8')
    for source,record in replacements.items():
        path=(ROOT/source).resolve()
        if not path.is_relative_to(boundary) or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Delete precheck changed')
        path.unlink()
    audit['platform_cache_reuse']={'deleted_exact_cache_copies':len(replacements),'bytes_removed':sum(x['bytes'] for x in replacements.values()),'items':replacements,'scope':'已核相同字节的本地当前素材复用；原始包、公司原件与回执不删除'}
    (AREA/'本地资产唯一性.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    from build_product_workspace import build,validate,write_generated
    data=json.loads((ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json').read_text(encoding='utf-8-sig'))
    if validate(data):raise ValueError('Registry needs validation before derived links regenerate')
    for path,body in build(data).items():
        target=ROOT/path
        write_generated(target,body)
    print('Exact cache duplicates removed; references regenerated')

if __name__=='__main__':main()
