"""Hash-verifiable duplicate cleanup confined to processed product assets.

Only exact copies in the processed archive with no explicit directory references
may be removed. Never deletes originals, receipts, videos or a junction tree.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / '01_产品资产/02_可发布素材'
REPORT = ROOT / '02_Alibaba运营/05_扩品工程/数据/目录对账/本地资产唯一性.json'
IMAGE_EXT = {'.jpg','.jpeg','.png','.webp','.avif'}


def digest(file):
    h = hashlib.sha256()
    with file.open('rb') as stream:
        while chunk := stream.read(1024*1024):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clean', action='store_true')
    args = parser.parse_args()
    intended = Path(r'E:\贝强大文件\01_产品资产\02_可发布素材').resolve()
    actual = ASSETS.resolve()
    if actual != intended:
        raise ValueError('Resolved asset root changed; review actual target before cleanup')
    indexed = defaultdict(list)
    count = 0
    for file in ASSETS.rglob('*'):
        if file.is_file() and file.suffix.lower() in IMAGE_EXT:
            indexed[digest(file)].append(file)
            count += 1
    results = []
    references = {}
    for sha, files in indexed.items():
        canonical = [p for p in files if '00_最终上传' in p.parts]
        if not canonical:
            continue
        keep = sorted(canonical, key=lambda p:len(str(p)))[0]
        for file in files:
            if '99_归档' not in file.parts:
                continue
            archive_index = file.parts.index('99_归档')
            directory_name = file.parts[archive_index+1]
            command = ['rg','-l','-F',directory_name,'00_总控台','02_Alibaba运营','07_知识库与Skills','08_工具链','.agents','-g','*.md','-g','*.json','-g','*.py','-g','*.ps1','-g','!**/本地资产唯一性.json']
            if directory_name not in references:
                search = subprocess.run(command, cwd=ROOT, capture_output=True)
                if search.returncode not in (0,1):
                    raise ValueError('Reference search failed; do not delete')
                references[directory_name] = search.returncode == 0
            referenced = references[directory_name]
            row = {'sha256':sha, 'path':file.relative_to(ROOT).as_posix(), 'canonical':keep.relative_to(ROOT).as_posix(), 'bytes':file.stat().st_size, 'state':'KEEP_REFERENCED' if referenced else 'EXACT_COPY_NO_EXPLICIT_REFERENCE'}
            if args.clean and not referenced:
                resolved = file.resolve()
                if not resolved.is_relative_to(intended/'99_归档') or file.is_symlink():
                    raise ValueError('Delete target escaped authorized processed archive')
                if digest(file) != sha or digest(keep) != sha:
                    raise ValueError('File changed since inventory; do not delete')
                file.unlink()
                row['state'] = 'DELETED_EXACT_COPY'
            results.append(row)
    summary = {'scope':'已扫描可发布素材；原始包/平台回执/其他业务未删除。不同版本或哈希不同不当重复', 'images_scanned':count, 'duplicates_against_current_assets':len(results), 'deleted':sum(x['state']=='DELETED_EXACT_COPY' for x in results), 'bytes_removed':sum(x['bytes'] for x in results if x['state']=='DELETED_EXACT_COPY'), 'items':results}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='items'},ensure_ascii=False))


if __name__ == '__main__':
    main()
