"""Website inquiry source and explicitly invoked buyer-thread reply."""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError

URL='https://www.beiqiang.online/api/admin/inquiries'
REPLY_URL='https://www.beiqiang.online/api/admin/inquiry-message'

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class WebsiteInquiries:
    def __init__(self,root,fetch=None,ttl=120,clock=time.time):
        self.root=Path(root);self.fetch=fetch or self._fetch;self.ttl=ttl;self.clock=clock
        self.lock=threading.RLock();self._records=[];self._success=None;self._busy=False
        self._status={'state':'not_loaded','source':URL,'observed_at':None,'last_attempt_at':None,
                      'error':None,'total':None,'excluded_internal_tests':None,'stale':True}

    def _token(self):
        env=self.root/'03_独立站/03_网站源码/.env'
        token=None
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            key,separator,value=line.strip().removeprefix('export ').partition('=')
            if separator and key.strip()=='INQUIRY_ADMIN_TOKEN':
                value=value.strip();token=value[1:-1] if len(value)>=2 and value[0]==value[-1] and value[0] in '\"\'' else value
        if not token:raise ValueError('TOKEN_NOT_CONFIGURED')
        return token

    def _fetch(self):
        request=Request(URL,headers={'Authorization':'Bearer '+self._token(),'Accept':'application/json'},method='GET')
        with build_opener(_NoRedirect).open(request,timeout=10) as response:
            raw=response.read(5_000_001)
            if len(raw)>5_000_000:raise ValueError('RESPONSE_TOO_LARGE')
            return json.loads(raw)

    def reply(self, object_id, message):
        if not isinstance(object_id,str) or not object_id.startswith('customer:website-'):
            raise ValueError('仅支持网站询盘私信')
        if not isinstance(message,str) or not 2<=len(message.strip())<=2000:
            raise ValueError('请输入2至2000字的回复')
        self.refresh(wait=True)
        if self.status(start_refresh=False)['state']!='ready':raise ValueError('网站询盘暂不可读，未发送')
        ref=object_id.removeprefix('customer:website-')
        record=next((r for r in self.records() if r.get('reference')==ref),None)
        if not record or not record.get('receivedAt'):raise ValueError('未找到网站询盘，未发送')
        payload=json.dumps({'reference':ref,'receivedAt':record['receivedAt'],'message':message.strip()},ensure_ascii=False).encode('utf-8')
        request=Request(REPLY_URL,data=payload,headers={'Authorization':'Bearer '+self._token(),'Content-Type':'application/json','Accept':'application/json'},method='POST')
        try:
            with build_opener(_NoRedirect).open(request,timeout=20) as response: result=json.loads(response.read())
        except Exception as exc:
            raise ValueError('发送结果未确认，请先重新读取网站往来，确认是否已保存后再操作') from exc
        if not result.get('ok'):raise ValueError('网站未确认保存，请先重新读取往来')
        saved=result.get('record') or {}
        messages=saved.get('messages') or []
        last=messages[-1] if messages else {}
        if saved.get('reference')!=ref or last.get('body')!=message.strip():
            raise ValueError('网站返回未能确认消息，请先重新读取网站往来')
        with self.lock:
            self._records=[copy.deepcopy(saved) if r.get('reference')==ref else r for r in self._records]
        return {'saved':True,'notification_sent':bool(result.get('notificationSent')),'message_id':last.get('id')}

    def _load(self):
        try:
            payload=self.fetch()
            if not isinstance(payload,dict) or payload.get('ok') is not True or not isinstance(payload.get('records'),list):raise ValueError('INVALID_RESPONSE')
            records=payload['records']
            if any(not isinstance(row,dict) or not isinstance(row.get('reference'),str) for row in records):raise ValueError('INVALID_RESPONSE')
            visible=[r for r in records if r.get('internalTest') is not True]
            now=self.clock()
            with self.lock:
                self._records=copy.deepcopy(visible);self._success=now
                self._status.update(state='ready',observed_at=datetime.fromtimestamp(now,timezone.utc).isoformat(),
                    error=None,total=len(visible),excluded_internal_tests=len(records)-len(visible),stale=False)
        except Exception as error:
            code='AUTH_REQUIRED' if isinstance(error,HTTPError) and error.code in (401,403) else 'SOURCE_UNAVAILABLE'
            if isinstance(error,(FileNotFoundError,)) or str(error)=='TOKEN_NOT_CONFIGURED':code='TOKEN_NOT_CONFIGURED'
            with self.lock:self._status.update(state='not_configured' if code=='TOKEN_NOT_CONFIGURED' else 'error',error={'code':code,'message':'网站原来源暂不可读；本地客户和已有成果仍可使用。'},stale=True)
        finally:
            with self.lock:self._busy=False

    def refresh(self,wait=False):
        with self.lock:
            if self._busy:return self.status(start_refresh=False)
            self._busy=True;self._status.update(state='refreshing',last_attempt_at=datetime.fromtimestamp(self.clock(),timezone.utc).isoformat())
        if wait:self._load()
        else:threading.Thread(target=self._load,daemon=True,name='website-inquiries-read').start()
        return self.status(start_refresh=False)

    def status(self,start_refresh=True):
        with self.lock:
            expired=self._success is None or self.clock()-self._success>=self.ttl
            # Failed attempts also have a TTL, avoiding one thread per list call.
            attempted=self._status['last_attempt_at']
            recent=attempted and self.clock()-datetime.fromisoformat(attempted).timestamp()<self.ttl
            should=start_refresh and expired and not self._busy and not recent
            if expired:self._status['stale']=True
        if should:self.refresh()
        with self.lock:return copy.deepcopy(self._status)

    def records(self):
        self.status()
        with self.lock:return copy.deepcopy(self._records)
