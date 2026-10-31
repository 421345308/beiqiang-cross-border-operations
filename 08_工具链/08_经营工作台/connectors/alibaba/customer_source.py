"""Private, bounded Alibaba order-buyer source. This is not an inquiry feed.

Uses the maintained authorized client, never refreshes tokens or writes to Alibaba.
Only read-business APIs are invoked (the official signing transport uses POST).
"""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

LIST = 'alibaba.seller.order.list'
GET = 'alibaba.seller.order.get'
CACHE = '04_客户开发/.local/alibaba-order-buyers/cache.json'


def _timestamp(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _hash(value):
    return hashlib.sha256(value.encode('utf8')).hexdigest()[:24]


def _client():
    path=Path(__file__).with_name('adapter.py')
    spec=importlib.util.spec_from_file_location('alibaba_customer_client',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.ExistingClient()


class SourceError(Exception):
    def __init__(self,code):self.code=code


class AlibabaCustomerSource:
    def __init__(self, root, client=None, ttl=120, clock=time.time, page_size=5):
        if type(page_size) is not int or not 1<=page_size<=20:raise ValueError('每页订单数应为1至20')
        self.root=Path(root).resolve();self.client=client;self.ttl=ttl;self.clock=clock;self.page_size=page_size
        self.cache=self.root/CACHE;self.lock=threading.RLock();self.condition=threading.Condition(self.lock)
        self._busy=False;self._success=None;self._attempt=None;self._records=[]
        self._enabled=client is not None or (self.root/'.agents/skills/alibaba-openapi-operator/scripts/alibaba_openapi.py').is_file()
        self._status={'state':'not_loaded','source':'alibaba-openapi','source_kind':'alibaba_order_buyer',
                      'coverage':'single-page-orders-not-inquiries','observed_at':None,'last_attempt_at':None,
                      'error':None,'stale':True,'loaded_orders':None,'loaded_buyers':None,'pagination':None,
                      'account_identity_verified':False,
                      'inquiries':{'state':'not-verified','reason':'既有2026-09权限清单未记录询盘/CRM读取接口；本轮未验证其当前授权，不把订单买家当作询盘。'}}
        if self.cache.is_file() and not self.cache.is_symlink() and self.cache.resolve().is_relative_to(self.root):
            try:
                value=json.loads(self.cache.read_text(encoding='utf8'))
                if isinstance(value.get('records'),list) and isinstance(value.get('success_epoch'),(float,int)):
                    self._records=value['records'];self._success=value['success_epoch']
                    self._status.update(value['status']);self._status.update(state='ready',stale=self.clock()-self._success>=self.ttl)
            except (ValueError,OSError,KeyError):pass

    def _call(self,method,params):
        if method not in (LIST,GET):raise SourceError('UNSUPPORTED_OPERATION')
        if self.client is None:self.client=_client()
        raw=self.client.call(method,params)
        if (not isinstance(raw,dict) or raw.get('error_response') or raw.get('success') is False
                or str(raw.get('code','0')) not in ('','0')):raise SourceError('PLATFORM_ERROR')
        return raw

    @staticmethod
    def _dates(value):
        return {k:v for k,v in (value or {}).items() if k in ('timestamp','format_date') and type(v) in (str,int)} if isinstance(value,dict) else None

    @staticmethod
    def _ids(raw):
        return {target:raw[key] for target,key in (('request_id','request_id'),('trace_id','_trace_id_'))
                if isinstance(raw.get(key),str) and re.fullmatch('[A-Za-z0-9_-]{1,160}',raw[key])}

    def _load(self,page):
        try:
            raw=self._call(LIST,{'param_trade_ecology_order_list_query':json.dumps({'role':'seller','start_page':page-1,'page_size':self.page_size})})
            body=raw.get('result')
            if not isinstance(body,dict) or body.get('success') is not True:raise SourceError('ORDER_LIST_NOT_SUCCESSFUL')
            value=body.get('value') or {};rows=value.get('order_list');total=value.get('total_count')
            if not isinstance(rows,list) or type(total) is not int or total<0:raise SourceError('INVALID_RESPONSE')
            ids=[r.get('trade_id') if isinstance(r,dict) else None for r in rows]
            more=page*self.page_size<total
            if (any(not isinstance(pid,str) or not pid for pid in ids) or len(set(ids))!=len(ids)
                    or len(rows)>self.page_size or total<len(rows) or (more and len(rows)!=self.page_size)
                    or (not rows and (page-1)*self.page_size<total)):raise SourceError('INVALID_PAGINATION')
            records={};originals={'list':raw,'details':[]}
            for pid in ids:
                detail=self._call(GET,{'e_trade_id':pid,'language':'en_US'})
                order=detail.get('value')
                if not isinstance(order,dict) or order.get('trade_id')!=pid:raise SourceError('ORDER_IDENTITY_MISMATCH')
                buyer=order.get('buyer')
                if not isinstance(buyer,dict) or not buyer:raise SourceError('BUYER_NOT_RETURNED')
                identity=buyer.get('immutable_eid') or buyer.get('e_account_id')
                identity_scope='buyer-account' if isinstance(identity,str) and identity else 'order-only'
                reference=_hash(('buyer:'+identity) if identity_scope=='buyer-account' else 'order:'+pid)
                if reference not in records:
                    records[reference]={'id':'alibaba-order-buyer:'+reference,'source_kind':'alibaba_order_buyer',
                        'name':buyer.get('full_name') if isinstance(buyer.get('full_name'),str) else None,
                        'country':buyer.get('country') if isinstance(buyer.get('country'),str) else None,
                        'buyer_ref':reference,'identity_scope':identity_scope,'orders':[],
                        'source':{'provider':'alibaba-openapi','methods':[LIST,GET],'account_identity_verified':False}}
                products=order.get('order_products',[])
                if isinstance(products,dict):products=products.get('trade_ecology_order_product',[])
                if not isinstance(products,list):raise SourceError('INVALID_RESPONSE')
                projected=[]
                for product in products:
                    if not isinstance(product,dict):raise SourceError('INVALID_RESPONSE')
                    projected.append({key:product[key] for key in ('product_id','name','sku_id','sku_code','model_number','quantity','unit')
                                      if type(product.get(key)) in (str,int)})
                    for key in ('product_id','sku_id'):
                        if key in projected[-1]:projected[-1][key]=str(projected[-1][key])
                records[reference]['orders'].append({'id':pid,'status':order.get('trade_status') if isinstance(order.get('trade_status'),str) else None,
                    'created':self._dates(order.get('create_date')),'modified':self._dates(order.get('modify_date')),
                    'products':projected,'source':self._ids(detail)})
                originals['details'].append(detail)
            epoch=self.clock();at=_timestamp(epoch)
            for record in records.values():record['observed_at']=at
            result=list(records.values())
            if hasattr(self.client,'safe'):
                result=self.client.safe(result);originals=self.client.safe(originals)
            status={**self._status,'state':'ready','observed_at':at,'error':None,'stale':False,
                    'loaded_orders':len(ids),'loaded_buyers':len(result),
                    'pagination':{'page':page,'pageSize':self.page_size,'totalOrders':total,'returnedOrders':len(ids),
                                  'hasMore':more,'nextPage':page+1 if more else None},'list_receipt':self._ids(raw)}
            self._persist({'records':result,'originals':originals,'status':status,'success_epoch':epoch})
            with self.lock:self._records=result;self._success=epoch;self._status=status
        except Exception as exc:
            with self.lock:
                self._status.update(state='error',stale=True,error={'code':exc.code if isinstance(exc,SourceError) else 'CLIENT_OR_CACHE_FAILURE',
                    'message':'国际站订单买家来源暂不可读；保留上次成功缓存，不把失败计为零客户或零询盘。'})
        finally:
            with self.condition:self._busy=False;self.condition.notify_all()

    def _persist(self,value):
        folder=self.cache.parent
        if not folder.resolve().is_relative_to(self.root) or self.cache.is_symlink():raise SourceError('CACHE_PATH_INVALID')
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd,name=tempfile.mkstemp(prefix='.buyers-',dir=folder)
        try:
            with os.fdopen(fd,'w',encoding='utf8') as stream:
                json.dump(value,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.cache)
        finally:Path(name).unlink(missing_ok=True)

    def refresh(self,wait=False,page=1):
        if type(page) is not int or page<1:raise ValueError('页码无效')
        if not self._enabled:
            with self.lock:self._status.update(state='not_configured',error={'code':'CLIENT_NOT_AVAILABLE','message':'该工作区未配置国际站客户端。'})
            return self.status(start_refresh=False)
        with self.condition:
            if self._busy:
                if wait:self.condition.wait_for(lambda:not self._busy)
                return self.status(start_refresh=False)
            self._busy=True;self._attempt=self.clock()
            self._status.update(state='refreshing',last_attempt_at=_timestamp(self._attempt))
        if wait:self._load(page)
        else:threading.Thread(target=self._load,args=(page,),daemon=True,name='alibaba-order-buyers-read').start()
        return self.status(start_refresh=False)

    def status(self,start_refresh=True):
        with self.lock:
            expired=self._success is None or self.clock()-self._success>=self.ttl
            recent=self._attempt is not None and self.clock()-self._attempt<self.ttl
            if expired:self._status['stale']=True
            should=start_refresh and expired and not recent and not self._busy
        if should:self.refresh()
        with self.lock:return copy.deepcopy(self._status)

    def records(self):
        self.status()
        with self.lock:return copy.deepcopy(self._records)
