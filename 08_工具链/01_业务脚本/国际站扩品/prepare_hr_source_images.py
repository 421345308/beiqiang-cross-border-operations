"""Render per-shoe approved photographic layouts; shoe facts live in the business plan."""
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
import argparse, hashlib, json

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
NAVY='#162b46';ORANGE='#de6c35'


def text(image,value,xy,size=28,bold=False):
    font=ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf'if bold else'arial.ttf'),size)
    draw=ImageDraw.Draw(image)
    box=draw.textbbox(xy,value,font=font)
    assert box[0]>=0 and box[1]>=0 and box[2]<=image.width-25 and box[3]<=image.height-20,(value,box)
    draw.text(xy,value,font=font,fill=NAVY)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('family');parser.add_argument('--hero');args=parser.parse_args()
    folder=BASE/args.family;plan=json.loads((folder/'事实与页面计划.json').read_text(encoding='utf8'))
    raw=ROOT/plan['source_assets_root'];out=ROOT/'01_产品资产/02_可发布素材'/args.family
    assert out.resolve().is_relative_to((ROOT/'01_产品资产/02_可发布素材').resolve())
    out.mkdir(parents=True,exist_ok=True);manifest={};recipes={}
    for key,layout in plan['assets_layout'].items():
        detail=key.startswith('D');size=(1000,1250 if detail else 1000)
        image=Image.new('RGB',size,'white'if key.startswith(('M1','SKU_'))else'#fbfaf7')
        if layout.get('title'):
            ImageDraw.Draw(image).rectangle((45,45,100,52),fill=ORANGE)
            text(image,layout['title'],(45,75),40,True)
            text(image,layout.get('subtitle',''),(45,140),24)
        actual=[]
        for item in layout['photos']:
            path=Path(args.hero)if item.get('hero')and args.hero else raw/f"{item['index']:02}.jpg"
            source=Image.open(path)
            if source.mode=='RGBA':
                background=Image.new('RGBA',source.size,'white');source=Image.alpha_composite(background,source).convert('RGB')
            else:source=source.convert('RGB')
            crop=None if item.get('hero')and args.hero else item.get('crop')
            if crop:
                assert 0<=crop[0]<crop[2]<=source.width and 0<=crop[1]<crop[3]<=source.height,(key,crop,source.size)
                source=source.crop(crop)
            box=item['box'];resized=ImageOps.contain(source,(box[2]-box[0],box[3]-box[1]))
            image.paste(resized,(box[0]+(box[2]-box[0]-resized.width)//2,box[1]+(box[3]-box[1]-resized.height)//2))
            actual.append({'file':str(path),'crop':crop,'native_effective_pixels':list(source.size),'uniform_resize':True})
        for item in layout.get('text',[]):text(image,item['value'],item['xy'],item.get('size',28),item.get('bold',False))
        path=out/(key+'.jpg');image.save(path,quality=94,subsampling=0)
        manifest[key]={'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'dimensions':list(image.size)}
        recipes[key]={'buyer_question':layout['buyer_question'],'source_pixels':actual,'text':layout.get('text',[]),'title':layout.get('title')}
    shared=ROOT/'01_产品资产/02_可发布素材/共享素材/贝强公司简介图库.jpg'
    manifest['M6']={'path':shared.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(shared.read_bytes()).hexdigest(),'dimensions':list(Image.open(shared).size)}
    recipes['M6']={'buyer_question':'Who will coordinate the footwear order?','shared_approved_company_image':manifest['M6']['path']}
    keys=['M1','M2','M3','M4','M5','M6','D1','D2','D3','D4']+[k for k in manifest if k.startswith('SKU_')]
    sheet=Image.new('RGB',(1600,460*((len(keys)+3)//4)),'white')
    for i,key in enumerate(keys):
        path=ROOT/manifest[key]['path'];preview=ImageOps.contain(Image.open(path).convert('RGB'),(390,420));x=i%4*400;y=i//4*460
        sheet.paste(preview,(x+(390-preview.width)//2,y+35));text(sheet,key,(x+10,y+5),22)
    sheet.save(out/'审核总览.jpg',quality=94)
    (folder/'素材清单.json').write_text(json.dumps({'family':args.family,'state':'PENDING_VISUAL_REVIEW','items':manifest,'image_roles':recipes},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(args.family,'CURRENT_IMAGE_SET_PENDING_VISUAL_REVIEW',len(manifest))


if __name__=='__main__':main()
