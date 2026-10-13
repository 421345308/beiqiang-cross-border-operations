"""Bind already-real HR pages to their actual sources using explicit evidence.

Read-only toward Alibaba. Never infer source identity from titles or a score.
"""
from pathlib import Path
from urllib.parse import urlsplit
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,sys,argparse,time

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
REG=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
sys.path.insert(0,str(ROOT/'08_工具链/06_工作区维护'))
import build_product_workspace as workspace

def load(p):return json.loads((ROOT/p).read_text(encoding='utf8'))
def save(p,v):
    path=ROOT/p;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def ident(url):return urlsplit(url).path.rsplit('/',1)[-1].split('.')[0]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--family');args=parser.parse_args()
    catalog=load('99_临时区/HR实源替换/全量目录/catalog.json')
    assert catalog['complete']
    live={str(x['id']):x for x in catalog['products']}
    profiles=load(BASE.relative_to(ROOT)/'已有实款对应.json')
    registry=load(REG.relative_to(ROOT));products={p['id']:p for p in registry['products']}
    now=datetime.now(timezone.utc).isoformat()
    for profile in profiles['families']:
        if args.family and profile['family']!=args.family:continue
        family=profile['family'];bank=load(profile['approved_bank']);rows=[]
        root_map=profile.get('evidence_format')=='ROOT_APPROVED_MAP'
        current_five=profile.get('evidence_format') in ['CURRENT_PREFIXLESS_BANK','CURRENT_ROLE_MAP','CURRENT_ROLE_LIST','LAYERED_APPROVED_BANK']
        if current_five:
            visual=load(profile['approved_visual']);fact=load(profile['source_fact_file'])
            if profile['evidence_format']=='LAYERED_APPROVED_BANK':
                assert family=='HR044' and fact['source_model']=='L795' and fact['url']==profile['source_url']
                from bs4 import BeautifulSoup
                source_file=ROOT/fact['source_page_file']
                assert hashlib.sha256(source_file.read_bytes()).hexdigest()==fact['source_page_sha256']
                soup=BeautifulSoup(source_file.read_text(encoding='utf8'),'html.parser')
                table={n.get_text(strip=True):n.find_next_sibling('dd').get_text(' ',strip=True)for n in soup.select('dt.product-attrs-label')}
                assert table['Model NO.']=='L795'
                assert {k:table[k]for k in profile['materials']}==profile['materials']
                assert visual['approved'] and visual['all_current_main_roles_hash_verified']
                for source in visual['originals']:
                    assert hashlib.sha256((ROOT/source['file']).read_bytes()).hexdigest()==source['sha256']
                for role,row in bank.items():
                    assert row['sha256']==visual['roles'][role]['sha256']==hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()
                raw_evidence=profile['approved_visual']
            elif profile['evidence_format']=='CURRENT_PREFIXLESS_BANK':
                assert visual['status']=='ROOT_FULL_FRAME_11_ASSETS_APPROVED_BANK_ONLY'
                assert fact['source']['model']==profile['source_model'] and fact['source']['url']==profile['source_url']
                raw_evidence=profile['source_fact_file']
                for role in ['RAW_BLACK','RAW_BLUE']:
                    row=bank[role];assert row['exactBytePass']
                    assert hashlib.sha256(Path(row['sourcePath']).read_bytes()).hexdigest()==row['sourceSha256']
                for role in ['M1_hero_black','M2_option_size','M3_visible_details','M4_materials','M5_quote_inputs']:
                    row=bank[role];asset=visual['assets'][role]
                    assert row['exactBytePass'] and asset['rootFullFramePass'] and row['sourceSha256']==asset['sourceSha256']
                    assert hashlib.sha256(Path(row['sourcePath']).read_bytes()).hexdigest()==row['sourceSha256']
            elif profile['evidence_format']=='CURRENT_ROLE_MAP':
                assert visual['all30FullFrameViewed']
                frozen=load(fact['sourceFactFile']);assert hashlib.sha256(Path(fact['sourceFactFile']).read_bytes()).hexdigest()==fact['sourceFactSha256']
                assert frozen['listing_source']['url']==profile['source_url'] and frozen['product_identity']['model_number']==profile['source_model']
                assert fact['fixedColors']==profile['colors'] and fact['sizesEU']==profile['sizes_eu']
                originals=[x for x in visual['assets'].values() if x.get('byteIdenticalOriginal')];assert originals
                for item in originals:
                    for file in item['originalPhotos']:assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==item['sourceSha256']
                for role,row in bank.items():
                    if '_M'in role or '_D'in role:
                        asset=visual['assets'][role];assert row['exactBytePass'] and asset['fullVisualReview']=='ROOT_PASS'
                        assert row['sourceSha256']==asset['sourceSha256']==hashlib.sha256(Path(row['sourcePath']).read_bytes()).hexdigest()
                raw_evidence=profile['approved_visual']
            else:
                assert visual['all30FullFrameViewed'] and fact['sourceModel']==profile['source_model']
                route=next(x for x in load(profile['source_fact_routes'])['families'] if x['family']==family)
                assert route['source_url']==profile['source_url'] and profile['source_model'] in route['source_model']
                reviewed={x['role']:x for x in visual['records']}
                for row in bank:
                    asset=reviewed[row['role']];assert row['exactBytePass'] and row['success']
                    assert row['sha256']==asset['sha256']==hashlib.sha256(Path(asset['path']).read_bytes()).hexdigest()
                    for original in asset['sources']:assert hashlib.sha256(Path(original['path']).read_bytes()).hexdigest()==original['sha256']
                raw_evidence=profile['approved_visual']
        elif root_map:
            plan=load(profile['approved_buyer_plan']);visual=load(profile['approved_visual'])
            assert plan['sourceModelInternalOnly']==profile['source_model']
            assert plan['sourcePage']==profile['source_url']
            assert visual['status']=='ROOT_FULL_FRAME_APPROVED'
            raw_photos=plan.get('colors')or[{'rawImage':plan['sourceRawImage'],'rawSHA256':plan['sourceRawSHA256']}]
            if visual.get('selectedOriginal'):
                selected=visual['selectedOriginal']
                raw_photos.append({'rawImage':selected['selectedRawImage'],'rawSHA256':selected['selectedSHA256']})
            for raw in raw_photos:
                assert hashlib.sha256(Path(raw['rawImage'].replace('\\\\','\\')).read_bytes()).hexdigest()==raw['rawSHA256']
            for role in ['M1','M2','M3','M4','M5']:
                row=bank[role];asset=visual['assets'][role]
                assert row['rootExactByteVerified']and row['sha256']==asset['sourceSha256']
                assert hashlib.sha256(Path(row['sourcePath'].replace('\\\\','\\')).read_bytes()).hexdigest()==row['sha256']
            raw_evidence=profile['approved_visual']
        elif profile.get('raw_image_manifest'):
            assert bank['all_pass']
            manifest=load(profile['raw_image_manifest']);assert manifest['sourcePage']==profile['source_url']
            for raw in manifest['images']:
                path=Path(raw['localFile'].replace('\\\\','\\'))
                assert hashlib.sha256(path.read_bytes()).hexdigest()==raw['sha256']
            raw_evidence=profile['raw_image_manifest']
        else:
            assert bank['all_pass']
            facts=load(profile['source_fact_routes'])
            route=next(f for f in facts['families']if f['family']==family)
            assert profile['source_model'].casefold()in route['source_model'].casefold()
            if route.get('source_url'):assert route['source_url']==profile['source_url']
            frozen=load(profile['approved_frozen_plan']);assert profile['source_model'].casefold()in frozen['sourceModel'].casefold()
            visual=load(profile['approved_visual']);assert visual['all30FullFrameViewed']
            originals=[v for v in visual['assets'].values()if v.get('byteIdenticalOriginal')]
            assert originals
            for item in originals:
                for file in item['originalPhotos']:
                    path=Path(file.replace('\\\\','\\'))
                    assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sourceSha256']
            raw_evidence=profile['approved_visual']
        ls=[l for l in registry['listings']if l.get('product_id')==family]
        assert {l['id']for l in ls}==set(profile['ids'])
        for l in ls:
            pid=l['id'];variant=l['model'].split('-')[-1];p=live[pid]
            if current_five:
                bank_rows=list(bank.values())if isinstance(bank,dict) else bank
                expected=[x for x in bank_rows if (x['role'].startswith(variant+'_M') or profile['evidence_format']=='CURRENT_PREFIXLESS_BANK' and x['role'].startswith('M')) and not x['role'].startswith(variant+'_M6')]
                assert len(expected)==5 and len(p['main_image']['images'])==6
                assert Counter(ident(x['url'])for x in expected)==Counter(ident(u)for u in p['main_image']['images'][:5])
                hero=next(x for x in expected if x['role'].startswith(variant+'_M1')or x['role'].startswith('M1_'))
                assert ident(hero['url'])==ident(p['main_image']['images'][0])
            elif root_map:
                expected=[bank['M'+str(i)]for i in range(1,6)]
                assert len(p['main_image']['images'])==6
                # Existing A/B/C use the same reviewed assets in different
                # gallery orders. Retain each link's exact formal sequence;
                # source identity requires the complete five-image multiset
                # and the reviewed M1 hero, without forcing A's order on B/C.
                assert ident(expected[0]['url'])==ident(p['main_image']['images'][0])
                assert Counter(ident(x['url'])for x in expected)==Counter(ident(u)for u in p['main_image']['images'][:5])
            else:
                expected=[x for x in bank['images']if x['role'].startswith(variant+'_M')]
                expected.sort(key=lambda x:int(x['role'].split('_M')[1]))
                assert len(expected)==6 and all(x.get('sameDecodedPixelPass')for x in expected)
                assert [ident(x['url'])for x in expected]==[ident(u)for u in p['main_image']['images']]
            f=Path('02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品')/pid/'formal_get.json'
            wrapper=load(f);g=wrapper['response']['product']
            assert g['status']=='approved'and g['display']=='Y'
            assert [ident(u)for u in g['main_image']['images']]==[ident(u)for u in p['main_image']['images']]
            attrs={a['attribute_name']:a['value_name']for a in g['attributes']}
            assert all(attrs[k].casefold()==v.casefold()for k,v in profile['materials'].items())
            sku=g['product_sku'];axes={str(a['attribute_id']):a['values']for a in sku['sku_attributes']}
            color_axes=[a for a in sku['sku_attributes']if a['attribute_name'].casefold()=='color']
            assert len(color_axes)==1
            color_id=str(color_axes[0]['attribute_id'])
            colors={str(v['value_id']):v['system_value_name']for v in axes[color_id]}
            sizes={str(v['value_id']):v['system_value_name']for v in axes['222038415']}
            assert set(colors.values())==set(profile['colors'])
            expected_sizes={str(n)for n in profile['sizes_eu']}
            assert {v.replace('EU','').strip()for v in sizes.values()}==expected_sizes
            pairs=Counter()
            for item in sku['skus']:
                values=json.loads(item['attr2_value'])
                pairs[(colors[str(values[color_id])],sizes[str(values['222038415'])].replace('EU','').strip())]+=1
            assert pairs==Counter((c,s)for c in profile['colors']for s in expected_sizes)
            rows.append({'id':pid,'model':l['model'],'formal_file':f.as_posix(),
                'formal_observed_at':wrapper['observed_at_utc'],'checks':{
                    'approved_actual_product_images_match':True,'whole_six_images_match_current_catalog':True,'raw_photo_hashes':True,
                    'materials_match_specific_model_table':True,'source_eu_cartesian':True,
                    'approved_y':True},'main_images':g['main_image']['images'],
                'sku_count':len(sku['skus'])})
        sid=profile['source_id'];source={'id':sid,'url':profile['source_url'],
            'shop_url':profile['source_url'].split('/product/')[0],
            'supplier':profile['supplier'],'model':profile['source_model'],
            'price':'未核当前进货报价','currency':'USD','unit':'双',
            'price_terms':'历史已采用实款对应恢复；当前数量、价格、包装及交期逐单询价，不从平台售价或样品费反推采购价。',
            'observed_at':profile['last_direct_source_date'],
            'evidence':[raw_evidence,profile['approved_bank'],
                (BASE/family/'来源与正式绑定核验.json').relative_to(ROOT).as_posix()]}
        registry['sources']=[s for s in registry['sources']if s['id']!=sid]+[source]
        product=products[family];product.update(source_state='ADOPTED',adopted_source_id=sid,candidate_source_ids=[sid])
        product['next_action']='已采用真实鞋型保持；原始像素、当前六图和EU材料对应已核，当前交易条件逐单确认，后续按本款质量问题优化。'
        product['local_assets'].update(current_fields_file=(BASE/family/'来源与正式绑定核验.json').relative_to(ROOT).as_posix(),state='EXISTING_REAL_SOURCE_FORMAL_BINDING_VERIFIED')
        proof={'family':family,'at':now,'state':'EXISTING_REAL_SOURCE_FORMAL_BINDING_VERIFIED',
               'source':source,'links':rows,'basis':profile['source_table_basis'],
               'source_current_access':profile['source_current_access'],
               'platform_mutation':'NONE_EXISTING_ACTUAL_SHOE_PRESERVED',
               'physical_stock':'NOT_CONFIRMED_ORDER_SPECIFIC'}
        save((BASE/family/'来源与正式绑定核验.json').relative_to(ROOT),proof)
        ref=(BASE/family/'来源与正式绑定核验.json').relative_to(ROOT).as_posix()
        product['evidence']=list(dict.fromkeys([*product.get('evidence',[]),ref]))
        for l in ls:
            l.update(bound_source_id=sid,source_relation='EXISTING_ACTUAL_SHOE_FORMAL_IMAGE_AND_SKU_MATCH')
            l['record_type']='当前实款正式绑定'
            l['notes']=f"现有真实鞋款{profile['source_model']}保持；已核当前六图、原件哈希、材料及EU组合对应。此处恢复货源绑定，不重复提交换款；交易条件按订单确认。"
            l.setdefault('optimization',{})['source_binding_reconciliation']={'state':proof['state'],'source_id':sid,'at':now,'evidence':[ref],'platform_mutation':'NONE'}
        print(family,'EXISTING_SOURCE_BOUND',len(rows),flush=True)
    errors=workspace.validate(registry);assert not errors,errors
    registry['updated_on']='2026-10-13';save(REG.relative_to(ROOT),registry)
    for p,data in workspace.build(registry).items():
        for attempt in range(3):
            try:
                workspace.write_generated(ROOT/p,data);break
            except PermissionError:
                if attempt==2:raise
                time.sleep(1)

if __name__=='__main__':main()
