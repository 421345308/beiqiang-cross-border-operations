"""Build a local, image-embedded review from the Douyin batch record. No HTTP writes."""
import argparse
import base64
import html
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
    cards = []
    for style in batch['styles']:
        model = style['source_model']
        hold = style['stage'].startswith(('HOLD_', 'EXCLUDED_'))
        badge = {'HOLD_USER_SKIP': '本轮暂缓', 'HOLD_BRAND': '品牌待核', 'EXCLUDED_NO_BRAND_AUTH': '无授权 · 已排除', 'HOLD_EXISTING_LISTING': '既有商品待核'}.get(style['stage'], '本地草稿')
        size = style['source_size_range']
        size_text = f'{size[0]}—{size[-1]}（当前工厂来源范围）' if size else '工厂店未找到该款，待补来源'
        notes = '；'.join(style['blocking_notes']) or '类目、材料及完整字段仍待核验；尚未提交'
        title = style['title_draft'] or '无品牌授权，已排除销售'
        price_text = f"¥{style['price']:.2f}/双" if style['price'] is not None else '不销售'
        stock_text = '按存量基线100/码准备 · 次日发' if style['stock'] is not None else '不填报'
        source = style.get('current_source_primary') or style.get('current_source') or {}
        source_url = source.get('url', '')
        source_link = f'<p class="muted">工厂来源：<a href="{esc(source_url)}" target="_blank" rel="noreferrer">{esc(source.get("source_model") or source.get("model") or model)}</a> · 核对日2026-10-15</p>' if source_url else '<p class="muted">工厂原页待补</p>'
        cards.append(f'''<article class="card {'hold' if hold else ''}" data-key="{esc(model)}" data-state="{'hold' if hold else 'draft'}">
<div class="cardhead"><h2>{esc(model)}</h2><span class="badge">{esc(badge)}</span></div>
<p class="muted">{esc(style['product_ref'] or '原货号保留 · 身份待绑定')} · {esc(style['structure'])}</p>
{source_link}
<div class="gallery">{''.join(image_tag(i['name'], model) for i in style['images'])}</div>
<p class="caption">原包候选图 · 尚未生成优化图</p>
<h3>标题草稿</h3><p class="title">{esc(title)}</p>
<div class="facts"><p><b>售价</b> {esc(price_text)}</p><p><b>颜色</b> {esc(' / '.join(c['name'] for c in style['colors']))}</p><p><b>尺码</b> {esc(size_text)}</p><p><b>库存</b> {esc(stock_text)}</p></div>
<details><summary>主图与详情安排</summary><p>{esc(style['visual_plan'])}</p><p>核心词：棉鞋。描述词：{esc('、'.join(style['keywords']['descriptive']))}。未取得这些长尾词的独立精确流量。</p><p>图序：完整鞋型 → 可选颜色 → 已有真实绒里/鞋底细节 → 核准尺码。缺少的实物角度保留缺口。</p></details>
<details><summary>详情文字草稿</summary>{''.join('<p>'+esc(line)+'</p>' for line in (style['detail_draft'] or ['该款已排除销售']))}</details>
<p class="issue">{esc(notes)}</p></article>''')
    unknown = ''.join(image_tag(name, '无货号白鞋') for name in batch['unknown_images'])
    unknown_section = ('<section class="panel" style="margin-top:24px"><h2>未归款图片</h2><div class="unknown">'+unknown+'</div></section>') if unknown else '<section class="panel" style="margin-top:24px"><h2>米白款已确认</h2><p>原无货号白鞋与工厂M889-1米白加绒主图SHA256完全一致，已归入M889家族；保留-1来源版本。</p></section>'
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>棉鞋上品准备 · 贝强</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:#172a35;font-family:"Microsoft YaHei",sans-serif;line-height:1.6}main{max-width:1440px;margin:auto;padding:36px 28px}header{background:#173f41;color:white;padding:30px;border-radius:18px}h1{margin:0 0 12px;font-size:30px}h2{margin:0;font-size:23px}h3{font-size:15px;margin:20px 0 6px}p{margin:8px 0}.muted,.caption,figcaption{color:#667782;font-size:12px}.stats{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}.stats div{background:white;border-radius:12px;padding:16px 24px;min-width:160px}.stats strong{display:block;font-size:28px}.panel{background:white;border-radius:14px;padding:22px;margin-bottom:22px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px;text-align:left;border-bottom:1px solid #e5e9ec}nav{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0;position:sticky;top:0;background:#f3f5f7;padding:12px 0;z-index:2}input,select{font:inherit;border:1px solid #c4cfd4;border-radius:9px;padding:10px;background:white}input{min-width:270px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.card{background:white;border-radius:16px;padding:20px;box-shadow:0 3px 12px #172a3508;min-width:0}.cardhead{display:flex;justify-content:space-between;align-items:center}.badge{font-size:12px;background:#fff2cf;color:#80550e;border-radius:30px;padding:4px 10px}.hold{border:2px solid #b94c4c}.hold .badge{background:#ffe5e5;color:#9b2929}.gallery{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:10px}figure{margin:0;min-width:100%;scroll-snap-align:start}img{width:100%;aspect-ratio:1;object-fit:contain;background:#f8f8f8;border-radius:10px}figcaption{word-break:break-all}.title{font-weight:600;min-height:52px}.facts{font-size:13px;background:#f4f7f7;padding:12px;border-radius:8px}.facts b{display:inline-block;min-width:40px}summary{cursor:pointer;color:#275d60}details{font-size:13px}.issue{font-size:12px;border-left:3px solid #d5a34f;padding-left:10px;color:#835d24;margin-top:18px}.unknown{max-width:360px}footer{padding:24px 0;color:#667782;font-size:13px}@media(max-width:1050px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){main{padding:18px 14px}.grid{grid-template-columns:1fr}header{padding:22px}h1{font-size:25px}.panel{overflow-x:auto}}
</style><main><header><h1>秋冬加绒棉鞋 · 上品准备</h1><p>按款 ¥71.50 / ¥72.90 / ¥74.90 · 沿旧店包邮（偏远地区例外）</p><p>资料核对日 2026-10-15。本页是内部审核稿，尚未提交或发布商品。</p></header><section class="stats"><div><strong>18</strong>明确款号</div><div><strong>32</strong>颜色版本</div><div><strong>36</strong>原始图片</div><div><strong>0</strong>本批已提交商品</div></section><section class="panel"><h2>先看有依据的需求</h2><p>电商罗盘 · 鞋靴 · 热度高 · 2026/10/07—10/13。以下为行业区间，不是本店预测。</p><table><tr><th>词</th><th>搜索人数</th><th>搜索用户支付金额</th><th>商品点击率</th></tr><tr><td>棉鞋</td><td>5万—7.5万</td><td>10万—25万元</td><td>50%—55%</td></tr><tr><td>冬天保暖鞋</td><td>1万—2.5万</td><td>7.5万—10万元</td><td>55%—60%</td></tr></table><p>“加绒”当前榜单筛选无结果，可按实物作描述词，不能编造流量。品牌热词、免弯腰、防水、医疗效果不因有流量就采用。</p></section><section class="panel"><h2>正式上架前的缺口</h2><p>用户已确认供货，库存按存量基线100/码、次日发准备，三包90天寄修。四款配码来源、逐款材料、同款身份及创建接口仍待核。</p><p>AA188无授权已排除销售；另有一张无货号白鞋。图片编辑服务连接失败，本页仍使用原图，并列出每款修改要求。</p></section><nav><input id="search" placeholder="按货号找款式，例如 M889" aria-label="搜索货号"><select id="state" aria-label="筛选状态"><option value="all">全部款式</option><option value="draft">可继续准备</option><option value="hold">专项核查 / 已排除</option></select><span id="count"></span></nav><section class="grid">''' + ''.join(cards) + '''</section><section class="panel" style="margin-top:24px"><h2>无货号白鞋 · 暂不归入M889</h2><div class="unknown">''' + unknown + '''</div></section><footer>原始包与真实产品身份共用；图片未改造实物，不以生成图证明参数。审核页可筛货号和状态，逐款横向滚动查看原图。</footer></main><script>const s=document.querySelector('#search'),f=document.querySelector('#state'),cards=[...document.querySelectorAll('.card')];function filter(){let n=0;for(const c of cards){const show=c.dataset.key.toLowerCase().includes(s.value.trim().toLowerCase())&&(f.value==='all'||c.dataset.state===f.value);c.hidden=!show;if(show)n++}document.querySelector('#count').textContent='显示 '+n+' 款'}s.addEventListener('input',filter);f.addEventListener('change',filter);filter();</script></html>'''
    document = document.replace('<strong>32</strong>颜色版本', '<strong>33</strong>颜色版本')
    document = document.replace('四款配码来源、逐款材料、同款身份及创建接口仍待核。', '731本轮暂缓；其他款的加绒版材料、同款身份及创建接口仍待核。其余可售款尺码已补工厂来源，9002/9507/2116为38—47码。')
    document = document.replace('另有一张无货号白鞋。', '米白鞋已哈希确认属于M889-1。')
    old_unknown = '<section class="panel" style="margin-top:24px"><h2>无货号白鞋 · 暂不归入M889</h2><div class="unknown">' + unknown + '</div></section>'
    document = document.replace(old_unknown, unknown_section)
    dest = business/'.local/棉鞋上品准备.html'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(document,encoding='utf-8')
    return dest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    print(build(args.workspace))
