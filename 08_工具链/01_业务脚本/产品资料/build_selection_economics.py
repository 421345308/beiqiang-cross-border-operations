"""Generate a local-only economic comparison from canonical costs and readbacks.

No pricing mutations. Supplier public prices are reference prices, not agreed
procurement costs. Scenario inputs are deliberately separate from source facts.
"""
import csv
import json
import re
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / '00_总控台/产品中心/数据/.local/主推组合评估'
EVIDENCE = OUT / '2026-10-29'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def build():
    costs = read(ROOT / '00_总控台/产品中心/数据/.local/生产成本基线.json')['families']
    prices = {p['id']:p for p in read(ROOT / '02_Alibaba运营/01_店铺与全店诊断/价格复核.json')['products']}
    operations = {p['id']:p for p in read(ROOT / '02_Alibaba运营/01_店铺与全店诊断/经营复核.json')['products']}
    selected = read(ROOT / '04_客户开发/06_报价与产品册/国际B2B精选册/selection.json')['products']
    candidates = [(p['code'],p['id'],p['group']) for p in selected] + [
        ('BQ037','1601924347721','reserve'), ('BQ1044','1601943650718','reserve'),
        ('BQ-M858','1601969853888','reserve')]
    notes = {
        'BQ008':'首推：差异化轮廓；第41周有产品行询盘，须继续验证成交。',
        'BQ009':'首推：与BQ008形成相邻纺织系列；本链接无足够询盘样本。',
        'BQ031':'首推：宽鞋头、38-47码；经济空间优于低价针织组。',
        'BQ001':'款式补充：套脚；100双价留给费用的空间小，不作为低价投放主力。',
        'BQ003':'款式补充：针织系带；与BQ001同样需要先核完整订单费用。',
        'BQ1009':'条件补充：白色低帮、MOQ120；公开同款有价，只靠转售价差不足以说明价值。',
        'BQ-LQ2597':'条件补充：39-48码与拼接外观；外采报价及服务费用逐单确认。',
        'BQ-C2627':'条件补充：洞洞鞋需求才推荐；单位价差薄、包装体积会影响经济性。',
        'BQ037':'优先候补：已有询盘；产品中心当前无原包路径，标准/加绒版本须结合原图核对，补证后与BQ003比较。',
        'BQ1044':'候补：商务便鞋对应不同系列；有询盘，但不塞入第一版休闲主线。',
        'BQ-M858':'候补：季节与成本结构不同，等具体买家需求，不因外观扩大主业。'
    }
    rows=[]
    for code,pid,group in candidates:
        raw=read(EVIDENCE/f'{pid}-current.json')
        formal=raw['response']['product']
        tier_sets={json.dumps(s['bulk_discount_prices'],sort_keys=True) for s in formal['product_sku']['skus']}
        assert len(tier_sets)==1,(code,'SKU prices vary: use version-specific comparison')
        tiers=json.loads(tier_sets.pop())
        if code in costs:
            source_tiers=[[1,None,costs[code]['cost_cny']]]
            currency='CNY';source_at='2026-10-21';kind='负责人确认生产基线'
            source_ref='00_总控台/产品中心/数据/.local/生产成本基线.json';source_url=None
        else:
            old=prices[pid];quote=old['public_quote']
            source_url=old['source_url'];kind='供应商公开参考价'
            if code in ('BQ-LQ2597','BQ-C2627'):
                stem='LQ2597' if code=='BQ-LQ2597' else 'C2627'
                content=(EVIDENCE/f'{stem}-supplier.md').read_text('utf-8')
                value=re.search(r'价格：\s*(\d+(?:\.\d+)?)',content)[1]
                source_tiers=[[1,None,value]];source_at='2026-10-29';currency='CNY'
                source_ref=str((EVIDENCE/f'{stem}-supplier.json').relative_to(ROOT))
            elif code=='BQ1009':
                content=(EVIDENCE/'BQ1009-supplier.md').read_text('utf-8')
                a=re.search(r'US\$(\d+\.\d+)\s*\n120-599 pairs',content)[1]
                b=re.search(r'US\$(\d+\.\d+)\s*\n600\+ pairs',content)[1]
                source_tiers=[[120,599,a],[600,None,b]];source_at='2026-10-29';currency='USD'
                source_ref=str((EVIDENCE/'BQ1009-supplier.json').relative_to(ROOT))
            else:
                source_tiers=quote['tiers'];currency=quote['currency'];source_at=quote['at'][:10]
                source_ref=quote['evidence']
        rows.append({'code':code,'id':pid,'group':group,'tiers':tiers,'cost_tiers':source_tiers,
                     'cost_currency':currency,'cost_kind':kind,'cost_at':source_at,'cost_source':source_ref,
                     'source_url':source_url,'read_at':raw['at'],
                     'week41':operations.get(pid,{}).get('week41') or {},'decision':notes[code]})
    fx={'cny_per_usd':'6.6545','bank':'Bank of China','type':'USD spot buying / 100',
        'quoted_value_per_100_usd':'665.45','quote_time':'2026-10-28 23:48:46 Asia/Shanghai',
        'observed_on':'2026-10-29','url':'https://www.boc.cn/sourcedb/whpj/',
        'scope':'Settlement reference, not an executed exchange rate.'}
    (EVIDENCE/'fx-observation.json').write_text(json.dumps(fx,ensure_ascii=False,indent=2),encoding='utf-8')
    data={'generated_from':'Canonical production costs, official product.get readbacks and supplier observations',
          'as_of':'2026-10-29','fx':fx,'rows':rows}
    (OUT/'经济比较.local.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    csvrows=[]
    for row in rows:
        for tier in row['tiers']:
            qty=int(tier['start_quantity']);price=Decimal(tier['price']);cost_tier=next(
                (t for t in reversed(row['cost_tiers']) if qty >= (t[0] or 1) and (t[1] is None or qty <= t[1])),None)
            if not cost_tier:continue
            cost=Decimal(str(cost_tier[2]))*(Decimal(fx['cny_per_usd']) if row['cost_currency']=='USD' else 1)
            spread=price*Decimal(fx['cny_per_usd'])-cost
            csvrows.append({'款号':row['code'],'平台ID':row['id'],'数量起点':qty,'当前单价USD':str(price),
                '生产或采购参考CNY':str(cost),'未扣费用差额CNY':str(spread.quantize(Decimal('.01'))),
                '每双另计5元情景CNY':str((spread-5).quantize(Decimal('.01'))),
                '每双另计8元情景CNY':str((spread-8).quantize(Decimal('.01'))),
                '成本依据':row['cost_kind'],'依据日期':row['cost_at'],'用途':'非净利润，5/8元仅压力情景'})
    with (OUT/'经济比较.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(csvrows[0]));writer.writeheader();writer.writerows(csvrows)
    html=HTML.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/'))
    (OUT/'主推组合经济比较.html').write_text(html,encoding='utf-8')
    print(json.dumps({'candidates':len(rows),'tiers':len(csvrows),'html':str(OUT/'主推组合经济比较.html')},ensure_ascii=False))


HTML='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>主推组合经济比较 · 内部</title><style>
*{box-sizing:border-box}body{font:15px/1.65 "Segoe UI","Microsoft YaHei",sans-serif;margin:0;background:#f3f3ec;color:#203c35}main{max-width:1540px;margin:36px auto;padding:0 30px}h1{font-size:32px;margin-bottom:8px}h2{font-size:21px;margin-top:30px}.intro{max-width:1100px;color:#52635b}.banner{background:#163c33;color:white;padding:22px 25px;border-radius:12px;margin:24px 0}.inputs{display:flex;gap:20px;flex-wrap:wrap;background:white;padding:22px;border-radius:12px}label{display:block;font-size:13px}input{display:block;width:140px;font:inherit;padding:8px;border:1px solid #b4c0b6;border-radius:5px;margin-top:6px}button{font:inherit;border:1px solid #a9b5ac;background:#fff;border-radius:6px;padding:7px 14px;cursor:pointer;margin:12px 6px 8px 0}.scroll{overflow:auto;background:white;border-radius:10px}table{width:100%;min-width:1330px;border-collapse:collapse}th,td{padding:12px 10px;border-bottom:1px solid #e2e5de;text-align:right;vertical-align:top;font-size:13px}th{background:#e4ebe2;white-space:nowrap}td:first-child,th:first-child{text-align:left;min-width:220px}small{display:block;color:#65776c;font-size:11px}strong{font-size:15px}.bad{color:#ac3328}.good{color:#08744c}.notes{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.note{background:#fff;padding:18px;border-radius:9px}.note p{margin:6px 0;font-size:13px}a{color:#1b6d58}.formula{font:13px/1.8 Consolas,monospace;background:#e7eae1;padding:16px;white-space:normal}.muted{color:#67756b}.error{color:#aa2525}footer{padding:28px 0;font-size:12px;color:#52635b}@media print{.inputs,button{display:none}body{background:white}main{margin:0;padding:0}.scroll{overflow:visible}table{min-width:0}th,td{font-size:9px;padding:4px}.notes{display:block}}
</style><main><div class="muted">贝强 / 内部经营资料 / 2026-10-29</div><h1>先看订单空间，再决定主推力度</h1>
<p class="intro">11 款同条件比较，8 款进入首版精选册。生产基线来自负责人确认；外采价来自供应商公开页。下面的差额、压力情景与反推报价用于决策，均不是已确认净利润，也不会修改平台价格。</p>
<div class="banner">主推：BQ008 / BQ009 / BQ031。BQ001 / BQ003 提供款式选择；BQ1009 / LQ2597 / C2627 只在对应需求下补充。先把选款、费用与采购条件讲清，再决定价格和获客投入。</div>
<div class="inputs"><label>同一比较数量 / 双<input id="qty" type="number" min="1" step="1" value="100"></label>
<label>结汇参考 / CNY每USD<input id="fx" type="number" min="0.01" step="0.0001" value="6.6545"></label>
<label>另计订单费用 / CNY每双<input id="extra" type="number" min="0" step="0.1" value="0"></label>
<label>订单固定费用 / CNY<input id="fixed" type="number" min="0" step="1" value="0"></label>
<label>收款等比例费 / %<input id="fee" type="number" min="0" max="99" step="0.1" value="0"></label>
<label>目标贡献率情景 / %<input id="target" type="number" min="0" max="99" step="1" value="15"></label></div>
<p class="muted">费用初值为 0，表示尚未填入，不表示实际为零。将包装、卖方承担的运输、检验及样品摊销等填入对应栏，避免重复计算。15% 仅反推演示，不是已定经营标准。</p>
<button data-qty="100">比较100双</button><button data-qty="120">比较120双</button><button data-qty="600">比较600双</button>
<button data-extra="0">仅看基线差额</button><button data-extra="5">每双另计5元情景</button><button data-extra="8">每双另计8元情景</button><p id="error" class="error"></p>
<div class="scroll"><table><thead><tr><th>产品与选款角色</th><th>现价 USD/双</th><th>基线 CNY/双</th><th>未扣费用差额</th><th>情景贡献 CNY/双</th><th>情景贡献率</th><th>目标情景反推 USD/双</th><th>货品基线总额 CNY</th></tr></thead><tbody id="rows"></tbody></table></div>
<p class="muted">未达到该链接或供应价数量门槛时不生成结果；不把 600 双采购价配给 120 双订单。总额是货品基线投入，不是预付金额、现金峰值或含运费总价。税费、实际结算与付款节奏须按订单核算。</p>
<h2>每款为什么进或不进首版</h2><div class="notes" id="notes"></div>
<h2>比较口径与来源</h2><div class="formula">未扣费用差额 = 平台单价 × 汇率 − 生产/采购参考单价。<br>情景贡献 = 销售额 × (1 − 比例费率) − 货品基线 − 另计每双费用 − 固定费用 / 数量。<br>情景贡献率 = 情景贡献 / 销售额。<br>目标情景反推价 = (货品基线 + 另计每双费用 + 固定费用 / 数量) / [汇率 × (1 − 比例费率 − 目标贡献率)]。向上取美分；不是已授权的新售价。</div>
<p>汇率参考：中国银行美元现汇买入价 665.45 元/100 美元，页面时间 2026-10-28 23:48:46，10月29日读取。<a href="https://www.boc.cn/sourcedb/whpj/">汇率来源</a>；实际收款汇率另定。</p>
<p>询盘数据仅为第41周（10月11–17日，PST）商品行统计，不是独立买家数、订单或本次改版效果。供应商公开价不证明当前库存、实际成交价或最终供货条件。制造成本基线不含全部经营费用。</p>
<footer>唯一源：产品中心受控生产成本基线；国际站10月29日正式API回读；LQ2597、C2627、BQ1009供方页10月29日回读，其余候补沿10月21日来源。原始证据位于本目录2026-10-29子目录。此文件为可重建比较视图，输入仅用于当前浏览情景，不保存为新成本真相。生成工具：08_工具链/01_业务脚本/产品资料/build_selection_economics.py。</footer></main>
<script>const D=__DATA__;const $=id=>document.getElementById(id);const fmt=n=>Number(n).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2});const groups={core:'主推',alternative:'款式补充',complement:'条件补充',reserve:'候补'};
function tier(ts,q){return ts.filter(t=>q>=Number(t.start_quantity)).sort((a,b)=>b.start_quantity-a.start_quantity)[0]}
function update(){let q=+$('qty').value,fx=+$('fx').value,e=+$('extra').value,f=+$('fixed').value,fee=+$('fee').value/100,t=+$('target').value/100;
if(!Number.isInteger(q)||q<1||fx<=0||e<0||f<0||fee<0||t<0||fee+t>=1){$('error').textContent='请输入有效数量、汇率和费用；比例费与目标贡献率之和应小于100%。';$('rows').innerHTML='';return}$('error').textContent='';
$('rows').innerHTML=D.rows.map(r=>{let p=tier(r.tiers,q),ct=r.cost_tiers.find(z=>q>=(z[0]||1)&&(z[1]===null||q<=z[1]));let title=`<strong>${r.code}</strong><small>${groups[r.group]} · ${r.id}</small><small>${r.cost_kind} · ${r.cost_at}</small>`;
if(!p||!ct)return `<tr><td>${title}</td><td colspan="7">数量未满足参考门槛；平台起点 ${Math.min(...r.tiers.map(z=>z.start_quantity))} 双</td></tr>`;
let price=+p.price,cost=+ct[2]*(r.cost_currency==='USD'?fx:1),rev=price*fx,spread=rev-cost,con=rev*(1-fee)-cost-e-f/q,ratio=con/rev,quote=Math.ceil(((cost+e+f/q)/(fx*(1-fee-t))-1e-10)*100)/100;
return `<tr><td>${title}</td><td>${fmt(price)}</td><td>${fmt(cost)}</td><td>${fmt(spread)}</td><td class="${con<0?'bad':'good'}">${fmt(con)}</td><td>${fmt(ratio*100)}%</td><td>${fmt(quote)}</td><td>${fmt(cost*q)}</td></tr>`}).join('')}
$('notes').innerHTML=D.rows.map(r=>`<div class="note"><strong>${r.code}</strong><p>${r.decision}</p><small>第41周：${r.week41.search_clicks??'无'} 搜索点击 / ${r.week41.inquiries??'无'} 产品行询盘；不是订单数。</small>${r.source_url?`<a href="${r.source_url}">供应方来源</a>`:''}</div>`).join('');
document.querySelectorAll('input').forEach(x=>x.addEventListener('input',update));document.querySelectorAll('[data-qty]').forEach(b=>b.onclick=()=>{$('qty').value=b.dataset.qty;update()});document.querySelectorAll('[data-extra]').forEach(b=>b.onclick=()=>{$('extra').value=b.dataset.extra;update()});update();</script></html>'''


if __name__=='__main__':build()
