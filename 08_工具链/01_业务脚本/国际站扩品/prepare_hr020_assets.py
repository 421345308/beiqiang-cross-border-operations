"""Build HR020's current images from the exact supplier photographs.

No shoe generation is needed for the clean existing side/top/outsole photos.
"""
from pathlib import Path
from PIL import Image
import hashlib,json
from prepare_hr054_assets import ROOT,photo,card,text

BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换/HR020'

def main():
    plan=json.loads((BASE/'事实与页面计划.json').read_text(encoding='utf8'))
    assert plan['source_artno']=='9917'
    raw=ROOT/plan['source_assets_root'];out=ROOT/'01_产品资产/02_可发布素材/HR020';out.mkdir(parents=True,exist_ok=True)
    def src(n):return raw/f'{n:02}.jpg'
    def save(im,key):im.save(out/(key+'.jpg'),quality=94,subsampling=0)
    cuts={'Black':(22,(0,0,790,480)),'Brown':(21,(0,180,790,600))}
    im=Image.new('RGB',(1000,1000),'white');photo(im,src(22),(30,130,970,850),cuts['Black'][1]);save(im,'M1')
    im=card('Slip-on summer styling','A closed-toe profile with open side panels');photo(im,src(16),(35,205,965,940));save(im,'M2')
    im=card('Perforated leather upper','See the hole pattern and stitched panel edges');photo(im,src(10),(30,235,970,830),(0,640,790,1470));text(im,'Side cutouts  |  Slip-on opening  |  Heel loop',(45,925),27);save(im,'M3')
    im=card('Two color options','Black / Brown')
    for i,(color,(n,crop))in enumerate(cuts.items()):
        y=205+i*345;photo(im,src(n),(35,y,965,y+295),crop);text(im,color,(45,y+305),32,True)
    save(im,'M4')
    im=card('EU 38-44 size range','Plan your assortment by color and EU size');photo(im,src(21),(35,210,965,760),(0,610,790,1010));text(im,'EU 38  39  40  41  42  43  44',(60,850),38,True);save(im,'M5')
    im=card('Closed-toe leather sandals','Perforated vamp with open side panels',True);photo(im,src(22),(30,215,970,965),(0,0,790,480));text(im,'Slip-on profile  /  Black & Brown  /  EU 38-44',(45,1060),31,True);text(im,'An option for summer casual footwear ranges',(45,1150),29);save(im,'D1')
    im=card('Construction from every angle','Actual photographed details of this style',True);photo(im,src(10),(35,205,965,675),(0,640,790,1470));photo(im,src(22),(35,735,965,1090),(0,540,790,940));text(im,'Panel stitching, cutouts and grooved tread',(45,1150),31,True);save(im,'D2')
    im=card('Choose your color direction','Two colorways of the same real shoe',True)
    for i,(color,(n,crop))in enumerate(cuts.items()):
        y=210+i*430;photo(im,src(n),(35,y,965,y+360),crop);text(im,color,(45,y+375),33,True)
    text(im,'Share your target color ratio for a wholesale quote',(45,1160),28);save(im,'D3')
    im=card('Plan sizes, quantities and packing','EU sizes for your intended footwear assortment',True);photo(im,src(21),(35,210,965,785),(0,610,790,1010));text(im,'EU 38  39  40  41  42  43  44',(50,865),39,True);text(im,'Send quantities by color and EU size',(45,990),32);text(im,'Add packing preference and destination',(45,1060),29);text(im,'Request a sample to review fit and finishing',(45,1140),29);save(im,'D4')
    for color,(n,crop)in cuts.items():
        im=Image.new('RGB',(1000,1000),'white');photo(im,src(n),(30,140,970,825),crop);text(im,color,(45,900),36,True);save(im,'SKU_'+color.upper())
    shared=ROOT/'01_产品资产/02_可发布素材/共享素材/贝强公司简介图库.jpg'
    manifest={p.stem:{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'dimensions':list(Image.open(p).size)}for p in out.glob('*.jpg')if p.stem!='审核总览'}
    manifest['M6']={'path':shared.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(shared.read_bytes()).hexdigest(),'dimensions':list(Image.open(shared).size)}
    sheet=Image.new('RGB',(1600,1380),'white')
    for i,p in enumerate(sorted(out.glob('M*.jpg'))+sorted(out.glob('D*.jpg'))+[shared]):
        x=(i%4)*400;y=(i//4)*460;photo(sheet,p,(x,y+30,x+390,y+445));text(sheet,p.stem if p!=shared else 'M6',(x+10,y+5),22)
    save(sheet,'审核总览')
    (BASE/'素材清单.json').write_text(json.dumps({'family':'HR020','state':'PENDING_VISUAL_REVIEW','items':manifest},ensure_ascii=False,indent=2),encoding='utf8')
    print('HR020_ASSETS_FOR_REVIEW',len(manifest))

if __name__=='__main__':main()
