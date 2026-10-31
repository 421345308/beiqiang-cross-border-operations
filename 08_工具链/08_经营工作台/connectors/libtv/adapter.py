"""Bounded official LibTV CLI adapter. No model execution or default binding."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from uuid import uuid4

HERE = Path(__file__).resolve().parent
OPERATIONS = {'account': set(), 'workspaces': {'page', 'page_size'},
    'projects': {'workspace_id', 'page', 'page_size'}, 'project': {'project_id'},
    'nodes': {'project_id'}, 'create_project': {'name', 'workspace_id'},
    'create_text_node': {'project_id', 'title', 'content', 'x', 'y'}}
WRITES = {'create_project', 'create_text_node'}

class AdapterError(Exception):
    def __init__(self, code, message): self.code, self.message = code, message

def _text(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or '\x00' in value:
        raise AdapterError('INVALID_ARGUMENT', '文字为空、过长或包含无效字符。')
    return value

def _workspace(value):
    if isinstance(value, bool) or not re.fullmatch(r'0|[1-9][0-9]{0,18}', str(value)):
        raise AdapterError('INVALID_ARGUMENT', '请明确指定工作区ID；0代表根目录。')
    return str(value)

def _project(value):
    if not isinstance(value,str) or not re.fullmatch(r'(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})',value):
        raise AdapterError('INVALID_ARGUMENT', '请指定有效的画布UUID。')
    return value

def _coordinate(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>10_000_000:
        raise AdapterError('INVALID_ARGUMENT', '画布坐标必须为有限数字。')
    return str(value)

def _first(value, *keys, default=None):
    return next((value[k] for k in keys if isinstance(value,dict) and value.get(k) is not None), default)

def _items(payload, *keys):
    if isinstance(payload,list): return payload
    for key in keys:
        if isinstance(payload.get(key),list): return payload[key]
        if key in payload and payload[key] is None: return []
    raise AdapterError('UNEXPECTED_RESPONSE','CLI返回结构已变化，请先检查官方CLI。')

def _node(value):
    data=value.get('data') or {};position=value.get('position') or {}
    return {'id':str(_first(value,'id','nodeId','nodeKey',default='')),
        'title':_first(value,'name','label','title',default=_first(data,'name','label','title',default='')),
        'type':_first(value,'type',default=data.get('type')),
        'x':_first(position,'x',default=value.get('x')), 'y':_first(position,'y',default=value.get('y')),
        'content':data.get('content',value.get('content'))}

def _canvas(value, fallback=None):
    # Actual project create stdout is {projectMeta:{uuid,name,...}}; list
    # entries and project summaries are unwrapped. Never infer an ID from name.
    if isinstance(value.get('projectMeta'),dict): value=value['projectMeta']
    return {'id':str(_first(value,'uuid','projectUuid','id',default=fallback or '')),
        'name':_first(value,'name','projectName','title',default=''),
        'workspace_id':_first(value,'workspaceId','folderId'),
        'updated_at':_first(value,'updatedAt','updated_at','updatedAtMs'), 'official_url':None}

def _redact(value):
    if isinstance(value,dict): return {k:_redact(v) for k,v in value.items() if not re.search(r'token|cookie|password|secret|authorization|email|phone',k,re.I)}
    if isinstance(value,list): return [_redact(v) for v in value]
    return value

class Adapter:
    def __init__(self, runner=None, executable=None, receipt_dir=None):
        self.runner=runner or subprocess.run
        self.executable=executable or shutil.which('libtv')
        self.receipt_dir=Path(receipt_dir) if receipt_dir is not None else HERE/'.local'/'receipts'

    def _call(self,args,cwd):
        if not self.executable: raise AdapterError('CLI_NOT_FOUND','本机未找到LibTV官方CLI。')
        if str(self.executable).lower().endswith(('.cmd','.bat')): raise AdapterError('UNSAFE_LAUNCHER','请使用LibTV官方原生可执行文件。')
        env=dict(os.environ);env.pop('LIBTV_DEBUG',None)
        try:
            result=self.runner([self.executable,*args],shell=False,cwd=cwd,env=env,
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
        except subprocess.TimeoutExpired: raise AdapterError('CLI_TIMEOUT','LibTV响应超时；创建结果可能未知，请先回读，不要重复提交。')
        except OSError: raise AdapterError('CLI_UNAVAILABLE','LibTV无法启动，请检查本机CLI。')
        if result.returncode:
            if re.search(r'\b401\b|\b10001\b|未登录|未授权',result.stderr or ''):
                raise AdapterError('AUTH_REQUIRED','请先通过LibTV官方CLI正常登录。')
            raise AdapterError('CLI_FAILED','LibTV操作未成功；请在受控终端检查，不要重复创建。')
        if len(result.stdout.encode('utf-8'))>10_000_000: raise AdapterError('RESPONSE_TOO_LARGE','CLI响应过大，请缩小查询范围。')
        try: payload=json.loads(result.stdout)
        except (ValueError,TypeError): raise AdapterError('UNEXPECTED_RESPONSE','CLI未返回有效JSON。')
        if not isinstance(payload,(dict,list)): raise AdapterError('UNEXPECTED_RESPONSE','CLI响应类型无效。')
        if isinstance(payload,dict) and (payload.get('ok') is False or payload.get('code') in (401,10001)):
            raise AdapterError('CLI_FAILED','LibTV未确认成功，请检查登录与操作范围。')
        return payload

    def execute(self,operation,**kwargs):
        requested_operation=operation
        operation=operation.replace('-','_') if isinstance(operation,str) else ''
        request_id=uuid4().hex
        source={'provider':'libtv-cli','request_id':request_id,'receipt':None,'read_only':operation not in WRITES}
        try:
            if operation not in OPERATIONS or set(kwargs)-OPERATIONS[operation]: raise AdapterError('INVALID_OPERATION','不支持的操作或参数。')
            page=kwargs.get('page',1);size=kwargs.get('page_size',20)
            if type(page) is not int or page<1 or type(size) is not int or not 1<=size<=100: raise AdapterError('INVALID_ARGUMENT','分页参数无效。')
            args=[]
            if operation=='workspaces': args=['workspace','list','--page',str(page),'--page-size',str(size)]
            elif operation=='projects':
                args=['project','list','--page',str(page),'--page-size',str(size)]
                if 'workspace_id' in kwargs: args+=['-w',_workspace(kwargs['workspace_id'])]
            elif operation=='project': args=['project',_project(kwargs.get('project_id'))]
            elif operation=='nodes': args=['node','list','-p',_project(kwargs.get('project_id'))]
            elif operation=='create_project': args=['project','create','-w',_workspace(kwargs.get('workspace_id')),'--',_text(kwargs.get('name'),200)]
            elif operation=='create_text_node':
                args=['node','--x',_coordinate(kwargs.get('x',0)),'--y',_coordinate(kwargs.get('y',0)),
                    'create','-p',_project(kwargs.get('project_id')),'-t','text','-u',
                    'content='+json.dumps([_text(kwargs.get('content'),20000)],ensure_ascii=False),
                    '--',_text(kwargs.get('title'),200)]
            with tempfile.TemporaryDirectory(prefix='beiqiang-libtv-') as cwd:
                # account info mutates active scope. list only reads it. Some CLI
                # project endpoints return false empty success when unauthenticated.
                accounts=self._call(['account','list'],cwd)
                active=next((a for a in _items(accounts,'accounts') if a.get('isActive') is True),None)
                if not active: raise AdapterError('ACCOUNT_NOT_SELECTED','没有可确认的当前账户，请在官方CLI选择账户。')
                if operation=='account':
                    data={'account':{'name':active.get('accountName',''),'account_type':active.get('accountType'),
                        'status':'authenticated','credits':_first(active,'credits','balance','remainingCredits')}}
                    payload=None
                else:
                    payload=self._call(args,cwd)
                    if operation in WRITES:
                        self.receipt_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
                        receipt=self.receipt_dir/(request_id+'.json')
                        with receipt.open('x',encoding='utf-8') as stream: json.dump({'operation':operation,'request_id':request_id,'response':_redact(payload)},stream,ensure_ascii=False)
                        if os.name!='nt': receipt.chmod(0o600)
                        source['receipt']='.local/receipts/'+receipt.name
                    if operation in ('workspaces','projects'):
                        values=_items(payload,*(['folders'] if operation=='workspaces' else ['projectMetaList','projects']))
                        items=[({'id':str(v.get('id','')),'name':v.get('name',''),'updated_at':_first(v,'updatedAt','updated_at','updateAt'),'official_url':None} if operation=='workspaces' else _canvas(v)) for v in values]
                        data={operation:{'items':items,'total':payload.get('total',len(items)),'page':page,'page_size':size}}
                    elif operation=='nodes':
                        values=_items(payload,'nodes','nodeList')
                        items=[_node(v) for v in values]
                        text_nodes=[n for n in items if n['type']=='text']
                        # node list intentionally omits content. Read only a small
                        # bounded set of text nodes with the official node query.
                        for node in text_nodes[:10]:
                            if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',node['id']):
                                raise AdapterError('UNEXPECTED_RESPONSE','CLI返回无效节点ID。')
                            detail=_node(self._call(['node',node['id'],'-p',kwargs['project_id']],cwd))
                            node['content']=detail['content']
                            if detail['title']:node['title']=detail['title']
                        data={'nodes':{'project_id':kwargs['project_id'],'items':items,'total':len(values),'text_content_complete':len(text_nodes)<=10}}
                    elif operation in ('project','create_project'):
                        canvas=_canvas(payload,kwargs.get('project_id'));canvas.update(nodes=[_node(v) for v in payload.get('nodes',[])],edges=[{k:v.get(k) for k in ('id','source','target')} for v in payload.get('edges',[])])
                        data={'project':canvas}
                    else:
                        data={'node':_node(payload.get('node',payload)),'project_id':kwargs['project_id']}
                    if operation in WRITES and not data['project' if operation=='create_project' else 'node']['id']:
                        raise AdapterError('WRITE_RESULT_UNCONFIRMED','CLI创建返回缺少ID；请先回读画布，不要重复创建。')
            return {'ok':True,'operation':requested_operation,'data':data,'error':None,'source':source}
        except AdapterError as error:
            return {'ok':False,'operation':requested_operation,'data':None,'error':{'code':error.code,'message':error.message,'retryable':False},'source':source}
        except Exception:
            return {'ok':False,'operation':requested_operation,'data':None,'error':{'code':'ADAPTER_ERROR','message':'本机适配失败，请在受控终端检查；不要重复创建。','retryable':False},'source':source}

def execute(operation,**kwargs): return Adapter().execute(operation,**kwargs)
def create_project(name,workspace_id): return execute('create_project',name=name,workspace_id=workspace_id)
def create_text_node(project_id,title,content,x=0,y=0): return execute('create_text_node',project_id=project_id,title=title,content=content,x=x,y=y)
