"""Canonical raw/finished asset store; explicit plan, guarded migration and hash audit.

Original package bytes and formal platform receipts are immutable. Historical
paths can be resolved through the local migration index without rewriting receipts.
"""
from pathlib import Path
import argparse, hashlib, json, os, re, shutil
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[2]
ASSET=ROOT/'01_产品资产'
EXPECTED=Path('E:/贝强大文件/01_产品资产').resolve()
RAW=ASSET/'01_原始素材'; FINISHED=ASSET/'02_成品素材'
INDEX=ROOT/'00_总控台/产品中心/数据/素材索引.json'
ALIASES=Path('E:/贝强离线归档/产品旧档/路径迁移索引.json')
MEDIA={'.png','.jpg','.jpeg','.webp','.gif','.mp4','.svg'}
def read(p):return json.loads(p.read_text('utf-8-sig'))
def write(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n','utf-8')
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def guard(p):
 resolved=p.resolve()
 if not resolved.is_relative_to(EXPECTED):raise RuntimeError(f'Outside verified asset root: {p}')
 return resolved
def resolve_legacy_asset(path):
 path=str(path).replace('\\','/');p=ROOT/path
 if p.exists():return p
 if ALIASES.exists():
  mapping=read(ALIASES)['paths'];return ROOT/mapping.get(path,path)
 return p
def strings(value):
 if isinstance(value,str):yield value
 elif isinstance(value,list):
  for v in value:yield from strings(v)
 elif isinstance(value,dict):
  for v in value.values():yield from strings(v)
def plan():
 assert ASSET.resolve()==EXPECTED,(ASSET.resolve(),EXPECTED)
 if RAW.exists() or FINISHED.exists():raise RuntimeError('Canonical store already exists; use --check.')
 products=read(ROOT/'00_总控台/产品中心/数据/产品.json')['products']
 codes={p['id']:p.get('current_model') or next((a for a in p['aliases'] if a.startswith('BQ')),p['id']) for p in products}
 owners=defaultdict(set);roles=defaultdict(set);record_paths=set(); rawowners={}
 def select(path,code,role):
  p=ROOT/str(path).replace('\\','/')
  if p.is_file() and p.suffix.lower() in MEDIA:
   owners[rel(p)].add(code);roles[rel(p)].add(role)
 for p in products:
  code=codes[p['id']]
  for raw in p['raw_packages']:rawowners[raw.replace('\\','/')]=code
  for gallery in p.get('local_assets',{}).get('current_gallery_by_id',{}).values():
   file=ROOT/gallery
   if not file.exists():continue
   record_paths.add(gallery); data=read(file)
   for item in data.get('main',[]):select(item.get('file',''),code,'Alibaba main '+str(item.get('slot','')))
  # Current source-reviewed images, not generic historical HR render folders.
  f=ROOT/(p.get('local_assets',{}).get('current_fields_file') or '_missing')
  if f.is_file() and f.suffix=='.json':
   facts=read(f)
   if facts.get('assets_layout'):
    for folder in p.get('local_assets',{}).get('asset_roots',[]):
     for key in facts['assets_layout']:
      select(str(Path(folder)/(key+'.jpg')),code,'Reviewed '+key)
 # Current Douyin data selects main, SKU and detail images; SVG source projects
 # stay in raw history and never inflate the finished raster catalogue.
 for file in (ROOT/'09_国内电商/抖店/数据').glob('*.json'):
  data=read(file)
  if file.name!='品牌首发商品.json':continue
  bindings=defaultdict(set)
  for listing in read(ROOT/'09_国内电商/抖店/数据/渠道产品对应.json')['listings']:
   if listing.get('product_id'):bindings[listing['source_model']].add(codes.get(listing['product_id'],listing['product_id']))
  for model,obj in data.get('models',{}).items():
   bound=obj.get('canonical_product_id')
   code=codes.get(bound,bound) if bound else next(iter(bindings[model])) if len(bindings[model])==1 else '抖店独立款_'+model
   for key in ['main_files','color_files','detail_files']:
    for path in strings(obj.get(key,[])):
     if Path(path).suffix.lower()!='.svg':select(path,code,'Douyin '+key)
 # The website directory is a deployment copy; master finished photographs live
 # once in the product store. Build derivatives remain reproducible site output.
 website=ROOT/'03_独立站/03_网站源码'
 provenance=read(website/'data/product-photo-provenance.json')
 for code,pics in provenance['products'].items():
  for pic in pics:select(rel(website/'public'/pic['image'].lstrip('/')),code,'Website '+pic.get('role','photo'))
 files=[]
 for base,dirs,names in os.walk(ASSET,followlinks=False):
  for name in names:
   p=Path(base)/name;guard(p);files.append(p)
 hashes={rel(p):digest(p) for p in files}
 for path in owners:
  if path not in hashes:hashes[path]=digest(ROOT/path)
 groups=defaultdict(list)
 for path in owners:groups[hashes[path]].append(path)
 finished=[];selected_dest={}
 for sha,paths in sorted(groups.items()):
  modelset=sorted(set().union(*(owners[p] for p in paths)));code=modelset[0] if len(modelset)==1 else '共享素材'
  ext=Path(paths[0]).suffix.lower();dest=FINISHED/code/f'{code}_{sha[:16]}{ext}'
  for path in paths:selected_dest[path]=rel(dest)
  finished.append({'file':rel(dest),'sha256':sha,'products':modelset,'roles':sorted(set().union(*(roles[p] for p in paths))),'origins':paths})
 # Exact prefix routing gives every original file a deterministic destination.
 directory_map={}
 oldraw=ASSET/'01_原始数据包'
 for child in oldraw.iterdir():
  if not child.is_dir():continue
  relative=rel(child);code=rawowners.get(relative)
  if not code:
   match=re.search(r'(BQ\d{3}|HR\d{3})(?:_|$)',child.name)
   if match:code=codes.get(match[1],match[1])
  if code:
   name=re.sub(r'HR\d{3}',lambda m:codes.get(m[0],m[0]),child.name)
   directory_map[relative]=rel(RAW/code/name)
  else:directory_map[relative]=rel(RAW/'历史输入'/child.name)
 for old,new in [('02_可发布素材','历史制作资料'),('04_去标与处理后素材','历史制作资料/去标处理'),('05_平台当前素材','平台回读'),('03_技术资料卡','技术资料')]:
  directory_map[rel(ASSET/old)]=rel(RAW/new)
 moves=[];pathmap={}
 for p in files:
  src=rel(p);dst=selected_dest.get(src)
  if not dst:
   prefix=next((k for k in sorted(directory_map,key=len,reverse=True) if src.startswith(k+'/')),None)
   if not prefix:raise RuntimeError('Unclassified '+src)
   dst=directory_map[prefix]+src[len(prefix):]
  guard(ROOT/dst);pathmap[src]=dst;moves.append({'from':src,'to':dst,'sha256':hashes[src],'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns})
 # Supplier originals collected for the website belong in the same raw store.
 for directory in (ROOT/'00_总控台/产品中心/证据').glob('*/官网图片来源'):
  for p in directory.rglob('*'):
   if not p.is_file():continue
   src=rel(p);dst=rel(RAW/directory.parent.name/'搜鞋网原图'/p.relative_to(directory));pathmap[src]=dst
   moves.append({'from':src,'to':dst,'sha256':digest(p),'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns})
 return {'schema_version':1,'products':codes,'finished':finished,'moves':moves,'paths':pathmap,'directories':directory_map,'current_gallery_records':sorted(record_paths)}
def apply(data):
 assert ASSET.resolve()==EXPECTED
 # Validate the complete input before any mutation, including concurrent edits.
 for item in data['moves']:
  p=ROOT/item['from'];st=p.stat()
  if st.st_size!=item['size'] or st.st_mtime_ns!=item['mtime_ns']:raise RuntimeError('Changed since plan: '+str(p))
  guard(ROOT/item['to'])
 RAW.mkdir(exist_ok=True);FINISHED.mkdir(exist_ok=True)
 write(ALIASES,{'schema_version':1,'paths':data['paths'],'directories':data['directories'],'policy':'Historical receipts remain byte-identical; resolve historical local paths with this index.'})
 for item in data['moves']:
  src=ROOT/item['from'];dst=ROOT/item['to'];dst.parent.mkdir(parents=True,exist_ok=True)
  if dst.exists():
   if digest(dst)!=item['sha256']:raise RuntimeError('Destination collision: '+str(dst))
   # Only an exact duplicate of a verified, already-retained file is removed.
   src.unlink()
  else:shutil.move(str(src),str(dst))
 for item in data['finished']:
  dest=ROOT/item['file'];guard(dest)
  if not dest.exists():
   source=next(ROOT/p for p in item['origins'] if (ROOT/p).is_file());dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
  if digest(dest)!=item['sha256']:raise RuntimeError('Finished hash mismatch '+str(dest))
 # Only remove empty old directories, bottom-up, after resolved containment checks.
 for old in ['01_原始数据包','02_可发布素材','03_技术资料卡','04_去标与处理后素材','05_平台当前素材']:
  root=ASSET/old
  if not root.exists():continue
  guard(root)
  for base,dirs,files in os.walk(root,topdown=False):
   p=Path(base);guard(p)
   if not list(p.iterdir()):p.rmdir()
 for directory in (ROOT/'00_总控台/产品中心/证据').glob('*/官网图片来源'):
  for base,dirs,files in os.walk(directory,topdown=False):
   p=Path(base)
   if not list(p.iterdir()):p.rmdir()
 write(INDEX,{'schema_version':1,'updated_on':'2026-10-25','raw_root':rel(RAW),'finished_root':rel(FINISHED),'legacy_path_index':rel(ALIASES),'files':data['finished']})
 check()
def check():
 data=read(INDEX);paths=read(ALIASES)['paths'];seen=set()
 for item in data['files']:
  p=ROOT/item['file'];guard(p);sha=digest(p)
  assert sha==item['sha256'],item['file'];assert sha not in seen,'Duplicate finished bytes';seen.add(sha)
 for old,new in paths.items():assert (ROOT/new).is_file(),new
 print(json.dumps({'finished_unique':len(seen),'legacy_paths_resolved':len(paths),'top_level_directories':[p.name for p in ASSET.iterdir() if p.is_dir()]},ensure_ascii=False))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--plan');parser.add_argument('--apply');parser.add_argument('--check',action='store_true');args=parser.parse_args()
 if args.plan:
  data=plan();write(Path(args.plan),data);print(json.dumps({'move_files':len(data['moves']),'finished_unique':len(data['finished']),'finished_references':sum(len(x['origins']) for x in data['finished'])}))
 elif args.apply:apply(read(Path(args.apply)))
 else:check()
