"""Sync exact-ID company-gallery receipts and reads into existing product records.

No platform writes, no source-state changes. Submission, formal binding and
public presentation retain separate states, including originally offline IDs.
"""
from pathlib import Path
import argparse,json,sys,hashlib,importlib.util,copy
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'08_工具链/01_业务脚本/商品图片与审计'))
import replace_company_gallery as op
from field_stage_navigation import annotate
REGISTRY=ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json'
DETAILS=ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--ids');a=ap.parse_args()
 prep=op.load(op.BASE/'替换准备.json');ids=a.ids.split(',')if a.ids else prep['eligible_ids']
 raw=REGISTRY.read_bytes();data=json.loads(raw);listings={x['id']:x for x in data['listings']};products={x['id']:x for x in data['products']}
 source_before=copy.deepcopy(data['sources']);product_states={x['id']:x['source_state']for x in data['products']};touched=set();states={}
 rel=lambda p:p.relative_to(ROOT).as_posix()
 for pid in ids:
  f=op.BASE/'商品'/pid
  if not(f/'update_once.json').exists():continue
  assert pid in prep['eligible_ids'] and pid in listings
  listing=listings[pid];product=products[listing['product_id']];touched.add(product['id'])
  v=op.load(f/'verification.json')if(f/'verification.json').exists()else{}
  receipt=op.load(f/'update_receipt.json')if(f/'update_receipt.json').exists()else{}
  public=op.load(f/'public_verification.json')if(f/'public_verification.json').exists()else{}
  state=v.get('status')or receipt.get('status')or'STARTED_OUTCOME_UNKNOWN'
  evidence=[rel(f/x)for x in ['manifest.json','prepared.json','update_once.json','update_receipt.json','after_get.json','after_render.json','verification.json','public_verification.json']if(f/x).exists()]
  factory={'asset_version':6,'at':v.get('at')or receipt.get('attempted_at')or op.now(),'state':state,'scope':['companyImage'],'historical_company_only':pid in prep['historical_company_only_ids'],'source_state_unchanged':True,'formal_binding_verified':state=='FORMAL_PASS','public_status':public.get('status')or v.get('public_status')or'NOT_CHECKED','evidence':evidence,'next_action':'核精确商品公开工厂图；不重放已有提交'if state=='FORMAL_PASS'else'等待审核并独立回读；不重放已有提交'}
  if factory['public_status']=='PUBLIC_FIVE_FACTORY_IMAGES_LOADED':factory['next_action']='本轮五张工厂图正式与公开呈现已核；鞋款来源及其他商品问题按各自状态继续'
  elif factory['public_status']=='NOT_APPLICABLE_OFFLINE_DISPLAY_PRESERVED':factory['next_action']='保留原下架状态；本轮只核工厂图正式绑定，不计买家公开页通过'
  listing.setdefault('optimization',{})['factory_gallery']=factory;states[pid]=state
  if v and(f/'after_get.json').exists():
   got=op.load(f/'after_get.json');actual=got['product'];formal=DETAILS/pid/'formal_get.json'
   previous=op.load(formal)if formal.exists()else{}
   if v['at']>=previous.get('observed_at_utc',''):
    formal.parent.mkdir(parents=True,exist_ok=True);op.save(formal,{'requested_product_id':pid,'observed_at_utc':v['at'],'method':'alibaba.icbu.product.get','response':got})
    listing['formal_fields']={'file':rel(formal),'at':v['at'],'scope':'完整product.get；工厂图/审核和公开验收分别记录，不解除货源待核'}
    listing['current_platform_fields']={**listing.get('current_platform_fields',{}),'at':v['at'],'title':actual.get('subject',''),'keywords':actual.get('keywords',[]),'main_images':actual.get('main_image',{}).get('images',[]),'category_id':actual.get('category_id'),'display':actual.get('display'),'status':actual.get('status'),'url':actual.get('pc_detail_url',''),'scope':'按ID完整product.get正式字段；审核与公开验收分开'}
    listing['local_sync']={**listing.get('local_sync',{}),'state':'FORMAL_SNAPSHOT_SAVED_FACTORY_'+state,'current_fields_file':rel(formal),'next_action':factory['next_action']}
  for ref in evidence:
   if ref not in product['evidence']:product['evidence'].append(ref)
 assert data['sources']==source_before and all(x['source_state']==product_states[x['id']]for x in data['products'])
 assert REGISTRY.read_bytes()==raw,'Registry changed; rerun from fresh input'
 data['updated_on']=op.now()[:10];op.save(REGISTRY,data)
 spec=importlib.util.spec_from_file_location('dossiers',ROOT/'08_工具链/06_工作区维护/product_dossiers.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 selected={**data,'products':[x for x in data['products']if x['id']in touched],'listings':[x for x in data['listings']if x['product_id']in touched]}
 for path,content in m.builds(selected).items():(ROOT/path).write_bytes(annotate(content,selected,path,ROOT))
 old=op.load(op.BASE/'双改同步.json')if(op.BASE/'双改同步.json').exists()else{}
 op.save(op.BASE/'双改同步.json',{'at':op.now(),'synced_ids':sorted(set(old.get('synced_ids',[]))|set(states)),'states':{**old.get('states',{}),**states},'touched_dossiers':sorted(set(old.get('touched_dossiers',[]))|touched),'scope':['companyImage'],'registry_input_sha256':hashlib.sha256(raw).hexdigest(),'source_states_unchanged':True,'no_platform_writes':True})
 print('FACTORY_LOCAL_SYNC',len(states),len(touched))
if __name__=='__main__':main()
