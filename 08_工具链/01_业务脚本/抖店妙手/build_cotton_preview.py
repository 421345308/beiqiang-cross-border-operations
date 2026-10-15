"""Build a local, image-embedded review from the Douyin batch record. No HTTP writes."""
import argparse
import base64
import html
import hashlib
import json
from pathlib import Path


def build(workspace: Path):
    business = workspace / '09_国内电商/抖店'
    batch = json.loads((business/'数据/棉鞋上品包.json').read_text(encoding='utf-8-sig'))
    esc = lambda value: html.escape(str(value))
    image_root = workspace / batch['source']['image_dir']
    def image_tag(name, label):
        path = image_root / name
        # Only exact files from the archive manifest can be embedded.
        assert name in {i['name'] for i in batch['source']['images']}
        mime = 'image/png' if path.suffix.lower() == '.png' else 'image/jpeg'
        data = base64.b64encode(path.read_bytes()).decode('ascii')
        return f'<figure><img loading="lazy" src="data:{mime};base64,{data}" alt="{esc(label)}"><figcaption>{esc(name)}</figcaption></figure>'
    def factory_image_tag(asset, label):
        path = workspace / asset['path']
        assert path.resolve().is_relative_to((workspace / '01_产品资产/02_可发布素材').resolve())
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == asset['sha256']
        data = base64.b64encode(raw).decode('ascii')
        return f'<figure><img loading="lazy" src="data:image/jpeg;base64,{data}" alt="{esc(label)}"><figcaption>工厂来源原图 · {esc(path.name)}</figcaption></figure>'
    submitted = sum(s['stage'] in ('AUDIT_PASSED_ON_SALE_API_VERIFIED', 'CREATED_WAREHOUSE_DUPLICATE_GUARD') for s in batch['styles'])
    on_sale = sum(s['stage'] == 'AUDIT_PASSED_ON_SALE_API_VERIFIED' for s in batch['styles'])
    cards = []
    for style in batch['styles']:
        model = style['source_model']
        hold = style['stage'].startswith(('HOLD_', 'EXCLUDED_'))
        badge = {'HOLD_USER_SKIP': '本轮暂缓', 'HOLD_BRAND': '品牌待核', 'EXCLUDED_NO_BRAND_AUTH': '无授权 · 已排除', 'HOLD_EXISTING_LISTING': '既有商品待核', 'HOLD_EXISTING_FLEECE_SKU': '已有加绒SKU · 待整理', 'HOLD_MARKING_UNVERIFIED': '标记身份待核', 'AUDIT_PASSED_ON_SALE_API_VERIFIED': '审核通过 · 后台上架', 'CREATED_WAREHOUSE_DUPLICATE_GUARD': '已建页 · 查重转仓库'}.get(style['stage'], '本地草稿')
        size = style.get('active_size_range') or style['source_size_range']
        size_text = f'{size[0]}—{size[-1]}（当前工厂来源范围）' if size else '工厂店未找到该款，待补来源'
        notes = '；'.join(style['blocking_notes']) or style.get('current_scope', '待完成当前字段核验')
        title = style.get('title_current') or style['title_draft'] or '无品牌授权，已排除销售'
        price_text = f"¥{style['price']:.2f}/双" if style['price'] is not None else '不销售'
        stock_text = '初始填报100/码 · 次日发' if style['stock'] is not None else '不填报'
        source = style.get('current_source_primary') or style.get('current_source') or {}
        source_url = source.get('url', '')
        source_link = f'<p class="muted">工厂来源：<a href="{esc(source_url)}" target="_blank" rel="noreferrer">{esc(source.get("source_model") or source.get("model") or model)}</a> · 核对日2026-10-15</p>' if source_url else '<p class="muted">工厂原页待补</p>'
        state = 'published' if style['stage'] == 'AUDIT_PASSED_ON_SALE_API_VERIFIED' else 'warehouse' if style['stage'] == 'CREATED_WAREHOUSE_DUPLICATE_GUARD' else 'hold' if hold else 'draft'
        cards.append(f'''<article class="card {'hold' if hold else ''}" data-key="{esc(model)}" data-state="{state}">
<div class="cardhead"><h2>{esc(model)}</h2><span class="badge">{esc(badge)}</span></div>
<p class="muted">{esc(style['product_ref'] or '原货号保留 · 身份待绑定')} · {esc(style['structure'])}</p>
{source_link}
<div class="gallery">{''.join(factory_image_tag(a, model) for a in style.get('selected_factory_images', []))}{''.join(image_tag(i['name'], model) for i in style['images'])}</div>
<p class="caption">已选工厂来源原图在前、原包证据在后 · 未用AI改鞋</p>
<h3>标题草稿</h3><p class="title">{esc(title)}</p>
<div class="facts"><p><b>售价</b> {esc(price_text)}</p><p><b>颜色</b> {esc(' / '.join(c['name'] for c in style['colors']))}</p><p><b>尺码</b> {esc(size_text)}</p><p><b>库存</b> {esc(stock_text)}</p></div>
<details><summary>主图与详情安排</summary><p>{esc(style['visual_plan'])}</p><p>核心词：棉鞋。描述词：{esc('、'.join(style['keywords']['descriptive']))}。未取得这些长尾词的独立精确流量。</p><p>图序：完整鞋型 → 可选颜色 → 已有真实绒里/鞋底细节 → 核准尺码。缺少的实物角度保留缺口。</p></details>
<details><summary>详情文字草稿</summary>{''.join('<p>'+esc(line)+'</p>' for line in (style['detail_draft'] or ['该款已排除销售']))}</details>
<p class="issue">{esc(notes)}</p></article>''')
    unknown = ''.join(image_tag(name, '无货号白鞋') for name in batch['unknown_images'])
    unknown_section = ('<section class="panel" style="margin-top:24px"><h2>未归款图片</h2><div class="unknown">'+unknown+'</div></section>') if unknown else '<section class="panel" style="margin-top:24px"><h2>米白款已确认</h2><p>原无货号白鞋与工厂M889-1米白加绒主图SHA256完全一致，已归入M889家族；保留-1来源版本。</p></section>'
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>棉鞋上品准备 · 贝强</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:#172a35;font-family:"Microsoft YaHei",sans-serif;line-height:1.6}main{max-width:1440px;margin:auto;padding:36px 28px}header{background:#173f41;color:white;padding:30px;border-radius:18px}h1{margin:0 0 12px;font-size:30px}h2{margin:0;font-size:23px}h3{font-size:15px;margin:20px 0 6px}p{margin:8px 0}.muted,.caption,figcaption{color:#667782;font-size:12px}.stats{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}.stats div{background:white;border-radius:12px;padding:16px 24px;min-width:160px}.stats strong{display:block;font-size:28px}.panel{background:white;border-radius:14px;padding:22px;margin-bottom:22px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px;text-align:left;border-bottom:1px solid #e5e9ec}nav{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0;position:sticky;top:0;background:#f3f5f7;padding:12px 0;z-index:2}input,select{font:inherit;border:1px solid #c4cfd4;border-radius:9px;padding:10px;background:white}input{min-width:270px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.card{background:white;border-radius:16px;padding:20px;box-shadow:0 3px 12px #172a3508;min-width:0}.cardhead{display:flex;justify-content:space-between;align-items:center}.badge{font-size:12px;background:#fff2cf;color:#80550e;border-radius:30px;padding:4px 10px}.hold{border:2px solid #b94c4c}.hold .badge{background:#ffe5e5;color:#9b2929}.gallery{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:10px}figure{margin:0;min-width:100%;scroll-snap-align:start}img{width:100%;aspect-ratio:1;object-fit:contain;background:#f8f8f8;border-radius:10px}figcaption{word-break:break-all}.title{font-weight:600;min-height:52px}.facts{font-size:13px;background:#f4f7f7;padding:12px;border-radius:8px}.facts b{display:inline-block;min-width:40px}summary{cursor:pointer;color:#275d60}details{font-size:13px}.issue{font-size:12px;border-left:3px solid #d5a34f;padding-left:10px;color:#835d24;margin-top:18px}.unknown{max-width:360px}footer{padding:24px 0;color:#667782;font-size:13px}@media(max-width:1050px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){main{padding:18px 14px}.grid{grid-template-columns:1fr}header{padding:22px}h1{font-size:25px}.panel{overflow-x:auto}}
</style><main><header><h1>秋冬加绒棉鞋 · 上品准备</h1><p>按款 ¥71.50 / ¥72.90 / ¥74.90 · 沿旧店包邮（偏远地区例外）</p><p>资料核对日 2026-10-15。本页为内部执行记录，按实际回读区分后台上架、仓库、待核与排除。</p></header><section class="stats"><div><strong>18</strong>明确款号</div><div><strong>32</strong>颜色版本</div><div><strong>36</strong>原始图片</div><div><strong>{submitted_count}</strong>本轮已建商品</div><div><strong>{on_sale_count}</strong>后台上架且审核通过</div></section><section class="panel"><h2>先看有依据的需求</h2><p>电商罗盘 · 鞋靴 · 热度高 · 2026/10/07—10/13。以下为行业区间，不是本店预测。</p><table><tr><th>词</th><th>搜索人数</th><th>搜索用户支付金额</th><th>商品点击率</th></tr><tr><td>棉鞋</td><td>5万—7.5万</td><td>10万—25万元</td><td>50%—55%</td></tr><tr><td>冬天保暖鞋</td><td>1万—2.5万</td><td>7.5万—10万元</td><td>55%—60%</td></tr></table><p>“加绒”当前榜单筛选无结果，可按实物作描述词，不能编造流量。品牌热词、免弯腰、防水、医疗效果不因有流量就采用。</p></section><section class="panel"><h2>当前执行范围与待办</h2><p>用户已确认供货，库存按存量基线100/码、次日发准备，三包90天寄修。独立HTTP创建、编辑、审核及回读已跑通；46/47按负责人确认的标准码补齐。其余旧链接含跨货号加绒SKU，需先整理身份，不重复销售。</p><p>AA188无授权已排除销售；另有一张无货号白鞋。图片编辑服务连接失败，本页仍使用原图，并列出每款修改要求。</p></section><nav><input id="search" placeholder="按货号找款式，例如 M889" aria-label="搜索货号"><select id="state" aria-label="筛选状态"><option value="all">全部款式</option><option value="published">审核通过 / 上架</option><option value="warehouse">新建后转仓库</option><option value="draft">可继续准备</option><option value="hold">专项核查 / 已排除</option></select><span id="count"></span></nav><section class="grid">''' + ''.join(cards) + '''</section><section class="panel" style="margin-top:24px"><h2>无货号白鞋 · 暂不归入M889</h2><div class="unknown">''' + unknown + '''</div></section><footer>原始包与真实产品身份共用；图片未改造实物，不以生成图证明参数。审核页可筛货号和状态，逐款横向滚动查看原图。</footer></main><script>const s=document.querySelector('#search'),f=document.querySelector('#state'),cards=[...document.querySelectorAll('.card')];function filter(){let n=0;for(const c of cards){const show=c.dataset.key.toLowerCase().includes(s.value.trim().toLowerCase())&&(f.value==='all'||c.dataset.state===f.value);c.hidden=!show;if(show)n++}document.querySelector('#count').textContent='显示 '+n+' 款'}s.addEventListener('input',filter);f.addEventListener('change',filter);filter();</script></html>'''
    document = document.replace('<strong>32</strong>颜色版本', '<strong>33</strong>颜色版本')
    document = document.replace('{submitted_count}', str(submitted)).replace('{on_sale_count}', str(on_sale))
    document = document.replace('独立HTTP创建、编辑、审核及回读已跑通；46/47按负责人确认的标准码补齐。其余旧链接含跨货号加绒SKU，需先整理身份，不重复销售。', '731本轮暂缓；其他款的加绒版材料、同款身份及创建接口仍待核。其余可售款尺码已补工厂来源，9002/9507/2116为38—47码。')
    document = document.replace('另有一张无货号白鞋。', '米白鞋已哈希确认属于M889-1。')
    old_unknown = '<section class="panel" style="margin-top:24px"><h2>无货号白鞋 · 暂不归入M889</h2><div class="unknown">' + unknown + '</div></section>'
    document = document.replace(old_unknown, unknown_section)
    dest = business/'.local/棉鞋上品准备.html'
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp = dest.with_name(dest.name + '.tasktmp')
    temp.write_text(document,encoding='utf-8')
    temp.replace(dest)
    return dest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    print(build(args.workspace))
