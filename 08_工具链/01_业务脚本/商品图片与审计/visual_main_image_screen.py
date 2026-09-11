"""Read-only screen for suspicious Alibaba main-image composition.

Downloads only the current first image for each API product, caches it locally,
and emits measurable flags plus a contact sheet. It does not call any write API.
"""
from __future__ import annotations
import csv, hashlib, io, json, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image, ImageStat, ImageDraw, ImageFont

ROOT=Path(r"C:\Users\spq\Desktop\贝强")
AUDIT=ROOT/"02_Alibaba运营/01_店铺与全店诊断/全量商品审查_2026-09-04"
DETAILS=AUDIT/"api_product_get_details.json"
OUT=AUDIT/"主图视觉二次筛查_2026-09-04"
CACHE=OUT/"cache"

def fetch(url: str, path: Path):
    if path.exists(): return True
    try:
        req=Request(url,headers={"User-Agent":"Mozilla/5.0"})
        path.write_bytes(urlopen(req,timeout=25).read()); return True
    except Exception: return False

def metrics(im: Image.Image):
    im=im.convert("RGB").resize((256,256))
    pix=list(im.getdata()); border=pix[:256]+pix[-256:]+[im.getpixel((x,0)) for x in range(256)]+[im.getpixel((x,255)) for x in range(256)]
    b=ImageStat.Stat(Image.new("RGB",(len(border),1))); b.mean=[sum(x[i] for x in border)/len(border) for i in range(3)]
    # Border variation catches collage/striped/patterned backgrounds; near-white is expected.
    means=b.mean; var=sum(sum((p[i]-means[i])**2 for i in range(3))**.5 for p in border)/len(border)
    # connected-ish foreground estimate by contrast against median border color
    bg=tuple(int(x) for x in means); mask=[]
    for p in pix:
        mask.append(sum((p[i]-bg[i])**2 for i in range(3))**.5>28)
    ys=[i//256 for i,v in enumerate(mask) if v]; xs=[i%256 for i,v in enumerate(mask) if v]
    occ=((max(xs)-min(xs)+1)*(max(ys)-min(ys)+1)/65536) if xs else 0
    # ratio of dark/strongly colored pixels in outer 15%: flags background graphics and cutout edges
    edge=[]
    for y in range(256):
        for x in range(256):
            if x<38 or x>=218 or y<38 or y>=218: edge.append(pix[y*256+x])
    chroma=sum(max(p)-min(p)>40 and min(p)<210 for p in edge)/len(edge)
    dark=sum(max(p)<110 for p in edge)/len(edge)
    return var,occ,chroma,dark

def main():
    data=json.loads(DETAILS.read_text(encoding="utf-8")); CACHE.mkdir(parents=True,exist_ok=True); OUT.mkdir(exist_ok=True)
    def one(item):
        pid, rec = item
        p=rec.get("product") or {}; imgs=(p.get("main_image") or {}).get("images") or []
        if not imgs:
            rows.append(dict(product_id=pid,model="",title=p.get("subject",""),image_no=1,url="",status="NO_MAIN_IMAGE",reason="无主图"))
            return dict(product_id=pid,model="",title=p.get("subject",""),image_no=1,url="",status="NO_MAIN_IMAGE",reason="无主图")
        url=imgs[0]; f=CACHE/(hashlib.sha1(url.encode()).hexdigest()+".jpg"); ok=fetch(url,f)
        if not ok: return dict(product_id=pid,model="",title=p.get("subject",""),image_no=1,url=url,status="DOWNLOAD_ERROR",reason="当前主图无法下载")
        try: im=Image.open(f); var,occ,chroma,dark=metrics(im)
        except Exception as e: return dict(product_id=pid,model="",title=p.get("subject",""),image_no=1,url=url,status="DECODE_ERROR",reason=str(e))
        reasons=[]
        if var>30: reasons.append(f"边框背景变化大({var:.1f})，疑似拼图/条纹/复杂背景")
        if occ<0.35: reasons.append(f"主体占画布偏小({occ:.2f})，需人工确认点击辨识度")
        if chroma>0.16 or dark>0.18: reasons.append(f"边缘存在强色/深色图形(chroma={chroma:.2f},dark={dark:.2f})，疑似非纯净商品主图")
        status="REVIEW" if reasons else "PASS_HEURISTIC"
        return dict(product_id=pid,model="",title=p.get("subject",""),image_no=1,url=url,status=status,reason="；".join(reasons),cache=str(f),metrics=f"border_var={var:.1f};occupancy={occ:.2f};edge_chroma={chroma:.2f};edge_dark={dark:.2f}")
    rows=[]
    with ThreadPoolExecutor(max_workers=12) as pool:
        rows=list(pool.map(one,data.items()))
    with (OUT/"主图视觉二次筛查.csv").open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    flagged=[r for r in rows if r["status"]=="REVIEW"]
    # compact contact sheet for human review, with product ID and reasons.
    thumbs=[]
    for r in flagged:
        if not r.get("cache"): continue
        try:
            im=Image.open(r["cache"]).convert("RGB"); im.thumbnail((220,220)); card=Image.new("RGB",(420,285),"white"); card.paste(im,((220-im.width)//2,5));
            d=ImageDraw.Draw(card); d.text((8,230),r["product_id"],fill=(0,0,0)); d.text((8,247),r["title"][:50],fill=(0,0,0)); d.text((8,264),r["reason"][:62],fill=(180,0,0)); thumbs.append(card)
        except Exception: pass
    cols=3; sheet=Image.new("RGB",(cols*420,((len(thumbs)+cols-1)//cols)*285),(235,235,235))
    for i,card in enumerate(thumbs): sheet.paste(card,((i%cols)*420,(i//cols)*285))
    sheet.save(OUT/"疑似异常主图联系表.jpg",quality=92)
    print(json.dumps({"total":len(rows),"review":len(flagged),"pass":sum(r["status"]=="PASS_HEURISTIC" for r in rows)},ensure_ascii=False))
if __name__=="__main__": main()
