"""Business objects read their original files; artifact bodies remain files."""
from __future__ import annotations
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime,timezone
from urllib.parse import urlencode,urlsplit
from uuid import uuid4
from website_inquiries import WebsiteInquiries,URL as WEBSITE_URL
from connectors.alibaba.customer_source import AlibabaCustomerSource

PRODUCTS='00_总控台/产品中心/数据/产品.json'
SUPPLY='00_总控台/产品中心/数据/供应来源.json'
ASSETS='00_总控台/产品中心/数据/素材索引.json'
CHANNEL='02_Alibaba运营/05_扩品工程/数据/国际站商品.json'
CRM='04_客户开发/04_发送与跟进记录/客户开发跟进表_20260802.csv'
SKIP={'node_modules','outputs','_build','build','dist','cache','__pycache__','backups'}
SOURCE_STATES={'ADOPTED':'已采纳供货来源','RAW_PACKAGE':'已有原始数据包','MAPPED':'已建立来源对应','MISSING':'来源缺失，待补证','CANDIDATE':'候选来源，尚未采纳','HOLD_SOURCE':'来源待核实，暂停承诺'}

def _now():return datetime.now(timezone.utc).isoformat()
def _stable(value):return hashlib.sha256(value.encode('utf8')).hexdigest()[:20]
def _clean(value):return re.sub(r'\s+',' ',str(value)).strip()
def _fact(label,value):return {'label':label,'value':value}
def _object(oid,kind,title,source,subtitle='',summary='',content=''):
    return {'id':oid,'kind':kind,'title':title,'subtitle':subtitle,'source':source,'summary':summary,
            'facts':[],'assets':[],'links':[],'related':[],'content':content}

class Business:
    def __init__(self,app):
        self.app=app;self.root=Path(app.root).resolve();self.website=getattr(app,'website_inquiries',None) or WebsiteInquiries(self.root)
        self.alibaba=getattr(app,'alibaba_customers',None) or AlibabaCustomerSource(self.root)
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS business_artifacts (id TEXT PRIMARY KEY, object_id TEXT NOT NULL, title TEXT NOT NULL, path TEXT NOT NULL, updated_at TEXT NOT NULL)')
            app.db.commit()

    def _json(self,path,key):
        file=self.root/path
        if not file.is_file():return []
        data=json.loads(file.read_text(encoding='utf-8-sig'))
        rows=data.get(key,[])
        if not isinstance(rows,list):raise ValueError('业务原档结构发生变化：'+path)
        return rows

    def _products(self):
        sources={r['id']:r for r in self._json(SUPPLY,'sources')}
        assets=self._json(ASSETS,'files');asset_map={}
        for asset in assets:
            for pid in asset.get('products',[]):asset_map.setdefault(pid,[]).append(asset)
        channel_map={}
        for row in self._json(CHANNEL,'listings'):channel_map.setdefault(row.get('product_id'),[]).append(row)
        result=[]
        for product in self._json(PRODUCTS,'products'):
            pid=product.get('id')
            if not isinstance(pid,str) or not pid:continue
            listings=channel_map.get(pid,[])
            adopted=bool(product.get('adopted_source_id'))
            source=sources.get(product.get('adopted_source_id') or product.get('reference_source_id'),{})
            state_label=SOURCE_STATES.get(product.get('source_state'),product.get('source_state') or '尚未记录')
            first=listings[0] if listings else {};fields=first.get('current_platform_fields') or {}
            title=fields.get('title') or (first.get('catalog_fields') or {}).get('title') or ''
            obj=_object('product:'+pid,'product',pid,PRODUCTS,subtitle=title or state_label,
                summary=' · '.join(str(v) for v in [state_label,source.get('supplier'),source.get('model')] if v))
            obj['facts']=[_fact('共用产品ID',pid),_fact('来源状态',state_label),_fact('别名',product.get('aliases',[])),
                _fact('原始资料包',product.get('raw_packages') or '原档未列出原包路径')]
            mode=product.get('supply_mode')
            if mode:obj['facts'].append(_fact('供货模式（原记录）',mode))
            classification=product.get('classification') or {}
            if classification.get('local_intent_candidates'):obj['facts'].append(_fact('用途候选（非逐款能力结论）',classification['local_intent_candidates']))
            specifications={k:product[k] for k in ('specifications','materials','material','sizes','size_range','colors') if product.get(k)}
            if specifications:obj['facts'].append(_fact('原档已有规格',specifications))
            if source:
                obj['facts'] += [_fact('已采纳供应来源' if adopted else '历史参考来源（非采购承诺）',source.get('id')),_fact('供应商',source.get('supplier','未记录')),
                    _fact('供应商原款',source.get('model','未记录')),_fact('历史参考价',{'price':source.get('price'),'currency':source.get('currency'),'observed_at':source.get('observed_at'),'basis':source.get('price_basis')})]
                if str(source.get('url','')).startswith('https://'):obj['links'].append({'label':'原供货来源','url':source['url']})
            for listing in listings:
                current=listing.get('current_platform_fields') or {};historic=listing.get('catalog_fields') or {}
                status={'approved':'已审核','modified':'修改审核中','pending':'待审核','published':'已发布'}.get(current.get('status'),current.get('status') or '未记录审核状态')
                obj['facts'].append(_fact('Alibaba '+str(listing.get('id')),' · '.join(str(v) for v in [current.get('title') or historic.get('title'),status,current.get('at')] if v)))
                url=current.get('url') or listing.get('url')
                if isinstance(url,str) and url.startswith('https://'):obj['links'].append({'label':'Alibaba '+str(listing.get('id')),'url':url})
            for asset in asset_map.get(pid,[]):
                relative=asset.get('file','')
                if not isinstance(relative,str):continue
                parts=Path(relative.replace('\\','/')).parts
                if not relative.startswith('01_产品资产/') or '..' in parts or any(p.startswith('.') for p in parts):continue
                if Path(relative).suffix.lower() not in ('.jpg','.jpeg','.png','.webp','.gif','.mp4','.webm','.mp3','.wav'):continue
                obj['assets'].append({'path':relative,'label':' / '.join(asset.get('roles',[])) or Path(relative).name,
                    'url':'/api/media/file?'+urlencode({'path':relative})})
            # Agent context is a useful brief, not hundreds of transport receipts.
            evidence=[p for p in product.get('evidence',[]) if isinstance(p,str)]
            evidence.sort(key=lambda p:(bool(re.search(r'receipt|verification|after_get|after_render|update_once',p,re.I)),not bool(re.search(r'facts|事实|原包|规格|计划|copy',p,re.I))))
            local=product.get('local_assets') or {}
            selected=[p for p in [local.get('current_fields_file'),local.get('current_buyer_copy'),local.get('current_assortment')]+evidence if isinstance(p,str)]
            selected=list(dict.fromkeys(selected))[:8]
            core={k:product[k] for k in ('id','aliases','source_state','raw_packages','notes','supply_mode') if k in product}
            core['source_state_label']=state_label;core['classification']=classification;core['existing_specifications']=specifications
            source_core={k:source[k] for k in ('id','supplier','model','url','price','currency','observed_at','price_terms') if k in source}
            channel_core=[{'id':v.get('id'),'url':v.get('url'),'current':{k:v.get('current_platform_fields',{}).get(k) for k in ('title','status','at','price_tiers')},'historical_title':v.get('catalog_fields',{}).get('title')} for v in listings]
            obj['content']=json.dumps({'product':core,'source_role':'已采纳' if adopted else '历史参考，非新增供货承诺',
                'supply_source':source_core,'selected_evidence_paths':selected,'channel_listings':channel_core,
                'full_index':PRODUCTS,'boundary':'标题/用途候选不是材料、功能、自有工厂或供货承诺的证明。完整回执按原档路径查阅。'},ensure_ascii=False,indent=2)
            result.append(obj)
        return result

    def _documents(self,relative,max_depth=2):
        base=self.root/relative
        if not base.is_dir():return []
        found=[]
        for current,dirs,files in os.walk(base,followlinks=False):
            depth=len(Path(current).relative_to(base).parts)
            dirs[:]=sorted(d for d in dirs if not d.startswith('.') and d not in SKIP and depth<max_depth)
            for name in sorted(files):
                path=Path(current)/name
                if name.endswith('.md') and not name.startswith('.') and path.resolve().is_relative_to(base.resolve()):found.append(path)
                if len(found)>=100:return found
        return found

    def _customers(self):
        customers={}
        def add(name,source,values,content='',subtitle='本地客户记录'):
            name=_clean(name).strip('`* ')
            if not name or name in ('示例公司','Example Company','示例','测试公司'):return None
            oid='customer:'+_stable(name.casefold())
            if oid not in customers:customers[oid]=_object(oid,'customer',name,source,subtitle=subtitle)
            obj=customers[oid]
            obj['facts'].append(_fact('原记录来源',source))
            obj['facts'] += [_fact(k,v) for k,v in values.items() if v not in ('',None)]
            for value in values.values():
                if isinstance(value,str) and value.startswith('https://'):obj['links'].append({'label':'原记录链接','url':value})
            if content:obj['content']+=('\n\n' if obj['content'] else '')+content
            if not obj['summary']:obj['summary']=_clean(str(values.get('Next_Action') or values.get('下一动作') or values.get('状态') or values.get('Reply_Status') or ''))
            return obj
        path=self.root/CRM
        if path.is_file():
            with path.open(encoding='utf-8-sig',newline='') as stream:
                for row in csv.DictReader(stream):add(row.get('Company',''),CRM,row,json.dumps(row,ensure_ascii=False,indent=2))
        # Only explicit account/company tables; no prose/name guessing.
        for path in self._documents('04_客户开发/01_线索与CRM',max_depth=1):
            content=path.read_text(encoding='utf-8-sig');lines=content.splitlines();headers=None;index=None
            for line in lines:
                if not line.startswith('|'):headers=None;index=None;continue
                cells=[c.strip() for c in re.split(r'(?<!\\)\|',line.strip().strip('|'))]
                if all(re.fullmatch(r'[:\- ]+',c or ' ') for c in cells):continue
                if headers is None:
                    headers=cells;index=next((i for i,k in enumerate(headers) if k in ('账户','公司','Company','客户公司','买家公司')),None);continue
                if index is not None and len(cells)==len(headers):
                    row=dict(zip(headers,cells));source=path.relative_to(self.root).as_posix()
                    add(cells[index],source,row,'来源：'+source+'\n'+json.dumps(row,ensure_ascii=False,indent=2),subtitle='本地CRM研究/跟进记录（不代表采购意向）')
        for path in self._documents('04_客户开发/05_客户项目',max_depth=3):
            source=path.relative_to(self.root).as_posix();relative=path.relative_to(self.root/'04_客户开发/05_客户项目')
            if len(relative.parts)<2:continue
            # Nested 报价/方案 folders belong to the same customer project.
            # 历史客户资料 is a container, not a customer identity.
            folder=relative.parts[1] if relative.parts[0]=='历史客户资料' and len(relative.parts)>=3 else relative.parts[0]
            if folder.startswith(('_','.')):continue
            name=re.sub(r'[_ -]+BQ[-_]?\d+.*$','',folder,flags=re.I)
            content=path.read_text(encoding='utf-8-sig')
            add(name,source,{'原项目':relative.parent.as_posix()},content,subtitle='本地客户项目原档')
        return list(customers.values())

    def _website_objects(self):
        result=[]
        for row in self.website.records():
            reference=row['reference']
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',reference):continue
            requirements=str(row.get('requirements') or '')
            summary=requirements if len(requirements)<=240 else requirements[:239]+'…'
            obj=_object('customer:website-'+reference,'customer',row.get('company') or row.get('name') or reference,
                '网站记录 · '+reference,subtitle='网站记录 · '+str(row.get('country') or ''),summary=summary,
                content=json.dumps(row,ensure_ascii=False,indent=2))
            labels={'name':'联系人','company':'公司','country':'国家/地区','email':'邮箱','quantity':'采购数量','status':'处理状态','receivedAt':'收到时间'}
            statuses={'new':'待处理','open':'处理中','handled':'已处理','closed':'已关闭','pending':'待处理','replied':'已回复'}
            obj['facts']=[_fact('来源','网站原始记录'),_fact('记录编号',reference)]+[
                _fact(label,statuses.get(row[k],row[k]) if k=='status' else row[k]) for k,label in labels.items() if row.get(k) not in ('',None)]
            obj['links']=[{'label':'网站私有后台','url':'https://www.beiqiang.online/admin/workbench/'}]
            result.append(obj)
        return result

    def _alibaba_objects(self):
        result=[]
        for row in self.alibaba.records():
            obj=_object('customer:'+row['id'],'customer',row.get('name') or '国际站订单买家',
                '国际站订单接口',subtitle='国际站 · 订单买家',summary='已读取订单 '+str(len(row['orders']))+' 笔；订单记录不代表新询盘。',
                content=json.dumps(row,ensure_ascii=False,indent=2))
            obj['source_type']='alibaba_order_buyer'
            obj['facts']=[_fact('来源','国际站订单买家'),_fact('国家/地区',row.get('country') or '原记录未提供'),
                _fact('读取时间',row.get('observed_at'))]
            obj['facts'] += [_fact('订单 '+o['id'],o.get('status') or '原记录未提供') for o in row['orders']]
            result.append(obj)
        return result

    def _prospect_objects(self):
        workspace=getattr(self.app,'customer_workspace',None)
        if not workspace:return []
        result=[]
        for row in workspace.list_discovery():
            obj=_object('prospect:'+row['id'],'prospect',row['title'],row.get('source') or '本地客户开发研究',
                subtitle='开发研究任务' if row['kind']=='research_task' else '主动开发候选',summary=row.get('next_action') or row.get('target') or '',
                content=json.dumps(row,ensure_ascii=False,indent=2))
            obj['source_type']='outbound_research';obj['original_text']=row.get('notes') or row.get('target') or ''
            obj['facts']=[_fact('研究目标',row.get('target') or '待明确'),_fact('当前状态',row.get('status') or '待研究')]
            if row.get('website'):obj['links']=[{'label':'企业官网','url':row['website']}]
            result.append(obj)
        return result

    def _intake_objects(self):
        intake=getattr(self.app,'inquiry_intake',None)
        if not intake:return []
        result=[]
        for row in intake.list_records():
            channel={'alibaba':'国际站','email':'邮件','other':'其他渠道'}.get(row['channel'],'其他渠道')
            obj=_object('customer:intake:'+row['id'],'customer',row.get('company') or row.get('contact_name') or '待确认客户',
                channel+'原文录入',subtitle=channel+' · 原文录入',summary=row['original_text'][:200],content=json.dumps(row,ensure_ascii=False,indent=2))
            obj['source_type']='manual_import';obj['original_text']=row['original_text']
            obj['facts']=[_fact('记录来源',channel+'原文录入'),_fact('接收日期',row.get('received_at') or '未提供')]
            result.append(obj)
        return result

    def list_objects(self,kind='',q=''):
        if kind not in ('','product','customer','prospect') or not isinstance(q,str):raise ValueError('业务查询参数无效')
        objects=(self._products() if kind in ('','product') else [])+(self._customers()+self._website_objects()+self._alibaba_objects()+self._intake_objects() if kind in ('','customer') else [])+(self._prospect_objects() if kind in ('','prospect') else [])
        query=q.strip().casefold()
        if query:objects=[o for o in objects if query in json.dumps(o,ensure_ascii=False).casefold()]
        # List stays compact; detail and Agent context use get_object.
        return [{**{k:o[k] for k in ('id','kind','title','subtitle','source','summary')},'source_type':o.get('source_type') or ('website' if o['id'].startswith('customer:website-') else 'local'),'assets':o['assets'][:1], 'facts':[f for f in o['facts'] if f['label'].startswith('用途候选')] if o['kind']=='product' else []} for o in objects]

    def get_object(self,object_id):
        if not isinstance(object_id,str):raise ValueError('业务对象ID无效')
        if object_id.startswith('product:'):objects=self._products()
        elif object_id.startswith('customer:website-'):objects=self._website_objects()
        elif object_id.startswith('customer:alibaba-order-buyer:'):objects=self._alibaba_objects()
        elif object_id.startswith('customer:intake:'):objects=self._intake_objects()
        elif object_id.startswith('prospect:'):objects=self._prospect_objects()
        elif object_id.startswith('customer:'):objects=self._customers()
        else:raise ValueError('未知业务对象类型')
        item=next((o for o in objects if o['id']==object_id),None)
        if item is None:raise ValueError('业务对象不存在或原来源暂未读取')
        return item

    def website_status(self):return self.website.status()
    def refresh_website(self,wait=False):return self.website.refresh(wait=wait)

    def _artifact_base(self,object_id):
        obj=self.get_object(object_id)
        if object_id.startswith('customer:website-'):
            reference=object_id.removeprefix('customer:website-')
            return self.root/'04_客户开发/.local/网站询盘'/reference
        folder='00_总控台/产品中心' if obj['kind']=='product' else '04_客户开发'
        return self.root/folder/'.local/成果'/_stable(object_id)

    def _artifact(self,row):
        oid,object_id,title,relative,at=row
        path=self.root/relative
        if not path.resolve().is_relative_to(self.root) or '.local' not in path.parts:raise ValueError('成果路径不在本地业务范围')
        return {'id':oid,'object_id':object_id,'title':title,'content':path.read_text(encoding='utf8'),
                'path':relative,'updated_at':at}

    def list_artifacts(self,object_id=None):
        with self.app.lock:
            rows=self.app.db.execute('SELECT id,object_id,title,path,updated_at FROM business_artifacts'+(' WHERE object_id=?' if object_id is not None else '')+' ORDER BY updated_at DESC',(object_id,) if object_id is not None else ()).fetchall()
        return [self._artifact(row) for row in rows]

    def save_artifact(self,object_id,title,content,artifact_id=None):
        if not isinstance(title,str) or not title.strip() or len(title)>200 or not isinstance(content,str) or len(content)>200000:raise ValueError('成果标题或正文无效')
        base=self._artifact_base(object_id)
        if artifact_id is not None and not re.fullmatch(r'[0-9a-f]{32}',str(artifact_id)):raise ValueError('成果ID无效')
        oid=artifact_id or uuid4().hex
        with self.app.lock:
            previous=self.app.db.execute('SELECT object_id,path FROM business_artifacts WHERE id=?',(oid,)).fetchone()
            if artifact_id and (not previous or previous[0]!=object_id):raise ValueError('成果不属于这个业务对象')
            if not base.resolve().is_relative_to(self.root):raise ValueError('成果目录超出原业务范围')
            private=next(p for p in (base,*base.parents) if p.name=='.local')
            private.mkdir(parents=True,exist_ok=True,mode=0o700)
            cursor=private
            for part in base.relative_to(private).parts:
                cursor=cursor/part;cursor.mkdir(exist_ok=True,mode=0o700)
            target=base/(oid+'.md')
            if target.is_symlink():raise ValueError('成果文件不能是链接')
            if target.exists():
                previous_path=target.with_suffix('.prev.md')
                if previous_path.is_symlink():raise ValueError('成果备份不能是链接')
                previous_fd,previous_name=tempfile.mkstemp(prefix='.previous-',dir=base)
                try:
                    with os.fdopen(previous_fd,'wb') as stream:stream.write(target.read_bytes());stream.flush();os.fsync(stream.fileno())
                    os.replace(previous_name,previous_path)
                finally:
                    if os.path.exists(previous_name):os.unlink(previous_name)
            fd,name=tempfile.mkstemp(prefix='.artifact-',dir=base)
            try:
                with os.fdopen(fd,'w',encoding='utf8',newline='\n') as stream:stream.write(content);stream.flush();os.fsync(stream.fileno())
                os.replace(name,target)
            finally:
                if os.path.exists(name):os.unlink(name)
            relative=target.relative_to(self.root).as_posix();at=_now()
            self.app.db.execute('INSERT OR REPLACE INTO business_artifacts VALUES (?,?,?,?,?)',(oid,object_id,title.strip(),relative,at));self.app.db.commit()
        return {'id':oid,'object_id':object_id,'title':title.strip(),'content':content,'path':relative,'updated_at':at}
