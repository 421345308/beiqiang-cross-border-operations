"""Render current per-shoe highlights; refer to the one general FAQ source.

Earlier copy.json objects remain unchanged as submission evidence. This
read-only renderer never publishes or upgrades their platform/source status.
"""
from pathlib import Path
from collections import defaultdict
import hashlib, json

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'02_Alibaba运营/02_单品优化记录/全店FAQ与产品亮点优化'

def main():
    registry=json.loads((ROOT/'02_Alibaba运营/05_扩品工程/数据/产品与链接台账.json').read_text('utf8'))
    links={x['id']:x for x in registry['listings']}
    general=json.loads((BASE/'通用FAQ与公司简介.json').read_text('utf8'))
    assert general['status']=='APPROVED_FOR_BATCH_REPLACEMENT'
    groups=defaultdict(list)
    for path in sorted((BASE/'商品').glob('*/copy.json')):
        c=json.loads(path.read_text('utf8'))
        signature=hashlib.sha256(c['highlights'].encode('utf8')).hexdigest()
        groups[(links[c['product_id']]['product_id'],signature)].append(c)
    rows=['# 实款商品亮点 · 当前审核入口','',
          '商品亮点按具体鞋款解释结构与选款价值。本页从逐ID亮点原稿生成，相同实款且亮点完全一致的链接合并展示；159条未闭环历史链接仍单列待修。','',
          '当前FAQ统一采用已认可的八问工厂合作问答，正文只维护在[通用FAQ与公司简介](通用FAQ与公司简介.json)，中英审核见[通用文案审核](通用文案审核.md)。逐ID替换与验收见[共享工厂详情](../../06_图片与检查记录/共享工厂详情/README.md)。','',
          '下列copy.json保留前次提交原稿，其中旧的单款FAQ仅供正式请求追溯；当前FAQ以通用正文及逐ID正式回读为准。亮点的前次执行状态见[当前执行](当前执行.json)。受保护源和五条离线重复链接只供本地审阅，仍按原范围排除。','']
    for (product_id,_),copies in sorted(groups.items()):
        c=copies[0]
        rows+=['## '+product_id+' · '+c['model'],'',
               '对应链接及亮点原稿：'+'、'.join('['+x['product_id']+'](商品/'+x['product_id']+'/copy.json)'for x in copies),'',
               '**产品亮点**','',c['highlights'],'']
    (BASE/'实款文案审核.md').write_text('\n'.join(rows)+'\n',encoding='utf8')
    print('CURRENT_HIGHLIGHT_REVIEW',len(groups),'blocks',sum(map(len,groups.values())),'exact links; one general FAQ source')

if __name__=='__main__':main()
