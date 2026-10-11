"""Single factory-image entry; current assets and read-only legacy source resolution.
No image generation, upload or product mutation. Legacy lookup is for receipt/
renderer replay only; it must never authorize new online bindings.
"""
from pathlib import Path
import argparse
import hashlib
import json
import fnmatch
import os
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote, parse_qs

ROOT=Path(__file__).resolve().parents[3]
ENTRY=ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情'
def manifest():
    return json.loads((ENTRY/'制作档案.json').read_text(encoding='utf8'))
def current_asset(role):
    row=manifest()['assets'][role]
    p=ROOT/row['path']
    if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
        raise ValueError('Current image differs from reviewed asset: '+role)
    return p
def current_root():
    return ROOT/manifest()['current_media_root']
def _aliases():
    return json.loads((ENTRY/'素材整理.json').read_text(encoding='utf8'))['aliases']
class LegacyAssetPath(os.PathLike):
    """Resolve an old local filename to its sole retained original/evidence file."""
    def __init__(self,relative):self.relative=relative.replace('\\','/').strip('/')
    def __truediv__(self,item):return LegacyAssetPath(self.relative+'/'+str(item))
    def _path(self):
        row=_aliases().get(self.relative)
        if not row or not row['target']:
            raise FileNotFoundError('Retired factory asset; use shared factory entry: '+self.relative)
        p=ROOT/row['target']
        if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Legacy evidence identity mismatch')
        return p
    def __fspath__(self):return str(self._path())
    def __str__(self):return str(self._path())
    def __getattr__(self,name):return getattr(self._path(),name)
    def glob(self,pattern):
        seen=set();prefix=self.relative+'/'
        for src,row in _aliases().items():
            suffix=src.removeprefix(prefix)
            if src.startswith(prefix) and '/' not in suffix and row['target'] and fnmatch.fnmatch(suffix,pattern):
                p=ROOT/row['target']
                if p not in seen:seen.add(p);yield p
def legacy_asset(relative):return LegacyAssetPath(relative)
def check_preview(m):
    class Images(HTMLParser):
        def __init__(self):super().__init__();self.rows=[]
        def handle_starttag(self,tag,attrs):
            if tag=='img':self.rows.append(dict(attrs))
    page=Images();page.feed((ENTRY/'预览.html').read_text(encoding='utf8'))
    assert len(page.rows)==5,'Preview must reference exactly five current images'
    assert {row.get('alt') for row in page.rows}==set(m['assets'])
    for row in page.rows:
        asset=m['assets'][row['alt']];url=urlsplit(row['src'])
        assert not url.scheme and not url.netloc,'Preview image must be local'
        assert (ENTRY/unquote(url.path)).resolve()==(ROOT/asset['path']).resolve()
        assert parse_qs(url.query).get('v')==[asset['sha256']],row['alt']+' preview version is stale'

def check():
    m=manifest();plan=json.loads((ENTRY/'素材整理.json').read_text(encoding='utf8'))
    assert set(m['assets'])=={'C1','C2','C3','C4','C5'}
    assert {p.name for p in current_root().glob('*')}=={Path(v['path']).name for v in m['assets'].values()}
    for role in m['assets']:current_asset(role)
    check_preview(m)
    if 'coverage_audit' in m:
        # Verify the explicit current photo allocation, alongside manual role review.
        photo_hashes={}
        for role,rows in m['active_sources'].items():
            photo_hashes[role]={hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in rows}
        roles=list(photo_hashes)
        for i,role in enumerate(roles):
            for other in roles[i+1:]:
                assert not photo_hashes[role] & photo_hashes[other],(role,other)
        assert m['coverage_audit']['visual_source_count']==sum(map(len,photo_hashes.values()))
    for row in m['originals']:
        p=ROOT/row['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    for src,row in plan['aliases'].items():
        assert not (ROOT/src).exists(),src
        if row['target']:legacy_asset(src)._path()
    assert plan['originals_retained']==33 and plan['redundant_or_obsolete_images_removed']==65
    # Local asset integrity does not depend on the publishing stage. Verify
    # uploaded-bank claims with their own evidence; bank upload is not binding.
    bank_images=0
    if m.get('online_state',{}).get('uploaded'):
        bank=json.loads((ENTRY/m['online_state']['bank_evidence']).read_text(encoding='utf8'))
        pixels=json.loads((ENTRY/m['online_state']['bank_pixels_evidence']).read_text(encoding='utf8'))
        assert bank['asset_version']==pixels['asset_version']==m['version']
        assert pixels['status']=='FIVE_BANK_PIXELS_EXACT_PASS'
        assert set(bank['items'])==set(m['assets'])
        for role,row in bank['items'].items():
            assert row['status']=='UPLOADED_OFFICIAL_BANK' and row['file_id']
            assert row['sha256']==m['assets'][role]['sha256']
        bank_images=len(bank['items'])
    return {'ok':True,'current_images':5,'originals':33,'historical_unique':34,
            'redundant_or_obsolete_images_removed':65,'preview_images_verified':5,
            'preview_versions_match_current_images':True,'bank_images_verified':bank_images,
            'scope':'Local media, source hashes, preview and recorded bank evidence; no product binding/public-page acceptance',
            'state':m['status']}
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--asset',choices=['C1','C2','C3','C4','C5'])
    args=parser.parse_args()
    if args.asset:print(current_asset(args.asset))
    else:print(json.dumps(check(),ensure_ascii=False))

