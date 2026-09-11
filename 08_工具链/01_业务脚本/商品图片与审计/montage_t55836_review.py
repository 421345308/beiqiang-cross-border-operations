from pathlib import Path
import pandas as pd
from PIL import Image,ImageDraw
ROOT=Path(r'C:\Users\spq\Desktop\贝强')
f=ROOT/'02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/全六图视觉二次审计_2026-09-04/全六图逐槽视觉筛查.csv'
d=pd.read_csv(f,encoding='utf-8-sig'); ids=['1601939638522','1601939619687','1601939736061']; d=d[d.product_id.astype(str).isin(ids)]
out=ROOT/'02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04/全六图视觉二次审计_2026-09-04/T55836_三链接人工复核联系表.jpg'
s=Image.new('RGB',(1200,900),'white'); dr=ImageDraw.Draw(s)
for i,(_,r) in enumerate(d.iterrows()):
    im=Image.open(r.cache).convert('RGB').resize((190,190)); x=(i%6)*200; y=(i//6)*300; s.paste(im,(x+5,y+5)); dr.text((x+5,y+200),str(r.product_id)+' M'+str(r.image_position),fill='black'); dr.text((x+5,y+218),str(r.model)[:20],fill='black')
s.save(out,quality=94)
print(out)
