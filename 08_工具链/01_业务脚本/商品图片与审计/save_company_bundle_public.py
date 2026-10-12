"""Persist actual cua_repl DOM observations; never infer public QA from API.

Input is the observation returned by the browser tool, with exact product ID,
URL, time, introduction comparison, eight paired FAQ checks and six images.
"""
from pathlib import Path
import argparse,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import replace_company_bundle as op

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--observations',required=True);a=ap.parse_args()
    source=op.load(Path(a.observations));scope=op.load(op.PHASE/'scope.json')
    assert source['method']=='cua_repl normal page DOM'and source['asset_version']==8
    seen=set()
    for row in source['items']:
        pid=row['id'];assert pid not in seen and pid in scope['eligible_ids'];seen.add(pid)
        f=op.folder(pid);v=op.load(f/'verification.json');assert v['status']=='FORMAL_PASS'and v['display']=='Y'
        assert '_'+pid+'.html'in row['url']and row['observedAt']>=v['at'].replace('+00:00','Z')[:19]
        assert len(row['faqPairMatches'])==8 and len(row['images'])==6
        assert {x['asset']for x in row['images']}=={'C1','C2','C3','C4','C5','C6'}
        passed=row['introMatch']and all(row['faqPairMatches'])and all(x['count']==1 and x['loaded']for x in row['images'])
        status='PUBLIC_SIX_IMAGES_INTRO_FAQ_PASS'if passed else'PUBLIC_TARGET_PENDING_DIAGNOSE'
        evidence={**row,'product_id':pid,'asset_version':8,'status':status,'method':source['method'],'copy_sha256':op.sha(op.COPY/'通用FAQ与公司简介.json'),'image_identity_evidence':'V8/url_identity.json','comparison':'Complete question/answer pairs, company introduction and six exact official image identities/native dimensions; whitespace normalized for rendered text only'}
        op.save(f/'public_verification.json',evidence);v['public_status']=status;op.save(f/'verification.json',v)
    print('PUBLIC_OBSERVATIONS_SAVED',len(seen));print(op.aggregate())
if __name__=='__main__':main()
