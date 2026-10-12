"""Save normal-browser exact-ID observations; never fetch or mutate the platform."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import replace_company_gallery as op

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--observations',required=True);a=ap.parse_args();rows=op.load(Path(a.observations));prep=op.load(op.BASE/'替换准备.json');proof=op.load(op.BASE/'正式图链像素核对.json')
 assert len({x['id']for x in rows})==len(rows)
 for row in rows:
  pid=row['id'];assert pid in prep['eligible_ids'] and row['matchedFive']is True and row['labelsMatched']is True
  f=op.BASE/'商品'/pid;v=op.load(f/'verification.json');got=op.load(f/'after_get.json')
  assert op.target_binding_verified(v) and got['product']['display']=='Y' and row['url']==got['product']['pc_detail_url']
  images=[{'asset':x['asset'],'gallery_id':x['gallery_id'],'url':x['accepted_urls'][1],'dimensions':x['dimensions'],'complete':True}for x in proof['items']]
  result={'product_id':pid,'asset_version':6,'observed_at':row['at'],'url':row['url'],'status':'PUBLIC_FIVE_FACTORY_IMAGES_LOADED','matched_image_identities':images,'company_labels_present':['Company overview','Competitive advantages','Customization capabilities','Production workflow','Packaging & shipping specifications'],'method':'Normal exact buyer-page browser DOM/accessibility plus rendered img src, complete and original natural dimensions; all five exact URLs matched. No hidden application state, iframe query tokens, form or platform write','formal_evidence':'verification.json','scope':'Exact product/time and V6 factory module only; source and other product fields separately assessed'}
  op.save(f/'public_verification.json',result);v['public_status']=result['status'];op.save(f/'verification.json',v)
 print('FACTORY_PUBLIC_OBSERVATIONS_SAVED',len(rows));op.aggregate()
if __name__=='__main__':main()
