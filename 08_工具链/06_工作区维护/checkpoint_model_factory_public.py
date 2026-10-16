"""Export only this goods-number/factory-gallery task through an isolated index.
Leaves shared HEAD/index and unrelated staged/uncommitted work untouched.
Public product fields and public source references only; raw identity stays local.
"""
from pathlib import Path
from copy import deepcopy
import argparse,json,hashlib,os,subprocess,tempfile,sys,io
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import checkpoint_hr_source_public as policy
import build_product_workspace as views
sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/国际站扩品'))
import normalize_models_factory_gallery as n
def raw_json(v):return(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8')
def main():
 sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser();ap.add_argument('--check-only',action='store_true');args=ap.parse_args();branch='codex/hr-source-replacement';git=policy.git
 assert git('remote','get-url','origin').decode().strip()=='https://github.com/421345308/beiqiang-cross-border-operations.git'
 head=git('rev-parse','HEAD').decode().strip();index=git('write-tree').decode().strip();base=git('rev-parse','refs/heads/'+branch).decode().strip()
 def base_json(path):return json.loads(git('show',base+':'+path))
 reg_path=n.rel(n.REG);live=n.load(n.REG);merged=base_json(reg_path);baseline=set(views.validate(merged));new_products={p['id']:p for p in live['products']};new_links={l['id']:l for l in live['listings']};scope=n.load(n.BASE/'范围.json');target_ids={z['id']for z in scope['targets']};changed_fact_paths=set()
 # HR039 already shares BQ036's exact adopted source in both snapshots. Its
 # current identity was consolidated before this migration; never resurrect it
 # as a second product just because the public branch still has the old row.
 for old in list(merged['products']):
  if old['id']in new_products:continue
  assert old['id']=='HR039'and 'HR039'in new_products['BQ036']['aliases']
  assert old['adopted_source_id']==new_products['BQ036']['adopted_source_id']
  assert all(l['id']in target_ids and new_links[l['id']]['product_id']=='BQ036'for l in merged['listings']if l['product_id']=='HR039')
  merged['products'].remove(old)
 for p in merged['products']:
  fresh=new_products[p['id']]
  for key in ('current_model','supply_mode'):
   if key in fresh:p[key]=deepcopy(fresh[key])
  if fresh.get('current_model')and p['id'].startswith('HR'):p['next_action']=fresh['next_action']
  if fresh.get('current_model')or fresh.get('local_assets',{}).get('current_gallery_by_id'):
   p['aliases']=deepcopy(fresh['aliases']);p.setdefault('local_assets',{})['current_gallery_by_id']=deepcopy(fresh.get('local_assets',{}).get('current_gallery_by_id',{}))
   f=p.get('local_assets',{}).get('current_fields_file')
   if f and f.endswith('事实与页面计划.json'):changed_fact_paths.add(f)
  if fresh.get('classification',{}).get('platform_category_ids'):
   p.setdefault('classification',{})['platform_category_ids']=deepcopy(fresh['classification']['platform_category_ids'])
  if p['id']=='LQ-2520':
   for key in ('publication_disposition','next_action'):
    if key in fresh:p[key]=deepcopy(fresh[key])
 for l in merged['listings']:
  if l['id']not in target_ids:continue
  fresh=new_links[l['id']]
  if l['product_id']!=fresh['product_id']:
   assert l['product_id']=='HR039'and fresh['product_id']=='BQ036';l['product_id']='BQ036'
  for key in ('model','legacy_model_aliases','observation','current_platform_fields','catalog_fields','formal_fields','local_sync','url','catalog_presence'):
   if key in fresh:l[key]=deepcopy(fresh[key])
  opt=fresh.get('optimization',{}).get('model_factory_normalization')
  if opt:l.setdefault('optimization',{})['model_factory_normalization']=deepcopy(opt)
 for work in merged.get('workstreams',[]):
  if work['name']in('路崎宽头/户外全分类','HR缺货源实款替换'):
   fresh=next(w for w in live['workstreams']if w['name']==work['name']);work['next_action']=fresh['next_action']
   if work['name']=='HR缺货源实款替换':work['status']=fresh['status'];work['evidence']=deepcopy(fresh['evidence'])
 merged['updated_on']=live['updated_on'];merged['model_factory_normalization']=deepcopy(live['model_factory_normalization']);assert set(views.validate(merged))<=baseline
 frozen={reg_path:raw_json(merged)}
 frozen.update({p.as_posix():body for p,body in views.build(merged).items()})
 names=['normalize_models_factory_gallery.py','sync_models_factory_gallery.py','audit_models_factory_prepared.py','audit_models_factory_completion.py','test_model_factory_preservation.py','repair_model_factory_quality.py','recover_category_reset_skus.py','schema_publish_contract.py','publish_hot_rank_hr_a_batch.py','publish_reviewed_luqi.py','verify_hr_real_sources.py','sync_hr_real_sources.py']
 paths=['08_工具链/01_业务脚本/国际站扩品/'+x for x in names]+['08_工具链/01_业务脚本/国际站扩品/README.md','08_工具链/06_工作区维护/build_product_workspace.py','08_工具链/06_工作区维护/product_dossiers.py','08_工具链/06_工作区维护/checkpoint_model_factory_public.py','08_工具链/01_业务脚本/商品图片与审计/factory_assets.py','02_Alibaba运营/00_运营SOP/国际站商品全生命周期SOP.md',n.rel(n.BASE.parent/'README.md'),n.rel(n.ENTRY/'README.md'),n.rel(n.ENTRY/'共用主图.json'),n.rel(n.ENTRY/'共用主图公开映射.json'),n.rel(n.ENTRY/'共用主图图链像素核验.json')]
 # Current scoped submission and verified-TLS native transport are required by
 # these controllers. The owner explicitly authorized the previous tool/SOP
 # work as well; exporting the old publisher would make the new tools unusable.
 paths.append('.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py')
 luqi='02_Alibaba运营/05_扩品工程/执行记录/路崎宽头户外_2026-10-08'
 paths +=[luqi+'/README.md',luqi+'/待补资料与局部问题.json',luqi+'/质量复核_2026-10-09/全分类处理队列.json']
 paths +=[n.rel(n.BASE/x)for x in ('范围.json','当前状态.json','准备载荷核验.json','完成核验.json','平台退回诊断.json')]+[n.rel(n.ENTRY/'预览.html')]
 for z in scope['targets']:
  f=n.BASE/'商品'/z['id']
  for name in ('prepared.json','verification.json','双改核验.json','当前图库与货号.json'):
   if(f/name).exists():paths.append(n.rel(f/name))
  for name in ('prepared.json','update_once.json','update_receipt.json','verification.json','fields_overlay.json'):
   if(f/'质量修正'/name).exists():paths.append(n.rel(f/'质量修正'/name))
  for name in ('prepared.json','update_once.json','update_receipt.json','verification.json','SKU编号变更映射.json'):
   if(f/'质量修正/规格恢复'/name).exists():paths.append(n.rel(f/'质量修正/规格恢复'/name))
  # Formal values are a public derivative, never raw account identity.
  if(n.CURRENT/z['id']/'formal_get.json').exists()and(f/'双改核验.json').exists():
   for name in ('formal_get.json','formal_render.json'):
    p=n.CURRENT/z['id']/name
    if p.exists():frozen[n.rel(p)]=raw_json(policy.public_product_snapshot(n.load(p)))
 for path in paths:
  p=ROOT/path
  if p.suffix=='.json':
   value=policy.public_product_snapshot(n.load(p));policy.safe(value);frozen[path]=raw_json(value)
  else:frozen[path]=p.read_bytes()
 fact_paths=sorted(changed_fact_paths)
 if fact_paths:
  stream=io.BytesIO(git('cat-file','--batch',input=''.join(base+':'+p+'\n'for p in fact_paths).encode('utf8')));base_facts={}
  for path in fact_paths:
   header=stream.readline().decode('ascii').split();assert len(header)==3 and header[1]=='blob',path
   raw=stream.read(int(header[2]));assert stream.read(1)==b'\n';base_facts[path]=json.loads(raw)
 for path in fact_paths:
  doc=base_facts[path];fresh=n.load(ROOT/path)
  for key in ('model_numbers','current_models_by_id','model_migration_evidence','current_platform_category_by_id','category_scope'):
   if key in fresh:doc[key]=deepcopy(fresh[key])
  frozen[path]=raw_json(doc)
 # Match normal Git text normalization without rewriting shared work files.
 frozen={path:raw.replace(b'\r\n',b'\n')for path,raw in frozen.items()}
 for path,raw in frozen.items():
  assert Path(path).suffix.lower()in('.md','.json','.py','.html','.csv'),path
  assert not policy.SECRET.search(raw.decode('utf-8-sig')),path
  if path.endswith('.json'):policy.safe(json.loads(raw))
 with tempfile.TemporaryDirectory(prefix='model-factory-public-',dir=ROOT/'99_临时区/HR货号与主图')as tmp:
  env=dict(os.environ,GIT_INDEX_FILE=str(Path(tmp)/'index'));git('read-tree',base,env=env);rows=list(frozen.items());files=[]
  for i,(path,raw)in enumerate(rows):p=Path(tmp)/str(i);p.write_bytes(raw);files.append(p.as_posix())
  blobs=git('hash-object','-w','--no-filters','--stdin-paths',input=('\n'.join(files)+'\n').encode('utf8')).decode().splitlines();assert len(blobs)==len(rows)
  entries=[]
  for(path,raw),blob in zip(rows,blobs):
   assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blob;assert not any(c in path for c in '\n\r\t');entries.append('100644 '+blob+'\t'+path+'\n')
  git('update-index','--index-info',input=''.join(entries).encode('utf8'),env=env);tree=git('write-tree',env=env).decode().strip();assert not git('diff','--check',base,tree)
  changed=[p for p in git('diff','--name-only','-z',base,tree).decode().split('\0')if p];assert set(changed)<=set(frozen);assert git('rev-parse','HEAD').decode().strip()==head and git('write-tree').decode().strip()==index
  if args.check_only:print('PUBLIC_SCOPE_PASS',len(changed),'TARGET_IDS',len(target_ids),'BASELINE_ONLY_ISSUES',len(baseline));return
  if not changed:print('NO_NEW_TASK_CHANGES');return
  commit=git('commit-tree',tree,'-p',base,input=b'feat: replace legacy HR models and unify verified factory gallery image\n').decode().strip();git('update-ref','refs/heads/'+branch,commit,base)
  n.save(n.BASE/'Git阶段提交.json',{'branch':branch,'base':base,'commit':commit,'files':changed,'root_HEAD_and_index_unchanged':True,'raw_accounts_sessions_media_excluded':True});print(json.dumps({'commit':commit,'branch':branch,'files':len(changed)}))
if __name__=='__main__':main()
