"""Task-scoped reuse of native SVG/Chrome photo layout; original shoe pixels only."""
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
import base64,json,subprocess,tempfile,concurrent.futures,html,hashlib
W=Path(__file__).resolve().parent;O=W/'F2888_execution';src=W/'shangchao_2357652';out=O/'assets';out.mkdir(parents=True,exist_ok=True)
assert json.loads((O/'resume_authorization.json').read_text(encoding='utf-8'))['authorized']
C={'Khaki':[205,445,322,220],'Cream':[30,720,313,216],'Black':[398,720,322,216]}
rows=[
 ('M1','main.jpg',[50,180,700,580],'QUILTED WINTER BOOTS','Plush lining | Side zipper'),
 ('M2','detail_04.jpg',list(C.values()),'THREE COLOR OPTIONS','Khaki / Cream / Black | Size labels 35-42'),
 ('M3','detail_08.jpg',[16,27,716,750],'OPENING & LINING','Actual plush interior and side zipper'),
 ('M4','detail_17.jpg',[240,175,300,215],'QUILTED UPPER','Actual panel and stitching details'),
 ('M5','detail_07.jpg',[245,0,487,780],'ON-FOOT VIEW','Round toe | Quilted boot silhouette'),
 ('M6','detail_04.jpg',C['Black'],'BLACK COLOR VIEW','Review this color for your assortment'),
 ('D1','detail_04.jpg',list(C.values()),'COLOR & SIZE OPTIONS','Khaki / Cream / Black | Size labels 35-42'),
 ('D2','detail_08.jpg',[16,27,716,750],'PLUSH INTERIOR','Artificial plush shaft lining and short-plush insole'),
 ('D3','detail_15.jpg',[140,220,325,210],'SIDE ZIPPER & PANELS','Actual closure and quilted upper construction'),
 ('D4','detail_07.jpg',[245,0,487,780],'BUILD YOUR COLOR-SIZE MIX','Send quantities, destination, packing and requested dispatch date.'),
 *[(c,'detail_04.jpg',crop,'','') for c,crop in C.items()]]
def render(row):
 code,file,crop,title,copy=row;p=src/file;w,h=Image.open(p).size;multiple=isinstance(crop[0],list);rects=crop if multiple else [crop]
 uri='data:image/jpeg;base64,'+base64.b64encode(p.read_bytes()).decode();svg=[]
 for i,(x,y,cw,ch) in enumerate(rects):
  assert x>=0 and y>=0 and x+cw<=w and y+ch<=h
  svg.append(f'<svg viewBox="{x} {y} {cw} {ch}"><defs><clipPath id="crop{i}"><rect x="{x}" y="{y}" width="{cw}" height="{ch}"/></clipPath></defs><image width="{w}" height="{h}" href="{uri}" clip-path="url(#crop{i})"/></svg>')
 size=800 if code in C else 1000 if code.startswith('M') else 1200
 content=''.join('<div class="color">'+v+(f'<label>{list(C)[i]}</label>' if multiple else '')+'</div>' for i,v in enumerate(svg))
 doc=f'<html><meta charset="utf-8"><style>html,body{{margin:0;width:{size}px;height:{size}px;overflow:hidden;background:white;font-family:Arial;color:#182937}}main{{box-sizing:border-box;height:100%;padding:{int(size*.055)}px;display:flex;flex-direction:column}}h1{{font-size:{int(size*.041)}px;line-height:1.1;margin:0 0 18px}}.photo{{flex:1;min-height:0;display:flex;align-items:center;justify-content:center}}.color{{width:100%;height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center}}svg{{width:100%;height:100%}}label{{font-size:{int(size*.027)}px}}p{{font-size:{int(size*.027)}px;line-height:1.4;margin:22px 0 0}}</style><main><h1>{html.escape(title)}</h1><div class="photo">{content}</div><p>{html.escape(copy)}</p></main></html>'
 page=out/(code+'.html');page.write_text(doc,encoding='utf-8');target=out/('F2888_'+code+'.png');profile=tempfile.mkdtemp(prefix='F2888_export_'+code+'_')
 args=['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--hide-scrollbars','--no-first-run','--no-default-browser-check','--user-data-dir='+profile,f'--window-size={size},{size}','--screenshot='+str(target),'--virtual-time-budget=1200',page.as_uri()]
 r=subprocess.run(args,capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW);(out/(code+'.chrome.log')).write_bytes(r.stdout+b'\n'+r.stderr)
 assert r.returncode==0 and target.exists(),code;assert Image.open(target).size==(size,size)
 return {'name':code,'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'source':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_pixels':[w,h],'crop':crop,'crop_pixels':[[a[2],a[3]] for a in rects],'title':title,'copy':copy,'target_size':[size,size],'review_status':'REQUIRES_INDIVIDUAL_VISUAL_REVIEW'}
import sys
if '--hero-only' in sys.argv:
 previous=json.loads((O/'asset_manifest.json').read_text(encoding='utf-8'));result=[render(rows[0])]+[x for x in previous['assets'] if x['name']!='M1']
else:
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:result=list(ex.map(render,rows))
(O/'asset_manifest.json').write_text(json.dumps({'style':'F2888','assets':result,'approval':'NOT_YET_VISUALLY_APPROVED'},ensure_ascii=False,indent=2),encoding='utf-8')
canvas=Image.new('RGB',(2500,1650),'#eef2f5');draw=ImageDraw.Draw(canvas)
for i,r in enumerate(result):
 im=ImageOps.contain(Image.open(r['path']),(480,480));x=i%5*500;y=i//5*550;canvas.paste(im,(x+10,y+30));draw.text((x+12,y+8),r['name'],fill='black')
canvas.save(O/'production_contact.jpg');print('Rendered 13 real-photo assets; individual visual review pending.')
