"""Publish only this performance task with an isolated index; raw metrics stay local."""
from pathlib import Path
from copy import deepcopy
import sys,json,os,tempfile,hashlib,argparse
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import checkpoint_hr_source_public as policy
import build_product_workspace as views
sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/国际站经营诊断'))
import diagnose_product_performance as d
import apply_product_performance_actions as a
from sync_product_performance_actions import FOLDERS

def raw(v):return(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8')

def main():
 sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser();ap.add_argument('--check-only',action='store_true');args=ap.parse_args();git=policy.git;branch='codex/hr-source-replacement'
 assert git('remote','get-url','origin').decode().strip()=='https://github.com/421345308/beiqiang-cross-border-operations.git'
 head=git('rev-parse','HEAD').decode().strip();shared=git('write-tree').decode().strip();base=git('rev-parse','refs/heads/'+branch).decode().strip()
 def prior(p):return json.loads(git('show',base+':'+p))
 live=d.load(d.REG);merged=prior(d.rel(d.REG));baseline=set(views.validate(merged));plan=d.load(a.PLAN);ids={x['id']for x in plan['items']};assert len(ids)==7 and not(ids&d.PROTECTED);newlinks={x['id']:x for x in live['listings']};products={x['id']:x for x in live['products']};families={newlinks[i]['product_id']for i in ids};facts=set()
 for l in merged['listings']:
  if l['id']not in ids:continue
  fresh=newlinks[l['id']];assert(l['product_id'],l.get('bound_source_id'))==(fresh['product_id'],fresh.get('bound_source_id'))
  for k in ('observation','current_platform_fields','catalog_fields','formal_fields','local_sync','url'):l[k]=deepcopy(fresh[k])
  l.setdefault('optimization',{})['product_performance_review']=deepcopy(fresh['optimization']['product_performance_review'])
 for p in merged['products']:
  if p['id']not in families:continue
  fresh=products[p['id']];p.setdefault('local_assets',{})['current_performance_by_id']=deepcopy(fresh['local_assets']['current_performance_by_id'])
  if p['id']=='HR030':p['next_action']=fresh['next_action'];p['publication_disposition']=deepcopy(fresh['publication_disposition']);p['local_assets']['state']=fresh['local_assets']['state']
  f=p.get('local_assets',{}).get('current_fields_file')
  if f and f.endswith('事实与页面计划.json'):facts.add(f)
 new_sources={s['id']:s for s in live['sources']}
 for s in merged['sources']:
  for pid,v in new_sources[s['id']].get('current_listing_dispositions',{}).items():
   if pid in ids:s.setdefault('current_listing_dispositions',{})[pid]=deepcopy(v)
 for w in merged.get('workstreams',[]):
  if w['name']=='HR缺货源实款替换':w['next_action']=next(x for x in live['workstreams']if x['name']==w['name'])['next_action']
 merged['updated_on']=live['updated_on'];merged['product_performance_review']=deepcopy(live['product_performance_review']);assert set(views.validate(merged))<=baseline
 frozen={d.rel(d.REG):raw(merged)};frozen.update({p.as_posix():body for p,body in views.build(merged).items()})
 diagnostic=d.load(d.AREA/'商品诊断数据.json');public=deepcopy(diagnostic)
 # Retain the exact-ID decision inventory, never the private per-period report.
 public['products']=[{k:v for k,v in p.items()if k!='periods'}for p in public['products']];public.pop('duplicate_pairs',None);public['raw_product_periods']='LOCAL_ONLY; source references identify local evidence, not uploaded backend reports.';frozen[d.rel(d.AREA/'商品诊断数据.json')]=raw(public)
 paths=[d.AREA/'店铺经营诊断.md',d.BASE/'处置计划.json',d.BASE/'当前处置状态.json',d.BASE/'最终核验.json',d.BASE/'自定义属性页面证据.json',d.BASE/'侵权退回事实.json',ROOT/'08_工具链/06_工作区维护/checkpoint_performance_public.py',ROOT/'08_工具链/06_工作区维护/product_dossiers.py',ROOT/'08_工具链/01_业务脚本/国际站扩品/sync_models_factory_gallery.py',a.n.BASE/'平台退回诊断.json',a.n.BASE.parent/'README.md']
 paths+=list((ROOT/'08_工具链/01_业务脚本/国际站经营诊断').glob('*.py'))+list((ROOT/'08_工具链/01_业务脚本/国际站经营诊断').glob('*.md'))
 review=d.load(d.BASE/'关键词与首图复核.json');frozen[d.rel(d.BASE/'关键词与首图复核.json')]=raw({'observed_at':review['observed_at'],'id':review['id'],'scope':review['scope'],'image_review':review['image_review'],'actions':review['actions'],'keyword_observation':'首屏含多种语言的泛鞋词，少量点击；逐词后台明细只保留本地。','limits':review['scope_note']})
 for row in plan['items']:
  f=d.BASE/'商品'/row['id']/FOLDERS[row['kind']]
  paths +=[f/name for name in('prepared.json','verification.json','双改核验.json','update_once.json','receipt.json')if(f/name).exists()]
  for name in ('formal_get.json','formal_render.json'):
   p=a.n.CURRENT/row['id']/name
   if p.exists():frozen[d.rel(p)]=raw(policy.public_product_snapshot(d.load(p)))
 # Current directory is public merchandise metadata; raw page/account envelopes
 # and raw analytics files are deliberately excluded.
 catalog=d.load(d.BASE/'处置后目录/catalog.json');frozen[d.rel(d.BASE/'处置后目录/catalog.json')]=raw(policy.public_product_snapshot(catalog))
 for f in facts:
  doc=prior(f);fresh=d.load(ROOT/f)
  for pid,v in fresh.get('current_platform_dispositions_by_id',{}).items():
   if pid in ids:doc.setdefault('current_platform_dispositions_by_id',{})[pid]=deepcopy(v)
  if f.endswith('/HR030/事实与页面计划.json'):
   for k in('page_state','publish_hold','ip_review','style_review'):
    if k in fresh:doc[k]=deepcopy(fresh[k])
  frozen[f]=raw(doc)
 for path in paths:
  if not path.exists():continue
  frozen[d.rel(path)]=raw(policy.public_product_snapshot(d.load(path)))if path.suffix=='.json'else path.read_bytes()
 frozen={p:b.replace(b'\r\n',b'\n')for p,b in frozen.items()}
 for p,b in frozen.items():
  assert Path(p).suffix.lower()in('.md','.json','.py','.html','.csv');assert not policy.SECRET.search(b.decode('utf-8-sig')),p
  if p.endswith('.json'):policy.safe(json.loads(b))
 temp=ROOT/'99_临时区/商品表现处置';temp.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='public-checkpoint-',dir=temp)as tmp:
  env=dict(os.environ,GIT_INDEX_FILE=str(Path(tmp)/'index'));git('read-tree',base,env=env);items=list(frozen.items());files=[]
  for i,(p,b)in enumerate(items):f=Path(tmp)/str(i);f.write_bytes(b);files.append(f.as_posix())
  blobs=git('hash-object','-w','--no-filters','--stdin-paths',input=('\n'.join(files)+'\n').encode('utf8')).decode().splitlines();assert len(blobs)==len(items)
  lines=[]
  for(p,b),blob in zip(items,blobs):
   assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==blob;assert not any(x in p for x in'\r\n\t');lines.append('100644 '+blob+'\t'+p+'\n')
  git('update-index','--index-info',input=''.join(lines).encode('utf8'),env=env);tree=git('write-tree',env=env).decode().strip();assert not git('diff','--check',base,tree);changed=[p for p in git('diff','--name-only','-z',base,tree).decode().split('\0')if p];assert set(changed)<=set(frozen);assert git('rev-parse','HEAD').decode().strip()==head and git('write-tree').decode().strip()==shared
  if args.check_only:print('PUBLIC_SCOPE_PASS',len(changed),'EXACT_ACTION_IDS',len(ids));return
  if not changed:print('NO_NEW_TASK_CHANGES');return
  commit=git('commit-tree',tree,'-p',base,input=b'feat: diagnose exact-product performance and retire duplicate weak entries\n').decode().strip();git('update-ref','refs/heads/'+branch,commit,base);d.save(d.BASE/'Git阶段提交.json',{'base':base,'branch':branch,'commit':commit,'files':changed,'shared_HEAD_and_index_unchanged':True,'raw_backend_metrics_accounts_and_media_excluded':True});print(json.dumps({'commit':commit,'branch':branch,'files':len(changed)}))

if __name__=='__main__':main()
