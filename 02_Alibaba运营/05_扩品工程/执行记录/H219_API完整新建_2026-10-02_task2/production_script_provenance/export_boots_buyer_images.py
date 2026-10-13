"""Adapt the verified task-2 native HTML/SVG export used for 936.
No generated/repainted shoe pixels; original source rectangles are preserved.
Run one style at a time. Uses an isolated headless Chrome profile.
"""
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import base64,json,subprocess,tempfile,concurrent.futures,html,hashlib,sys,datetime
W=Path(__file__).resolve().parent
STYLE=sys.argv[1]
assert STYLE in ['H219','F2888']
src=W/('ls2017_1565538' if STYLE=='H219' else 'shangchao_2357652')
out=W/(STYLE+'_execution')/'assets';out.mkdir(parents=True,exist_ok=True)
# Rectangles are [left,top,width,height], verified against actual source views.
# A photo may recur for an explicitly different detail role, never as a filler.
if STYLE=='H219':
 rows=[
  ('M1','detail_03.jpg',[0,105,790,858],'LACE-UP ANKLE BOOTS','Side zipper | Lug sole'),
  ('M2','detail_05.jpg',[35,145,706,283],'BROWN & BLACK','Single-shoe version | Size labels 35-40'),
  ('M3','detail_11.jpg',[54,218,342,410],'SIDE ZIPPER','Front lacing and an inner-side zipper'),
  ('M4','detail_10.jpg',[0,206,790,616],'RUBBER OUTSOLE','Actual lug tread shown'),
  ('M5','detail_14.jpg',[25,86,744,705],'ON-FOOT VIEW','Round toe | Lace-up ankle silhouette'),
  ('M6','detail_09.jpg',[54,314,690,570],'PU UPPER','A closer look at the toe and upper'),
  ('D1','detail_05.jpg',[35,145,706,283],'TWO COLOR OPTIONS','Brown and Black | Single-shoe version | Size labels 35-40'),
  ('D2','detail_11.jpg',[54,218,342,410],'LACING & ZIPPER','Review the opening and closure for your assortment.'),
  ('D3','detail_10.jpg',[0,206,790,616],'OUTSOLE DETAILS','Rubber outsole | Actual tread pattern'),
  ('D4','detail_14.jpg',[25,86,744,705],'BUILD YOUR COLOR-SIZE MIX','Send quantities by color and size, destination and packing requirements.'),
  ('Brown','detail_05.jpg',[35,145,309,283],'',''),
  ('Black','detail_05.jpg',[423,145,309,283],'','')]
else:
 rows=[
  ('M1','detail_17.jpg',[0,0,750,561],'QUILTED WINTER BOOTS','Plush lining | Side zipper'),
  ('M2','detail_04.jpg',None,'THREE COLOR OPTIONS','Khaki / Black / Cream | Size labels 35-42'),
  ('M3','detail_08.jpg',None,'OPENING & ZIPPER','See the actual opening and plush interior'),
  ('M4','detail_17.jpg',[200,35,470,420],'QUILTED UPPER','Actual panel and stitching details'),
  ('M5','detail_07.jpg',None,'ON-FOOT VIEW','Round toe | Quilted boot silhouette'),
  ('M6','detail_16.jpg',None,'BLACK COLOR VIEW','Size labels 35-42 | Confirm your color-size quantities'),
  ('D1','detail_04.jpg',None,'COLOR & SIZE OPTIONS','Khaki, Black and Cream | Size labels 35-42'),
  ('D2','detail_08.jpg',None,'PLUSH LINING & SIDE ZIPPER','Actual interior view | Confirm measurements for your order'),
  ('D3','detail_17.jpg',None,'QUILTED CONSTRUCTION','Actual upper panels and stitching'),
  ('D4','detail_15.jpg',None,'REQUEST AN ORDER QUOTATION','Send color-size quantities, destination, packing and dispatch requirements.')]
 # F2888 crops still require original-resolution review before rendering.
 raise SystemExit('F2888 rectangles intentionally HOLD pending per-image crop review; do not export unchecked Chinese overlays.')

def render(row):
 code,file,crop,title,copy=row;path=src/file
 w,h=Image.open(path).size;x,y,cw,ch=crop or [0,0,w,h]
 assert x>=0 and y>=0 and x+cw<=w and y+ch<=h,(code,crop,w,h)
 size=800 if code in ['Brown','Black'] else 1000 if code.startswith('M') else 1200
 uri='data:image/jpeg;base64,'+base64.b64encode(path.read_bytes()).decode()
 svg=f'<svg viewBox="{x} {y} {cw} {ch}"><defs><clipPath id="crop"><rect x="{x}" y="{y}" width="{cw}" height="{ch}"/></clipPath></defs><image width="{w}" height="{h}" href="{uri}" clip-path="url(#crop)"/></svg>'
 # Native SVG layout, same mature exporter as 936; no source-shoe repaint.
 doc=f'''<html><meta charset="utf-8"><style>html,body{{margin:0;width:{size}px;height:{size}px;overflow:hidden;background:white;font-family:Arial;color:#182937}}main{{box-sizing:border-box;height:100%;padding:{int(size*.055)}px;display:flex;flex-direction:column}}h1{{font-size:{int(size*.041)}px;line-height:1.1;margin:0 0 18px;letter-spacing:.015em}}.photo{{flex:1;min-height:0;display:flex;align-items:center;justify-content:center}}svg{{width:100%;height:100%}}p{{font-size:{int(size*.027)}px;line-height:1.4;margin:22px 0 0}}</style><main><h1>{html.escape(title)}</h1><div class="photo">{svg}</div><p>{html.escape(copy)}</p></main></html>'''
 page=out/(code+'.html');page.write_text(doc,encoding='utf-8');target=out/(STYLE+'_'+code+'.png')
 profile=tempfile.mkdtemp(prefix=STYLE+'_export_'+code+'_')
 args=['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--hide-scrollbars','--no-first-run','--no-default-browser-check','--user-data-dir='+profile,f'--window-size={size},{size}','--screenshot='+str(target),'--virtual-time-budget=1200',page.as_uri()]
 result=subprocess.run(args,capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
 (out/(code+'.chrome.log')).write_bytes(result.stdout+b'\n'+result.stderr)
 assert result.returncode==0 and target.exists(),code
 assert Image.open(target).size==(size,size)
 return {'name':code,'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_pixels':[w,h],'crop':crop,'crop_pixels':[cw,ch],'title':title,'copy':copy,'target_size':[size,size],'review_status':'REQUIRES_INDIVIDUAL_VISUAL_REVIEW'}

assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime(2026,10,2,18,tzinfo=datetime.timezone.utc),'Hard stop reached; no automatic resume'
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:result=list(ex.map(render,rows))
(out.parent/'asset_manifest.json').write_text(json.dumps({'style':STYLE,'assets':result,'approval':'NOT_YET_VISUALLY_APPROVED'},ensure_ascii=False,indent=2),encoding='utf-8')
canvas=Image.new('RGB',(2500,1100),'#eef2f5');draw=ImageDraw.Draw(canvas)
for i,r in enumerate(result):
 im=ImageOps.contain(Image.open(r['path']),(480,480));x=i%5*500;y=i//5*550;canvas.paste(im,(x+10,y+30));draw.text((x+12,y+8),r['name'],fill='black')
canvas.save(out.parent/'production_contact.jpg')
print('Rendered',STYLE,'six main and four detail images; individual review required before upload.',flush=True)
