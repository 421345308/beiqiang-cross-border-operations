"""Assemble approved HR054 source photographs; no generated SKU geometry.

The accepted AI hero is supplied explicitly. Source identity and facts remain in
the current business plan and read-only raw package, not script constants.
"""
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
import argparse, hashlib, json

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换/HR054'
NAVY='#162b46'; GREY='#607083'; ORANGE='#de6c35'

def text(im, value, xy, size=28, bold=False):
    font=ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if bold else 'arial.ttf'),size)
    ImageDraw.Draw(im).text(xy,value,font=font,fill=NAVY)

def photo(dst,path,box,crop=None):
    im=Image.open(path).convert('RGB')
    if crop:im=im.crop(crop)
    im=ImageOps.contain(im,(box[2]-box[0],box[3]-box[1]))
    dst.paste(im,(box[0]+(box[2]-box[0]-im.width)//2,box[1]+(box[3]-box[1]-im.height)//2))

def card(title,sub,detail=False):
    im=Image.new('RGB',(1000,1250 if detail else 1000),'#fbfaf7')
    ImageDraw.Draw(im).rectangle((45,45,100,52),fill=ORANGE)
    text(im,title,(45,75),40,True);text(im,sub,(45,140),24)
    return im

def main():
    p=argparse.ArgumentParser();p.add_argument('--hero',required=True);args=p.parse_args()
    plan=json.loads((BASE/'事实与页面计划.json').read_text(encoding='utf8'))
    assert plan['source_artno']=='27975' and plan['colors']==['Beige','Blue','Yellow']
    raw=ROOT/plan['source_assets_root'];out=ROOT/'01_产品资产/02_可发布素材/HR054'
    out.mkdir(parents=True,exist_ok=True)
    def src(n):return raw/f'{n:02}.jpg'
    def save(im,name):im.save(out/(name+'.jpg'),quality=94,subsampling=0)
    save(Image.open(args.hero).convert('RGB'),'M1')
    im=card('A bold casual silhouette','See the platform profile in everyday styling')
    photo(im,src(9),(40,200,960,940),(255,280,790,850));save(im,'M2')
    im=card('Construction up close','Round toe, stitched panels and grooved outsole')
    for box,crop in [((40,215,480,730),(10,320,250,555)),((520,215,960,730),(542,320,778,555))]:photo(im,src(7),box,crop)
    text(im,'Toe panel stitching',(45,790),30,True);text(im,'Rubber tread detail',(520,790),30,True);save(im,'M3')
    cuts={'Beige':(21,(145,350,660,690)),'Blue':(16,(140,410,675,800)),'Yellow':(12,(145,360,690,770))}
    im=card('Three color directions','Beige / Blue / Yellow')
    for i,(c,(n,crop))in enumerate(cuts.items()):
        y=200+i*240;photo(im,src(n),(40,y,780,y+220),crop);text(im,c,(795,y+95),29,True)
    save(im,'M4')
    im=card('EU 35-40 size options','Choose your assortment by EU size and color')
    photo(im,src(14),(40,210,960,750),(150,90,745,610));text(im,'EU 35   36   37   38   39   40',(80,820),40,True)
    text(im,'Plan your quantities for each color-size combination',(45,920),27);save(im,'M5')
    im=card('Lace-up platform sneakers','Paneled low-top profile with a tan rubber outsole',True)
    photo(im,Path(args.hero),(25,205,975,1000));text(im,'Three colors  /  EU 35-40',(45,1070),34,True)
    text(im,'For fashion-led casual footwear assortments',(45,1160),27);save(im,'D1')
    im=card('Details that define this style','Examine the actual photographed construction',True)
    photo(im,src(7),(40,210,490,740),(10,320,250,555));photo(im,src(7),(520,210,960,740),(542,320,778,555))
    text(im,'Layered round toe',(45,810),33,True);text(im,'Grooved rubber outsole',(520,810),30,True)
    text(im,'Two stitched side strips and contrasting toe panels',(45,920),29)
    text(im,'Flat laces with a second patterned lace detail',(45,1000),29)
    text(im,'Low-cut padded opening',(45,1090),29);save(im,'D2')
    im=card('Build a coordinated color range','Three colorways of the same real shoe',True)
    for i,(c,(n,crop))in enumerate(cuts.items()):
        y=215+i*295;photo(im,src(n),(40,y,960,y+240),crop);text(im,c,(45,y+245),28,True)
    text(im,'Select your preferred color ratio for a wholesale quote',(45,1170),26);save(im,'D3')
    im=card('Plan sizes, quantities and packing','EU size options for your intended assortment',True)
    photo(im,src(14),(40,210,960,795),(150,90,745,610));text(im,'EU 35   36   37   38   39   40',(65,865),40,True)
    text(im,'Send quantities by color and EU size',(45,990),32)
    text(im,'Add packaging preferences and destination',(45,1060),29)
    text(im,'Request a sample to review fit and finishing',(45,1140),29);save(im,'D4')
    for c,(n,crop)in cuts.items():
        im=Image.new('RGB',(1000,1000),'#fbfaf7');photo(im,src(n),(35,120,965,850),crop)
        text(im,c,(45,900),36,True);save(im,'SKU_'+c.upper())
    files=sorted(out.glob('M*.jpg'))+sorted(out.glob('D*.jpg'))
    shared=ROOT/'01_产品资产/02_可发布素材/共享素材/贝强公司简介图库.jpg'
    manifest={f.stem:{'path':f.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'dimensions':list(Image.open(f).size)}for f in out.glob('*.jpg')if f.stem!='审核总览'}
    manifest['M6']={'path':shared.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(shared.read_bytes()).hexdigest(),'dimensions':list(Image.open(shared).size)}
    sheet=Image.new('RGB',(1600,1380),'white')
    for i,f in enumerate(files+[shared]):
        x=(i%4)*400;y=(i//4)*460;photo(sheet,f,(x,y+30,x+390,y+445));text(sheet,f.stem,(x+10,y+5),22)
    save(sheet,'审核总览')
    (BASE/'素材清单.json').write_text(json.dumps({'family':'HR054','state':'PENDING_FULL_VISUAL_REVIEW','items':manifest},ensure_ascii=False,indent=2),encoding='utf8')
    print('HR054_ASSETS_FOR_REVIEW',len(manifest))

if __name__=='__main__':main()
