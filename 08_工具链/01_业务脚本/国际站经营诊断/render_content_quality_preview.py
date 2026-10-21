"""Render the current reviewed assets, without confusing drafts with live binding."""
from pathlib import Path
from html import escape
import os,sys,json
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s
import schema_publish_contract as c

def current_catalog(out):
    """Show current per-ID formal bindings, not every historical candidate."""
    closure_file=s.BASE/'全店图片终检.json'
    if not closure_file.exists():return ''
    registry=s.load(s.ProductRegistry(s.ROOT));byid={l['id']:l for l in registry['listings']}
    cache=s.load(s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前素材清单.json')['assets']
    native={c._created_image_identity(u):r for u,r in cache.items()if r.get('file')}
    families={}
    def cards(urls,labels):
        result=[]
        for u,label in zip(urls,labels):
            a=native[c._created_image_identity(u)];f=s.ROOT/a['file'];assert f.is_file()
            src=os.path.relpath(f,out.parent).replace('\\','/')
            result.append('<figure><a href="'+escape(src,quote=True)+'" target="_blank"><img loading="lazy" src="'+escape(src,quote=True)+'" alt="'+escape(label,quote=True)+'"></a><figcaption>'+escape(label)+'</figcaption></figure>')
        return '<div class="grid">'+''.join(result)+'</div>'
    for item in s.load(closure_file)['items']:
        pid=item['id'];l=byid[pid];p=s.load(s.ROOT/l['formal_fields']['file'])['response']['product']
        main=p['main_image']['images'];detail=[r['image_url']for r in p['struct_detail']['detail_image']['images']]
        colour=next((a['values']for a in p['product_sku']['sku_attributes']if str(a['attribute_id'])=='191288010'),[])
        labels=['工厂总览'if c._created_image_identity(u)==c._created_image_identity('https://sc04.alicdn.com/kf/Hea3fc4c6da4b46e0bb75c003260875120.png')else'搜索首图'if i==0 else'主图 '+str(i+1)for i,u in enumerate(main)]
        body='<p>'+escape(p.get('subject',''))+'</p><p>主图</p>'+cards(main,labels)+'<p>本款产品详情</p>'+cards(detail,['产品详情 '+str(i+1)for i in range(len(detail))])
        if colour:body+='<details><summary>查看本款规格照片</summary>'+cards([v['image_url']for v in colour],[v['system_value_name']for v in colour])+'</details>'
        states='已正式核验并同步'if item['state']=='FORMAL_IMAGE_CLOSURE_PASS'else'仍待核验'
        families.setdefault(l['product_id'],[]).append((pid,p.get('subject',''),body,states))
    suite=s.load(s.ROOT/'02_Alibaba运营/06_图片与检查记录/共享工厂详情/V8/url_identity.json')['items']
    shared='<details><summary>全店统一工厂详情（6张，含包装与运输）</summary>'+cards([r['accepted_urls'][0]for r in suite],['公司简介','OEM/ODM开发','生产流程','品质管理','包装','运输'])+'</details>'
    result=['<section id="catalog"><h2>全店当前图片</h2><p>这里按商品当前正式回读展示；每条链接单独列出，点击图片可查看原尺寸。下方制作记录只用于追溯。</p>'+shared+'<input id="find" type="search" placeholder="输入货号、商品ID或标题关键词" style="box-sizing:border-box;width:100%;padding:12px;font:inherit;border:1px solid #b9c7d5;border-radius:8px">']
    for family,rows in sorted(families.items()):
        search=' '.join([family]+[pid+' '+title for pid,title,body,state in rows]).lower()
        result.append('<details class="product" data-search="'+escape(search,quote=True)+'"><summary>'+escape(family)+' · '+str(len(rows))+'条链接</summary>')
        for pid,title,body,state in rows:result.append('<details><summary>商品 '+pid+' · '+state+'</summary>'+body+'</details>')
        result.append('</details>')
    result.append('</section><script>document.getElementById("find").addEventListener("input",function(){const q=this.value.trim().toLowerCase();document.querySelectorAll(".product").forEach(function(e){e.hidden=!!q&&!e.dataset.search.includes(q);if(q&&!e.hidden)e.open=true;});});</script>')
    return ''.join(result)

def main():
    out=s.BASE/'图片复核.html';sections=[]
    closure_file=s.BASE/'全店图片终检.json'
    if closure_file.exists():
        closure=s.load(closure_file);passed=closure.get('states',{}).get('FORMAL_IMAGE_CLOSURE_PASS',0);total=closure.get('eligible',0)
        sections.append('<section><h2>全店当前图片核对：'+str(passed)+' / '+str(total)+'</h2><p>按原商品ID核对主图、标准工厂图、产品详情、规格照片和本地当前档案。下列批次展开后可查看实际成品；评分和API回读与逐张原件对照分别留证。</p></section>')
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
    current=[]
    for filename in ('详情图组收尾执行.json','模板清理执行.json','首图修复执行.json','功能详情精修执行.json','专款配色详情执行.json','补充尺码图执行.json','配色图执行.json','旧报价图执行.json'):
        indexfile=s.BASE/filename
        if not indexfile.exists():continue
        groups=[]
        for g in s.load(indexfile)['groups']:
            folder=s.BASE/'图库重做'/g['family'];plan=s.load(folder/'计划.json');states=[]
            for pid in g['ids']:
                vf=folder/'商品'/pid/'verification.json'
                latest=g.get('current_states',{}).get(pid,{})
                if latest.get('proof'):vf=s.ROOT/latest['proof']
                v=s.load(vf)if vf.exists()else{}
                states.append(pid+'：'+('正式生效 / '+str(v.get('score'))+'分'if v.get('state')=='FORMAL_FIELDS_SCORE_PASS'else'待修正或核验'))
            cards=[]
            for role,row in plan['assets'].items():
                f=s.ROOT/row['file'];url=os.path.relpath(f,out.parent).replace('\\','/');cards.append('<figure><img loading="lazy" src="'+escape(url,quote=True)+'"><figcaption>'+escape(role)+'</figcaption></figure>')
            groups.append('<details><summary>'+escape(g['family'])+' · '+str(len(g['ids']))+'条商品</summary><p>'+escape('；'.join(states))+'</p><div class="grid">'+''.join(cards)+'</div></details>')
        current.append('<section><h2>'+escape(filename.removesuffix('.json'))+'</h2><p>下列状态逐商品读取正式回执；展开查看对应当前成品。未通过的记录保留，不以新图已生成代替生效。</p>'+''.join(groups)+'</section>')
    visible=''.join(sections[:1])+current_catalog(out)if closure_file.exists()else''
    evidence='<details><summary>制作与变更证据（含历史回执）</summary>'+''.join(current+sections[1:]if closure_file.exists()else current+sections)+'</details>'
    out.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>商品图片复核</title><style>body{font:16px/1.65 system-ui,Microsoft YaHei,sans-serif;margin:0;background:#f2f5f8;color:#16263a}main{max-width:1480px;margin:auto;padding:32px}h1{font-size:30px}h2{margin-top:0}.intro{color:#526277}section{background:white;border-radius:16px;padding:24px;margin:28px 0}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}figure{margin:0;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden}img{width:100%;height:auto;display:block}figcaption{padding:12px 16px;font-weight:600}details{padding:16px 0;border-top:1px solid #e2e8f0}summary{font-weight:650;cursor:pointer}.status{color:#a25010;background:#fff5e8;display:inline-block;padding:6px 12px;border-radius:8px}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}main{padding:14px}}@media(max-width:550px){.grid{grid-template-columns:1fr}}</style><main><h1>商品图片复核</h1><p class="intro">更新时间：'+escape(s.now())+'。原件与当前成品保留在对应单款目录。下方先显示每条商品当前正式绑定的图片，制作与变更证据单独折叠。按负责人要求使用API验收，不逐款进行浏览器回读。</p>'+visible+evidence+'<p>全店覆盖与当前结论见本目录README。</p></main></html>',encoding='utf8');print('PREVIEW_UPDATED')

if __name__=='__main__':main()
