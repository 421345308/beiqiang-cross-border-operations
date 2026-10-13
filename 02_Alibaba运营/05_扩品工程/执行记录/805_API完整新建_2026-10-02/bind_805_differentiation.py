from pathlib import Path
import json,hashlib,datetime,shutil,sys,importlib.util
sys.dont_write_bytecode=True
W=Path(__file__).parent;O=W/'805_execution';P=Path(r'C:\Users\spq\Desktop\贝强')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,j):(O/n).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
register=P/'02_Alibaba运营/05_扩品工程/HR系列真实货源改造_2026-09-21/HR持续替换目标与货源队列_2026-10-02.md'
assert register.exists();shutil.copyfile(register,O/'existing_source_queue.md')
assets={x['name']:x for x in json.loads((O/'upload_ledger.json').read_text(encoding='utf-8'))['uploads']}
near=json.loads((O/'dedup_image_manifest.json').read_text(encoding='utf-8'))
structure={'HR003':'Full perforated suede driver with metal-ended cord, thick moccasin edge and brown segmented pebble sole','HR044':'Glossy penny-strap loafer with thick continuous black sole','HR020':'Short wide full-perforated diamond-textured vamp with elastic inserts thick collar and multilayer sole','HR006':'Unperforated suede driver with metallic braided trim and dark segmented sole','HR001':'Plain leather walking slip-on with thick dark sole','HR010':'Penny strap suede driver with black pebble sole','HR013':'Women low-cut plain suede flat with brown low sole','HR014':'Women suede penny strap contrast panel loafer','HR015':'Women low-cut closed heel suede flat with segmented sole','HR025':'Women buckled instep strap closed heel flat with pale thick sole','HR036':'Knit vamp slip-on walking shoe with segmented pale sole','BQ-004':'Multicolor lace-up knit sneaker','BQ':'Existing 3522 plain long U-shaped vamp with perforated surrounding panels and continuous pale sole'}
records={}
for x in near:
 if not x.get('path'):continue
 family=str(x['model']).split('-')[0]
 records[str(x['id'])]={'existing_family':family,'hero_review':{'content_key':structure.get(family,'Visually reviewed different shoe in dedup_contact.jpg'),'sha256':x['sha256'],'evidence':['dedup_contact.jpg','dedup_image_manifest.json','dedup_gate.json']},'search_intent':{'key':structure.get(family,'Existing different assortment'),'evidence':['dedup_gate.json']}}
evidence=[{'path':p.name,'sha256':sha(p),'kind':'catalog_snapshot'} for p in sorted(O.glob('live_catalog_*.flat.json'))]
evidence.extend([{'path':'existing_source_queue.md','sha256':sha(O/'existing_source_queue.md'),'kind':'source_register'},{'path':'dedup_gate.json','sha256':sha(O/'dedup_gate.json'),'kind':'visual_review'},{'path':'source/source_attributes.json','sha256':sha(O/'source/source_attributes.json'),'kind':'candidate_source'}])
context={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'coverage_limit':'Complete 370-row current API catalog, 32 nearby original heroes actually reviewed. Registry evidence supports source records where known; this is not external market-wide or IP clearance.','evidence_files':evidence,'source_records':records,'candidate':{'model_number':'BQ-D805','hero_url':assets['M1']['official_url'],'source':{'reference':'https://yut.sooxie.com/detail/559264','style':'805','evidence':['source/source.html','source/source_attributes.json','source/published_manifest.json','ownership.json'],'critical_facts':{'profile':'Closed heel low-top slip-on moc-toe casual shoe','upper_structure':'Double tassels, coarse visible moc-toe stitching and all-over embossed surface texture; upper composition unspecified','outsole_structure':'Five separate rubber contact pads and small heel-end extension','closure':'Slip-On','lining':'PU','functional_use':'Mens daily casual tassel driver-style assortment; no driving safety or tested grip claim'}},'search_intent':{'key':'Mens embossed double-tassel slip-on driving moccasins with segmented rubber pads and heel extension','evidence':['facts_and_copy.json','dedup_gate.json','source/published_manifest.json']},'hero_review':{'url':assets['M1']['official_url'],'sha256':assets['M1']['sha256'],'content_key':'805 red closed-heel double-tassel embossed moc-toe and separate black rubber sole pads, visible rear extension','label_status':'not_present','evidence':['visual_gate.json','assets/M1.jpg','asset_manifest.json']}}}
context['candidate']['hero_review']['aliases']=[assets['M1']['official_url'].removeprefix('https:')]
save('differentiation_review.json',context)
m=json.loads((O/'publish_manifest.json').read_text(encoding='utf-8'));m.update(differentiation_review='differentiation_review.json',differentiation_review_sha256=sha(O/'differentiation_review.json'));save('publish_manifest.json',m)
s=importlib.util.spec_from_file_location('publisher805',P/'08_工具链/01_业务脚本/国际站扩品/publish_hot_rank_hr_a_batch.py');pub=importlib.util.module_from_spec(s);s.loader.exec_module(pub)
listing=pub.load_submission_manifest(O/'publish_manifest.json','create',None);report=listing['differentiation_review'];assert report['status']=='PASS',report
assert report['evidence_provenance']['counts_match_reported_total'],report['evidence_provenance']
save('prepared_listing.json',listing);save('bound_differentiation_preflight.json',report)
print('Actual manifest preflight PASS; complete370 catalog and source-register hashes; hero model bound')
