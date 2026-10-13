"""Restore only originally-offline IDs republished by the gallery update.

Official current batch display API; numeric IDs bind fresh exact-ID get.
No deleting, no new offline disposition, no replay of an existing ledger.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import replace_company_gallery as op

IDS=['1601943621884','1601943670678','1601943742273','1601943768215','1601943774082']
def main():
 api,cfg=op.b.api_client();parent=op.BASE/'原下架状态恢复';parent.mkdir(exist_ok=True)
 if(parent/'update_once.json').exists():
  error=op.load(parent/'receipt.json')['response'].get('error_response',{});assert error.get('code')=='MissingParameter','Unknown or successful old outcome must not be replayed'
 f=parent/'当前接口修正';f.mkdir(exist_ok=True);assert not(f/'update_once.json').exists()
 encrypted=[];before={}
 for pid in IDS:
  original=op.load(op.BASE/'商品'/pid/'before_get.json')['product'];assert original['display']=='N'
  got=op.read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});p=got['product'];assert p['status']=='approved'and p['display']=='Y'and op.gallery_identity_match(p,op.load(op.BASE/'当前上传回执.json'))
  assert '_'+pid+'.html'in p['pc_detail_url'];before[pid]=got;encrypted.append(p['product_id'])
 assert len(set(encrypted))==len(IDS)
 op.save(f/'before_get.json',before);params={'new_display':'off','product_id_list':[int(i)for i in IDS]};op.save(f/'request.json',{'method':'alibaba.icbu.product.batch.update.display','ids':IDS,'params':params,'intent':'Restore exact original display=N, not a new disposition','official_reference':'https://open.alibaba.com/doc/api.htm#/api?cid=20966&path=alibaba.icbu.product.batch.update.display&methodType=GET/POST','current_specification_observed':'product_id_list Number[] 商品明文id列表; current IOP sample [123,345]','previous_attempt':'Known MissingParameter business rejection; retained, not replayed unchanged'})
 with(f/'update_once.json').open('x',encoding='utf8')as h:h.write('{"status":"STARTED_OUTCOME_UNKNOWN"}')
 result=api.top_call(cfg,'alibaba.icbu.product.batch.update.display',params);op.save(f/'receipt.json',{'at':op.now(),'response':result});print('ORIGINAL_OFFLINE_RESTORE_RESPONSE',result)
 passed=[]
 for pid in IDS:
  got=op.read_only_call(api,cfg,'alibaba.icbu.product.get',{'product_id':pid,'language':'ENGLISH'});op.save(f/(pid+'_after_get.json'),got);p=got['product'];same=op.preserve(p)==op.preserve(before[pid]['product']);passed.append({'id':pid,'display':p['display'],'status':p['status'],'other_fields_preserved':same,'restored':p['display']=='N'and same})
 op.save(f/'verification.json',{'at':op.now(),'ids':IDS,'items':passed,'passed':all(x['restored']for x in passed),'scope':'Restore previously-offline five IDs only; company gallery/source separately assessed'});print(passed)
if __name__=='__main__':main()
