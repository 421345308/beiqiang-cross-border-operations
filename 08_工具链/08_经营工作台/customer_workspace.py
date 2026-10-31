"""Derived customer notes and a small research workspace; never sends messages.

Original customer/candidate records are read-only. JSON files own derived text;
SQLite contains identity/path indexes only. No model or network call here.
"""
from __future__ import annotations
import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

CANDIDATES='04_客户开发/02_目标名单/.local/客户发现助手/candidates.json'
SOURCE_FIELDS={'company','country','quantity','need','stage','contact_name','email','products','timeline','destination','budget','source_notes'}
ANALYSIS_FIELDS={'intent','fit','basis','missing','next_action','facts','inferences','needs','product_fit','recommendations','reply_draft','risks','questions'}
DISCOVERY_FIELDS={'title','target','company','website','market_hint','evidence','next_action','status','notes','object_id','origin_object_id','ready_for_customer'}

def _now():return datetime.now(timezone.utc).isoformat()
def _hash(value):return hashlib.sha256(value.encode('utf8')).hexdigest()
def _text(value,maximum=20000):
    if not isinstance(value,str) or len(value)>maximum or '\x00' in value:raise ValueError('文字格式无效或超过长度限制')
    return value
def _mapping(value,allowed):
    if not isinstance(value,dict) or set(value)-allowed:raise ValueError('派生字段不在允许范围')
    encoded=json.dumps(value,ensure_ascii=False,allow_nan=False)
    if len(encoded)>50000:raise ValueError('派生资料过长')
    return copy.deepcopy(value)
def _evidence(value):
    if not isinstance(value,list) or len(value)>50:raise ValueError('证据须为最多50条列表')
    result=[]
    for item in value:
        if isinstance(item,str):result.append({'text':_text(item,4000),'url':'','observed_at':''})
        elif isinstance(item,dict) and not set(item)-{'text','url','path','observed_at'}:
            result.append({key:_text(val,4000) for key,val in item.items()})
        else:raise ValueError('证据格式无效')
    return result

class CustomerWorkspace:
    def __init__(self,app):
        self.app=app;self.root=Path(app.root).resolve()
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS customer_profiles (object_id TEXT PRIMARY KEY,path TEXT NOT NULL)')
            app.db.execute('CREATE TABLE IF NOT EXISTS customer_discovery (id TEXT PRIMARY KEY,kind TEXT NOT NULL,path TEXT NOT NULL)')
            app.db.commit()

    def _read(self,path):
        target=self.root/path
        if not target.resolve().is_relative_to(self.root):raise ValueError('派生资料路径超出原业务范围')
        return json.loads(target.read_text(encoding='utf8'))

    def _write(self,path,data):
        if not path.resolve().is_relative_to(self.root) or path.is_symlink():raise ValueError('派生资料路径无效')
        local=next(p for p in path.parents if p.name=='.local');local.mkdir(parents=True,exist_ok=True,mode=0o700)
        parent=local
        for part in path.parent.relative_to(local).parts:parent=parent/part;parent.mkdir(exist_ok=True,mode=0o700)
        # One previous edit is enough for ordinary local recovery.
        if path.exists():
            previous=path.with_suffix('.prev.json')
            if previous.is_symlink():raise ValueError('派生资料上一版不能是链接')
            self._atomic(previous,path.read_bytes())
        self._atomic(path,(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
        return path.relative_to(self.root).as_posix()

    @staticmethod
    def _atomic(path,data):
        fd,name=tempfile.mkstemp(prefix='.customer-',dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.replace(name,path)
        finally:
            if os.path.exists(name):os.unlink(name)

    def _source(self,object_id):
        obj=self.app.business.get_object(object_id)
        if obj.get('kind') not in ('customer','prospect'):raise ValueError('请选择客户或候选目标')
        content=str(obj.get('content') or '')
        try:record=json.loads(content)
        except ValueError:record={}
        if not isinstance(record,dict):record={}
        source_type=obj.get('source_type') or ('website' if object_id.startswith('customer:website-') else 'local')
        original=record.get('requirements') if source_type=='website' else obj.get('original_text')
        if not isinstance(original,str):original=content
        canonical=json.dumps(record,ensure_ascii=False,sort_keys=True) if record else content
        return obj,source_type,record,original,_hash(canonical)

    def _saved_profile(self,object_id):
        with self.app.lock:row=self.app.db.execute('SELECT path FROM customer_profiles WHERE object_id=?',(object_id,)).fetchone()
        return self._read(row[0]) if row else {}

    def profile(self,object_id):
        obj,source_type,record,original,source_hash=self._source(object_id);saved=self._saved_profile(object_id)
        cleaned={'company':record.get('company'),'country':record.get('country'),'quantity':record.get('quantity'),
                 'need':record.get('requirements'),'stage':record.get('status'),'contact_name':record.get('name'),'email':record.get('email')}
        cleaned.update(saved.get('cleaned',{}))
        analysis={'intent':'unknown','fit':'unknown','basis':[],'missing':[],'next_action':'','facts':[],'inferences':[]}
        analysis.update(saved.get('analysis',{}))
        provenance={'source':obj.get('source'),'source_hash':source_hash,'observed_at':record.get('receivedAt') or record.get('checked_at'),
            'acquisition':'unknown','source_verification':{'state':'unverified','note':'仅确认原来源有这份记录；未核实访客身份、自然获客或渠道归因。' if source_type=='website' else '沿原业务记录读取；研究资料不等于采购意向或已触达。'},
            'evidence_notes':saved.get('source_note',''),'evidence':saved.get('evidence',[])}
        return {'object_id':object_id,'source_type':source_type,'provenance':provenance,'original_text':original,
            'original_language':saved.get('original_language') or record.get('original_language') or record.get('language') or 'unknown',
            'translation_zh':saved.get('translation_zh',''),'cleaned':cleaned,'analysis':analysis,
            'source_hash':source_hash,'derived_source_hash':saved.get('source_hash'),
            'stale':bool(saved) and saved.get('source_hash')!=source_hash,'updated_at':saved.get('updated_at'),
            'derivation':'人工或Agent派生资料；facts为列明依据的摘录，inferences为判断，不改原文。'}

    def save_profile(self,object_id,body):
        if not isinstance(body,dict) or set(body)-{'source_hash','original_language','translation_zh','cleaned','analysis','source_note','evidence'}:raise ValueError('不支持的客户分析字段')
        with self.app.lock:
            current=self.profile(object_id)
            if body.get('source_hash')!=current['source_hash']:raise ValueError('原来源已变化，请刷新后重新核对派生资料')
            saved=self._saved_profile(object_id)
            for key,limit in [('original_language',80),('translation_zh',50000),('source_note',10000)]:
                if key in body:saved[key]=_text(body[key],limit)
            if 'cleaned' in body:saved['cleaned']={**saved.get('cleaned',{}),**_mapping(body['cleaned'],SOURCE_FIELDS)}
            if 'analysis' in body:saved['analysis']={**saved.get('analysis',{}),**_mapping(body['analysis'],ANALYSIS_FIELDS)}
            if 'evidence' in body:saved['evidence']=_evidence(body['evidence'])
            saved.update(object_id=object_id,source_hash=current['source_hash'],updated_at=_now())
            if object_id.startswith('customer:website-'):
                reference=object_id.removeprefix('customer:website-')
                if not reference or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-' for c in reference):raise ValueError('网站询盘ID无效')
                path=self.root/'04_客户开发/.local/网站询盘'/reference/'客户分析.json'
            else:path=self.root/'04_客户开发/.local/客户分析'/(_hash(object_id)[:24]+'.json')
            relative=self._write(path,saved)
            self.app.db.execute('INSERT OR REPLACE INTO customer_profiles VALUES (?,?)',(object_id,relative));self.app.db.commit()
        return self.profile(object_id)

    def _source_candidates(self):
        path=self.root/CANDIDATES
        if not path.is_file():return []
        raw=json.loads(path.read_text(encoding='utf-8-sig'));rows=raw if isinstance(raw,list) else raw.get('candidates',[])
        result=[]
        for row in rows:
            company=str(row.get('company') or '').strip();website=str(row.get('website') or '')
            if not company or 'example.' in website.lower() or company in ('示例公司','Synthetic Example Footwear','Example Company'):continue
            source_id=str(row.get('id') or _hash(website or company)[:20])
            evidence=[{'url':row['source_url'],'text':'既有发现出处','observed_at':row.get('discovered_at') or ''}] if row.get('source_url') else []
            for page in row.get('pages',[]):
                if isinstance(page,dict) and page.get('url'):evidence.append({'url':page['url'],'text':page.get('title') or '既有读取页面','observed_at':page.get('checked_at') or ''})
            result.append({'id':'candidate:'+source_id,'kind':'candidate','source_id':source_id,'title':company,'company':company,'website':website,
                'market_hint':row.get('market_hint') or '', 'target':row.get('discovery_note') or '',
                'status':(row.get('review') or {}).get('state') or row.get('research_status') or '未核验',
                'evidence':evidence,'next_action':'','notes':'','object_id':'prospect:candidate:'+source_id,'ready_for_customer':False,'source':CANDIDATES,
                'source_record':{'contacts':row.get('contacts',[]),'research_status':row.get('research_status'),
                    'analysis':row.get('analysis',{}),'analysis_scope':'既有初筛，未在本次重新背调','review':row.get('review',{})},
                'source_verification':{'state':'unverified','note':'候选研究不代表当前采购需求；Lead ID、已发送及停止联系状态仍须核原CRM。'},
                'crm_status':'not_checked','outreach_status':'unknown','created_at':row.get('discovered_at'),'updated_at':row.get('checked_at')})
        return result

    def _local_discovery(self):
        with self.app.lock:rows=self.app.db.execute('SELECT id,kind,path FROM customer_discovery').fetchall()
        return {row[0]:self._read(row[2]) for row in rows}

    def list_discovery(self,kind='',q=''):
        if kind not in ('','candidate','research_task') or not isinstance(q,str):raise ValueError('研究查询参数无效')
        originals={row['id']:row for row in self._source_candidates()};local=self._local_discovery()
        for oid,value in local.items():
            if value.get('source_id'):
                if oid in originals:originals[oid].update(copy.deepcopy(value['annotations']),updated_at=value['updated_at'])
            else:originals[oid]=copy.deepcopy(value)
        rows=list(originals.values())
        if kind:rows=[r for r in rows if r['kind']==kind]
        if q.strip():rows=[r for r in rows if q.casefold() in json.dumps(r,ensure_ascii=False).casefold()]
        return rows

    def get_discovery(self,entry_id):
        row=next((r for r in self.list_discovery() if r['id']==entry_id),None)
        if row is None:raise ValueError('找不到这项候选或研究任务')
        return row

    def _fields(self,body):
        if not isinstance(body,dict) or set(body)-DISCOVERY_FIELDS-{'kind'}:raise ValueError('不支持的研究字段')
        clean={}
        for key,value in body.items():
            if key=='kind':continue
            if key=='ready_for_customer':
                if type(value) is not bool:raise ValueError('准备推进标记须为布尔值')
                clean[key]=value
            else:clean[key]=_evidence(value) if key=='evidence' else _text(value,12000 if key in ('notes','target','next_action') else 2000)
        return clean

    def create_discovery(self,body):
        clean=self._fields(body);kind=body.get('kind','research_task')
        if kind not in ('candidate','research_task') or not (clean.get('title') or clean.get('company')):raise ValueError('请填写研究任务标题或候选公司')
        oid=('candidate:local-' if kind=='candidate' else 'research:')+uuid4().hex;at=_now()
        row={'id':oid,'kind':kind,'source_id':None,'title':clean.get('title') or clean.get('company'),'target':'','company':'','website':'','market_hint':'',
             'evidence':[],'next_action':'','status':'待研究','notes':'','object_id':'prospect:'+oid,'ready_for_customer':False,'source':'人工研究补充',
             'source_verification':{'state':'unverified','note':'人工创建的研究对象，尚未核为采购机会或已触达。'},'crm_status':'not_checked','outreach_status':'unknown','created_at':at,'updated_at':at,**clean}
        with self.app.lock:
            path=self.root/'04_客户开发/02_目标名单/.local/工作台研究'/(oid.split(':',1)[1]+'.json')
            relative=self._write(path,row)
            self.app.db.execute('INSERT INTO customer_discovery VALUES (?,?,?)',(oid,kind,relative));self.app.db.commit()
        return row

    def update_discovery(self,entry_id,body):
        clean=self._fields(body)
        if 'kind' in body:raise ValueError('不能更改研究对象类型')
        with self.app.lock:
            old=self.get_discovery(entry_id);stored=self._local_discovery().get(entry_id,{})
            if old.get('source_id'):
                row={'id':entry_id,'kind':old['kind'],'source_id':old['source_id'],
                     'annotations':{**stored.get('annotations',{}),**clean},'updated_at':_now()}
            else:row={**old,**clean,'updated_at':_now()}
            path=self.root/'04_客户开发/02_目标名单/.local/工作台研究'/(_hash(entry_id)[:24]+'.json')
            relative=self._write(path,row)
            self.app.db.execute('INSERT OR REPLACE INTO customer_discovery VALUES (?,?,?)',(entry_id,old['kind'],relative));self.app.db.commit()
        return self.get_discovery(entry_id)

    def discovery(self):
        rows=self.list_discovery()
        counts={kind:sum(r['kind']==kind for r in rows) for kind in ('candidate','research_task')}
        return {'items':rows,'tasks':[r for r in rows if r['kind']=='research_task'],'candidates':[r for r in rows if r['kind']=='candidate'],
            'overview':{'candidate_count':counts['candidate'],'research_task_count':counts['research_task'],
                'ready_count':sum(r.get('ready_for_customer') is True for r in rows),'outreach_status':'not_enabled'},
            'sources':[{'path':CANDIDATES,'state':'ready' if (self.root/CANDIDATES).is_file() else 'not_available',
            'scope':'既有候选池只读；研究补充原业务.local保存，不复制或修改正式CRM。'}],
            'counts':counts,'outreach_enabled':False}
