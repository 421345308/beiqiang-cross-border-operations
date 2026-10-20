"""Render the current reviewed assets, without confusing drafts with live binding."""
from pathlib import Path
from html import escape
import os,sys
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s

def main():
    out=s.BASE/'图片复核.html';sections=[]
    plans=[('M001 · 已替换并正式核验','三色18个并码SKU；主图与产品详情已替换。',s.load(s.BASE/'M001/事实与页面计划.json'),None),('A116 · 新主图组','紫色EU35–40，其余三色EU35–45；新主图先在10000044007878绑定，其他链接分别检查。',None,s.load(s.BASE/'图库重做/BQ018_主图库/计划.json'))]
    for title,description,m001,gallery in plans:
        if gallery:
            assets=gallery['assets'];v=s.BASE/'图库重做/BQ018_主图库/商品/10000044007878/verification.json';status=s.load(v)['state']if v.exists()else'PREPARED_NOT_SUBMITTED'
        else:
            base=s.ROOT/'01_产品资产/02_可发布素材/00_最终上传/BQ-M001/05_AI候选';assets={k:{'file':s.rel(base/f)}for k,f in {'M1':'M1_black.png','M2':'M2_colors.png','M3':'M4_entry.png','M4':'M3_sole.png','M5':'M5_wear.png'}.items()};status=s.load(s.BASE/'M001/verification.json')['state']
        labels={'M1':'搜索首图','M2':'真实颜色与对应尺码','M3':'穿脱与闭合结构','M4':'鞋面与鞋底细节','M5':'上脚与日常穿搭'};cards=[]
        for role in ('M1','M2','M3','M4','M5'):
            image=s.ROOT/assets[role]['file'];url=os.path.relpath(image,out.parent).replace('\\','/');cards.append('<figure><img loading="lazy" src="'+escape(url,quote=True)+'"><figcaption>'+labels[role]+'</figcaption></figure>')
        translated={'FORMAL_FIELDS_SCORE_PASS':'图片已通过正式绑定与评分核验','REVIEW_PENDING':'商品图已提交，平台审核中'}.get(status,'图片仍在复核，未报完成')
        sections.append('<section><h2>'+title+'</h2><p>'+description+'</p><p class="status">'+translated+'</p><div class="grid">'+''.join(cards)+'</div></section>')
    for title,key,note in [('R1811 · 六色总览','BQ015_六色总览','三条链接分别替换重复的绿色侧面图，保留各自首图、鞋底、后跟和工厂图位置；六色EU35–45，每条66SKU，999为可询货标记。'),('229 · 七色总览','BQ-NS003_颜色总览','黑白、灰、全黑、卡其、绿、桃红EU35–45；紫色EU35–43。对应颜色鞋底保留原样，不统一改成同一种。')]:
        folder=s.BASE/'图库重做'/key;plan=s.load(folder/'计划.json');passed=all(s.load(folder/'商品'/pid/'verification.json')['state']=='FORMAL_FIELDS_SCORE_PASS'for pid in plan['ids']);f=s.ROOT/plan['assets']['COLORS']['file'];url=os.path.relpath(f,out.parent).replace('\\','/')
        sections.append('<section><h2>'+title+'</h2><p>'+note+'</p><p class="status">'+('已正式生效，评分5.0'if passed else'待核验，不报完成')+'</p><figure style="max-width:900px"><img loading="lazy" src="'+escape(url,quote=True)+'"><figcaption>来源对应的完整配色与尺码总览</figcaption></figure></section>')
    out.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>商品图片复核</title><style>body{font:16px/1.65 system-ui,Microsoft YaHei,sans-serif;margin:0;background:#f2f5f8;color:#16263a}main{max-width:1480px;margin:auto;padding:32px}h1{font-size:30px}h2{margin-top:0}.intro{color:#526277}section{background:white;border-radius:16px;padding:24px;margin:28px 0}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}figure{margin:0;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden}img{width:100%;height:auto;display:block}figcaption{padding:12px 16px;font-weight:600}.status{color:#a25010;background:#fff5e8;display:inline-block;padding:6px 12px;border-radius:8px}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}main{padding:14px}}@media(max-width:550px){.grid{grid-template-columns:1fr}}</style><main><h1>商品图片复核</h1><p class="intro">每张图承担一个产品问题。来源原图与当前成品保留在对应单款目录，出图、提交与正式生效分别记录。</p>'+''.join(sections)+'<p>其他商品的图库复盘与待修项目从本目录README进入；本页不代表全店图片已替换完成。</p></main></html>',encoding='utf8');print('PREVIEW_UPDATED')

if __name__=='__main__':main()
