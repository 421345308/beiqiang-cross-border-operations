from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

R=Path(r"C:\Users\spq\Desktop\贝强")
O=R/"02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/BQ019_W1_整页视觉样板_v5_2026-09-16"
M,D,C,A,P=[O/x for x in ("01_主图六张","02_产品详情四张","03_公司详情五张","04_待确认AI候选","05_审阅预览")]
for x in (M,D,C,P):
 x.mkdir(parents=True,exist_ok=True)
 for f in x.glob("*.jpg"): f.unlink()
RAW=R/"01_产品资产/01_原始数据包/已整理_BQ019_A206_A206情侣鞋图片/A206情侣鞋图片/主图"
FAC=R/"01_产品资产/02_可发布素材/00_最终上传/00_厂家资料/00_精选可用照片"
W=H=1200; INK="#14231F"; MUT="#5D6966"; GRN="#126B50"; DEEP="#073E32"; WHT="#FFFFFF"; LINE="#C7D7D1"
def F(n,b=False): return ImageFont.truetype(str(Path(r"C:\Windows\Fonts")/("arialbd.ttf" if b else "arial.ttf")),n)
def im(p): return Image.open(p).convert("RGB")
def tx(d,xy,s,n,c=INK,b=False,a=None): d.text(xy,s,font=F(n,b),fill=c,anchor=a)
def cv(bg="#F7F9F8"): return Image.new("RGB",(W,H),bg)
def mask(sz,r=25):
 m=Image.new("L",sz); ImageDraw.Draw(m).rounded_rectangle((0,0,sz[0]-1,sz[1]-1),r,fill=255); return m
def contain(x,sz,bg=WHT,p=10):
 f=Image.new("RGB",sz,bg); y=ImageOps.contain(x,(sz[0]-2*p,sz[1]-2*p),Image.Resampling.LANCZOS); f.paste(y,((sz[0]-y.width)//2,(sz[1]-y.height)//2)); return f
def cover(x,sz,focus=(.5,.5)):
 q=max(sz[0]/x.width,sz[1]/x.height); x=x.resize((round(x.width*q),round(x.height*q)),Image.Resampling.LANCZOS)
 a=max(0,min(x.width-sz[0],round((x.width-sz[0])*focus[0]))); b=max(0,min(x.height-sz[1],round((x.height-sz[1])*focus[1]))); return x.crop((a,b,a+sz[0],b+sz[1]))
def put(pg,x,box,fit="cover",bg=WHT,focus=(.5,.5),r=25):
 a,b,w,h=box; y=contain(x,(w,h),bg) if fit=="contain" else cover(x,(w,h),focus); pg.paste(y,(a,b),mask((w,h),r))
def card(d,bx,fill=WHT): d.rounded_rectangle(bx,25,fill=fill,outline=LINE,width=2)
def head(pg,e,t,s="",dark=False):
 d=ImageDraw.Draw(pg); tx(d,(60,52),e.upper(),19,"#9FD8C5" if dark else GRN,True); tx(d,(60,91),t,42,WHT if dark else INK,True)
 if s: tx(d,(60,148),s,19,"#D3E7E0" if dark else MUT)
 return d
def sq(src,dst): contain(im(src),(1200,1200),WHT,0).save(dst,quality=96)
def contacts(paths,dst,cols,th):
 lh=44; rows=(len(paths)+cols-1)//cols; sh=Image.new("RGB",(cols*th,rows*(th+lh)),"#E6ECE9"); d=ImageDraw.Draw(sh)
 for i,p in enumerate(paths):
  x=(i%cols)*th; y=(i//cols)*(th+lh); sh.paste(contain(im(p),(th,th),WHT,3),(x,y)); tx(d,(x+8,y+th+22),p.stem,14,INK,True,"lm")
 sh.save(dst,quality=94)

g=im(A/"PASS_M1_light_grey_hero.png"); b=im(A/"PASS_M2_black_pair.png"); c=im(A/"PASS_M3_cream_rear_opening.png"); w=im(A/"HOLD_M4_white_top_side.png")
factory=im(A/"PASS_C1_factory_left_entrance.png"); workshop=im(A/"PASS_C2_workshop_cleanup.png")
sq(A/"PASS_M1_light_grey_hero.png",M/"M1_light_grey_search_hero.jpg")
sq(A/"PASS_M2_black_pair.png",M/"M2_black_pair_three_quarter.jpg")
sq(A/"PASS_M3_cream_rear_opening.png",M/"M3_cream_rear_opening.jpg")
sq(A/"HOLD_M4_white_top_side.png",M/"M4_white_top_and_side_HOLD.jpg")

pg=cv("#E8F2EE"); d=head(pg,"A206 COLOR RANGE","SELECT THE COLOR DIRECTION","Real source range · final color confirmed before order")
put(pg,im(RAW/"3.jpg"),(55,220,1090,700),focus=(.5,.52))
for i,(n,col) in enumerate((("BLACK","#171717"),("CREAM","#EDE5D3"),("LIGHT GREY","#AAB2B1"),("WHITE","#FFFFFF"))):
 x=55+i*272; card(d,(x,950,x+245,1060)); d.ellipse((x+20,978,x+72,1030),fill=col,outline="#AAB8B3",width=2); tx(d,(x+90,1004),n,17,INK,True,"lm")
pg.save(M/"M5_four_color_range.jpg",quality=95)

pg=cv("#F5F0E5"); d=head(pg,"OEM / ODM + WHOLESALE","SEND A CLEAR BUYING BRIEF","Logo, color and packing options follow the actual request")
put(pg,g,(55,225,470,720),"contain","#EEE9DE")
items=(("LOGO","Artwork + placement"),("COLOR","Target direction"),("SIZE RATIO","Pairs by EU size"),("PACKING","Label + box request"),("QUANTITY","Total pairs"),("DESTINATION","Country / city / port"))
for i,(x1,x2) in enumerate(items):
 x=565+(i%2)*290; y=235+(i//2)*215; card(d,(x,y,x+260,y+180)); tx(d,(x+22,y+28),f"0{i+1}",16,GRN,True); tx(d,(x+22,y+66),x1,20,INK,True); tx(d,(x+22,y+110),x2,16,MUT)
card(d,(565,920,1145,1055),DEEP); tx(d,(855,963),"GET A WORKABLE QUOTE",22,"#A9DBC9",True,"mm"); tx(d,(855,1010),"Send the six inputs above.",18,WHT,False,"mm")
pg.save(M/"M6_oem_odm_quote_brief.jpg",quality=95)

pg=cv(); d=head(pg,"A206 PRODUCT","KNIT / TEXTILE LACE-UP SHOES","Verified listing facts for wholesale discussion"); put(pg,g,(55,220,650,820),"contain")
facts=(("MODEL","A206"),("UPPER","Knit / Textile"),("CLOSURE","Lace-Up"),("SOLE","EVA"),("TOE","Round Toe"),("FIT","Regular Fit"))
for i,(x1,x2) in enumerate(facts):
 y=230+i*132; card(d,(755,y,1145,y+105)); tx(d,(780,y+20),x1,15,GRN,True); tx(d,(780,y+56),x2,22,INK,True)
pg.save(D/"D1_verified_product_overview.jpg",quality=95)

pg=cv(DEEP); d=head(pg,"MULTI-ANGLE PROOF","SEE MORE THAN ONE SHOE FACE","Different colors carry different viewing roles",True)
views=((b,"PAIR / 3⁄4","Black pair and side profile","contain"),(c,"REAR / OPENING","Heel loop and opening","contain"),(im(RAW/"15.jpg"),"TOP / SIDE","Lacing and sole edge","cover"))
for i,(x1,t,s,fit) in enumerate(views):
 x=40+i*390; put(pg,x1,(x,220,360,700),fit,"#EDF1EF"); tx(d,(x+12,960),t,19,"#A9DBC9",True); tx(d,(x+12,1000),s,17,"#D4E8E0")
pg.save(D/"D2_multi_angle_product_proof.jpg",quality=95)

pg=cv("#E8F2EE"); d=head(pg,"ORDER MATRIX","COLOR + SIZE RATIO","EU 35–45 · combinations confirmed for the actual order")
for i,(n,x1) in enumerate((("BLACK",b),("CREAM",c),("LIGHT GREY",g),("WHITE",w))):
 x=45+i*285; put(pg,x1,(x,225,260,430),"contain","#FAFCFB",r=20); tx(d,(x+130,685),n,18,INK,True,"mm")
card(d,(55,765,1145,1045),"#FAFCFB"); tx(d,(90,810),"BUYER INPUT",20,GRN,True); tx(d,(90,858),"Tell us the number of pairs required in each EU size.",24,INK,True); tx(d,(90,920),"35×__  36×__  37×__  ...  45×__",22,MUT); tx(d,(90,980),"Mixed colors and size ratios are confirmed for the order.",18,MUT)
pg.save(D/"D3_color_size_order_matrix.jpg",quality=95)

pg=cv("#F5F0E5"); d=head(pg,"BUYER FAQ","ANSWERS BEFORE YOU SEND AN INQUIRY","Claims remain tied to the model and actual order")
faq=(("Can I add my logo?","Send artwork and placement."),("Can I choose colors?","Select a direction; confirm final color."),("What sizes are available?","Current listing: EU 35–45."),("What is the MOQ?","Listing baseline: 2 pairs."),("How is price decided?","Quantity, material, ratio, packing."),("What should I send?","Model, quantity, files, destination."))
for i,(q,a) in enumerate(faq):
 x=55+(i%2)*570; y=230+(i//2)*270; card(d,(x,y,x+520,y+225)); tx(d,(x+28,y+30),f"0{i+1}",16,GRN,True); tx(d,(x+28,y+72),q,21,INK,True); tx(d,(x+28,y+132),a,17,MUT)
pg.save(D/"D4_buyer_faq.jpg",quality=95)

pg=cv(DEEP); put(pg,factory,(40,40,1120,790),focus=(.5,.53)); d=ImageDraw.Draw(pg); tx(d,(60,875),"SUPPLIER IDENTITY",18,"#A9DBC9",True); tx(d,(60,918),"QUANZHOU BEIQIANG FOOTWEAR & APPAREL",32,WHT,True); tx(d,(60,976),"Source-anchored cleanup · real entrance remains on the far left.",18,"#D4E8E0"); tx(d,(60,1035),"Quanzhou · Fujian · China",20,"#A9DBC9",True)
pg.save(C/"C1_factory_identity_left_entrance.jpg",quality=95)

pg=cv(); d=head(pg,"PRODUCTION ORGANIZATION","A CLEANER VIEW OF THE REAL WORKSHOP","Source-anchored AI cleanup · not evidence of capacity or machine count"); put(pg,workshop,(55,220,1090,720),focus=(.5,.52))
for i,(x1,x2) in enumerate((("WORKSTATIONS","Visible footwear work area"),("IN-PROCESS SHOES","Organized on racks"),("ACTIVE FLOOR","Workers retained from source"))):
 x=55+i*365; card(d,(x,980,x+340,1080)); tx(d,(x+20,1001),x1,17,GRN,True); tx(d,(x+20,1040),x2,15,MUT)
pg.save(C/"C2_source_anchored_workshop.jpg",quality=95)

pg=cv("#F5F0E5"); d=head(pg,"OEM / ODM PROJECT","FROM BUYER BRIEF TO ORDER SPEC","A communication path, not a generic customization badge")
for i,(x1,x2) in enumerate((("BUYER BRIEF","Model · market · quantity"),("ARTWORK REVIEW","Logo · label · packing"),("SAMPLE SCOPE","Purpose · requested checks"),("ORDER SPEC","Ratio · destination · timing"))):
 x=55+(i%2)*570; y=235+(i//2)*315; card(d,(x,y,x+520,y+265)); d.ellipse((x+28,y+28,x+92,y+92),fill=GRN); tx(d,(x+60,y+60),str(i+1),20,WHT,True,"mm"); tx(d,(x+120,y+40),x1,21,INK,True); tx(d,(x+30,y+135),x2,20,MUT)
card(d,(55,915,1145,1055),DEEP); tx(d,(600,965),"BUYER ACTION",19,"#A9DBC9",True,"mm"); tx(d,(600,1010),"Send reference files and target order information.",18,WHT,False,"mm")
pg.save(C/"C3_oem_odm_project_flow.jpg",quality=95)

pg=cv(DEEP); d=head(pg,"PROCESS CHECKPOINTS","WHAT THE SOURCE PHOTOS ACTUALLY SHOW","Visible handling only · standards confirmed for the order",True)
pics=((FAC/"02_产品检查生产/01_upper_check.jpg","UPPER / FINISH"),(FAC/"02_产品检查生产/02_sole_check.jpg","SOLE / CONSTRUCTION"),(FAC/"02_产品检查生产/03_line_sorting.jpg","LINE SORTING"))
for i,(p,t) in enumerate(pics):
 x=40+i*390; put(pg,im(p),(x,220,360,700)); tx(d,(x+12,960),t,19,"#A9DBC9",True); tx(d,(x+12,1000),"Visible process handling",17,"#D4E8E0")
pg.save(C/"C4_real_process_checkpoints.jpg",quality=95)

pg=cv("#ECF2F5"); d=head(pg,"PACKING + HANDOFF","CONFIRM THE ORDER BEFORE RELEASE","No fixed freight, delivery-time or certification claims")
for i,(x1,x2) in enumerate((("PACKING FILE","Box, label and marks"),("ORDER MATRIX","Quantity, colors, size ratio"),("DESTINATION","Country, city or port"),("TRADE + FORWARDER","Terms and nominated logistics"))):
 x=55+(i%2)*570; y=240+(i//2)*315; card(d,(x,y,x+520,y+260)); tx(d,(x+30,y+35),f"0{i+1}  {x1}",20,GRN,True); tx(d,(x+30,y+110),x2,20,INK)
card(d,(55,920,1145,1055),DEEP); tx(d,(600,966),"FINAL PRICE AND TIMING FOLLOW THE ACTUAL ORDER",19,"#A9DBC9",True,"mm"); tx(d,(600,1010),"Confirm commercial inputs before release.",18,WHT,False,"mm")
pg.save(C/"C5_packing_and_handoff.jpg",quality=95)

mp,dp,cp=[sorted(x.glob("*.jpg")) for x in (M,D,C)]
contacts(mp,P/"01_main_gallery_v5.jpg",3,400); contacts(dp,P/"02_product_detail_v5.jpg",2,500); contacts(cp,P/"03_company_detail_v5.jpg",3,400)
(O/"README.md").write_text("""# BQ019-W1 整页视觉样板 v5

状态：LOCAL REVIEW ONLY，未上传平台。

- 主图6张：灰色搜索首图、黑色双鞋、米白后跟/鞋口、白色俯视/侧底、四色总览、OEM/报价输入。
- 产品详情4张：参数、真实多角度、颜色尺码矩阵、买家FAQ。
- 公司详情5张：厂址身份、车间组织、OEM流程、过程检查、包装交付。
- 厂房入口位于画面最左侧；上一版中央大门图已淘汰。
- M4仍标HOLD，上传前再次核对鞋底边缘。
- C1/C2为基于真实照片的受约束AI环境整理，不证明产能、设备数量、认证或交期。
""",encoding="utf-8")
