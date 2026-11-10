"""Local Gmail coordination, read-only polling and durable reply event deduplication."""
from __future__ import annotations
import copy
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from pathlib import Path
import threading
import time
from gmail_mailbox import GmailMailbox, normalize_email, test_credentials, save_password, credential_available
from gmail_oauth import GmailDependencyError, GmailOAuth, GmailOAuthMailbox, parse_addresses, credentials_available as oauth_credentials_available


class GmailDispatchDeferred(Exception):
    """Callback definitely did not create a job; retry later is safe.

    Raise only before invoking the job creation service, never for an unknown
    outcome after it has been invoked.
    """


def _add_event_column(db,name):
    try:db.execute('ALTER TABLE gmail_reply_events ADD COLUMN '+name+' TEXT')
    except sqlite3.OperationalError:
        # A separate process may have migrated the same column after our
        # PRAGMA snapshot. Only suppress the error when the column now exists.
        if name not in {row[1] for row in db.execute('PRAGMA table_info(gmail_reply_events)')}:raise


def _timestamp(value):
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d.timestamp() if d.tzinfo else None
    except (ValueError, TypeError, OverflowError):return None


def customer_emails(obj):
    """Only explicit contact fields; never infer addresses from narrative or URLs."""
    if obj.get('kind') not in ('customer','prospect'):raise ValueError('请选择客户或候选目标')
    try:record=json.loads(obj.get('content') or '{}')
    except (ValueError,TypeError):record={}
    if not isinstance(record,dict):record={}
    values=[record.get(k) for k in ('email','Email','EMAIL','contact_email','buyerEmail','Contact_Email')]
    for key in ('contact','contactInfo'):
        if isinstance(record.get(key),dict):values.append(record[key].get('email'))
    source=record.get('source_record') or {}
    for contact in source.get('contacts',[]) if isinstance(source,dict) else []:
        if isinstance(contact,dict) and str(contact.get('kind','')).lower() in ('email','e-mail','邮箱'):
            values.append(contact.get('value'))
    values.extend(f.get('value') for f in obj.get('facts',[]) if isinstance(f,dict) and str(f.get('label','')).strip().lower() in ('email','e-mail','邮箱','电子邮箱','联系邮箱','客户邮箱','contact_email'))
    found=set()
    for value in values:
        if not isinstance(value,str):continue
        for address in parse_addresses([value]):
            try:found.add(normalize_email(address))
            except ValueError:pass
    return sorted(found)


class GmailService:
    def __init__(self,app,*,mailbox_factory=GmailMailbox,credential_tester=test_credentials,
                 credential_saver=save_password,credential_checker=credential_available,
                 oauth_factory=GmailOAuth,oauth_mailbox_factory=GmailOAuthMailbox,
                 oauth_credential_checker=oauth_credentials_available,on_new_reply=None,translator=None,interval=120,clock=time.time):
        self.app=app;self.mailbox_factory=mailbox_factory;self.credential_tester=credential_tester
        self.credential_saver=credential_saver;self.credential_checker=credential_checker
        self.on_new_reply=on_new_reply;self.interval=interval;self.clock=clock
        self.translator=translator
        self.oauth=oauth_factory();self.oauth_mailbox_factory=oauth_mailbox_factory;self.oauth_credential_checker=oauth_credential_checker
        self.lock=threading.RLock();self._stop=threading.Event();self._thread=None
        self._cache={};self._mailbox=None;self._account='';self._connected_at=None;self.revision=0
        self._inbox={'status':{'state':'loading','last_success_at':None},'items':[]}
        self._state='not_connected';self._error=None;self._last_success=None;self._auth_mode='';self._publishing_status='';self._authorized_at=None
        self.path=Path(app.state)/'gmail.json'
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS gmail_reply_events (object_id TEXT NOT NULL,message_id TEXT NOT NULL,dispatch_state TEXT NOT NULL,PRIMARY KEY(object_id,message_id))')
            columns={row[1] for row in app.db.execute('PRAGMA table_info(gmail_reply_events)')}
            for column in ('job_id','updated_at','last_error'):
                if column not in columns:_add_event_column(app.db,column)
            app.db.execute('CREATE TABLE IF NOT EXISTS gmail_acknowledged (object_id TEXT PRIMARY KEY,message_id TEXT NOT NULL)')
            app.db.execute('CREATE TABLE IF NOT EXISTS gmail_inbox_dismissed (account TEXT NOT NULL,message_id TEXT NOT NULL,PRIMARY KEY(account,message_id))')
            app.db.execute('CREATE TABLE IF NOT EXISTS gmail_customer_addresses (object_id TEXT NOT NULL,address TEXT NOT NULL,PRIMARY KEY(object_id,address))')
            app.db.commit()
        from gmail_observations import GmailObservations
        self.observations=GmailObservations(app)
        if self.path.exists():
            try:
                config=json.loads(self.path.read_text(encoding='utf-8-sig'))
                self._account=normalize_email(config['email']);self._connected_at=config.get('connected_at')
                self._auth_mode=config.get('auth_mode') or 'app_password'
                self._publishing_status=config.get('publishing_status') or ''
                self._authorized_at=config.get('authorized_at') or self._connected_at
                checker,factory=(self.oauth_credential_checker,self.oauth_mailbox_factory) if self._auth_mode=='oauth' else (self.credential_checker,self.mailbox_factory)
                if checker(self._account):
                    self._mailbox=self._observe_mailbox(factory(self._account));self._state='connected'
            except GmailDependencyError as exc:
                self._state='error';self._error=str(exc)
            except Exception:
                self._state='error';self._error='Gmail本地配置或系统凭据暂不可读'

    def _observe_mailbox(self,mailbox):
        # The mailbox itself publishes even when a read-only caller invokes
        # context directly, without GmailService.customer or dispatching.
        mailbox.observation_store=self.observations
        return mailbox

    def _authorization_details(self):
        at=_timestamp(self._authorized_at)
        if self._auth_mode=='oauth' and self._publishing_status=='testing' and at is not None:
            return {'authorization_expires_at':(datetime.fromtimestamp(at,timezone.utc)+timedelta(days=7)).isoformat()}
        return {}

    def status(self):
        with self.lock:return {'state':self._state,'account_email':self._account,'connected_at':self._connected_at,
                               'last_success_at':self._last_success,'error':self._error,'revision':self.revision,
                               'auth_mode':self._auth_mode,'running':bool(self._thread and self._thread.is_alive()),**self._authorization_details()}

    def connect(self,email,password):
        account=normalize_email(email)
        # No persistence occurs before the supplied credential has passed a real login check.
        self.credential_tester(account,password)
        self.credential_saver(account,password)
        mailbox=self._observe_mailbox(self.mailbox_factory(account))
        # Keep the original sync boundary when reconnecting the same account,
        # so replies received while disconnected are still picked up.
        connected_at=(self._connected_at if self._account==account and _timestamp(self._connected_at) is not None
                      else datetime.fromtimestamp(self.clock(),timezone.utc).isoformat())
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        with self.lock:
            temporary.write_text(json.dumps({'email':account,'connected_at':connected_at}),encoding='utf-8')
            temporary.replace(self.path)
            self._account=account;self._connected_at=connected_at;self._mailbox=mailbox
            self._auth_mode='app_password';self._publishing_status='';self._authorized_at=None;self._cache={};self._inbox={'status':{'state':'loading','last_success_at':None},'items':[]};self._state='connected';self._error=None;self._last_success=None;self.revision+=1
        return self.status()

    def start_oauth(self,client_config,redirect_uri):
        return self.oauth.start(client_config,redirect_uri,self._account)

    def finish_oauth(self,state,code):
        account=self.oauth.finish(state,code)
        connected_at=(self._connected_at if self._account==account and _timestamp(self._connected_at) is not None
                      else datetime.fromtimestamp(self.clock(),timezone.utc).isoformat())
        authorized_at=datetime.fromtimestamp(self.clock(),timezone.utc).isoformat()
        mailbox=self._observe_mailbox(self.oauth_mailbox_factory(account))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        with self.lock:
            config={'email':account,'connected_at':connected_at,'auth_mode':'oauth','authorized_at':authorized_at}
            if self._account==account and self._publishing_status:config['publishing_status']=self._publishing_status
            temporary.write_text(json.dumps(config),encoding='utf-8')
            temporary.replace(self.path)
            if self._account!=account:self._publishing_status=''
            self._account=account;self._connected_at=connected_at;self._authorized_at=authorized_at;self._mailbox=mailbox;self._auth_mode='oauth'
            self._cache={};self._inbox={'status':{'state':'loading','last_success_at':None},'items':[]};self._state='connected';self._error=None;self._last_success=None;self.revision+=1
        self.start()
        return self.status()

    def _empty(self,state=None,error=None):
        return {'status':{'state':state or self._state,'account_email':self._account,'last_success_at':None,'error':error or self._error,**self._authorization_details()},
                'messages':[],'reply_pending':None,'next_action':'连接Gmail后查看邮件往来'}

    def peek(self,object_id):
        with self.lock:return copy.deepcopy(self._cache.get(object_id) or self._empty())

    def translation_changed(self):
        with self.lock:self.revision+=1

    def buyer_candidates(self):
        with self.lock:
            if not self._mailbox:return {'status':{'state':'not_connected'},'items':[]}
            result=copy.deepcopy(self._inbox)
            result.setdefault('status',{}).update(self._authorization_details())
            return result

    def dismiss_candidate(self,message_id):
        with self.lock:
            if not any(item.get('id')==message_id for item in self._inbox.get('items',[])):
                raise ValueError('邮件已不在待查看列表')
        with self.app.lock:
            self.app.db.execute('INSERT OR IGNORE INTO gmail_inbox_dismissed VALUES (?,?)',(self._account,message_id));self.app.db.commit()
        with self.lock:
            self._inbox['items']=[item for item in self._inbox.get('items',[]) if item.get('id')!=message_id];self.revision+=1
            return copy.deepcopy(self._inbox)

    def _workflow(self,object_id):
        workspace=self.app.customer_workspace
        if hasattr(workspace,'_saved_profile'):
            return workspace._saved_profile(object_id).get('workflow') or {}
        return workspace.workflow(object_id)

    def addresses(self, obj):
        with self.app.lock:
            rows=self.app.db.execute('SELECT address FROM gmail_customer_addresses WHERE object_id=?',(obj['id'],)).fetchall()
        return sorted(set(customer_emails(obj)) | {row[0] for row in rows})

    def link_sent_address(self, object_id, address):
        address=normalize_email(address)
        with self.app.lock:
            self.app.db.execute('INSERT OR IGNORE INTO gmail_customer_addresses VALUES (?,?)',(object_id,address));self.app.db.commit()

    def customer(self,object_id,force=False,*,_context=None,_object=None):
        obj=_object if _object is not None else self.app.business.get_object(object_id)
        emails=self.addresses(obj)
        with self.lock:
            account=self._account;mailbox=self._mailbox
        emails=[e for e in emails if e!=account]
        if not mailbox:
            result=self._empty()
        elif not emails:
            result=self._empty('no_contact_email','客户原记录未填写联系邮箱')
            result['next_action']='请先在客户原资料填写联系邮箱'
        else:
            try:
                result=copy.deepcopy(_context if _context is not None else mailbox.context(emails,force=force))
            except Exception as exc:
                result=self.peek(object_id);result['status'].update(state='error',error='Gmail读取失败（'+type(exc).__name__+'）');result['reply_pending']=None
            if result.get('status',{}).get('state')!='ready' and not result.get('messages'):
                result['messages']=self.peek(object_id).get('messages',[])
            accepted=[]
            for message in result.get('messages',[]):
                direction=message.get('direction')
                explicit=set(message.get('customer_emails') or [])
                senders=set(parse_addresses([message.get('from') or '']))
                recipients=set(parse_addresses([message.get(k) or '' for k in ('to','cc','bcc')]))
                valid=(direction=='inbound' and account in recipients and (senders|explicit).intersection(emails)) or (direction=='outbound' and account in senders and (recipients|explicit).intersection(emails))
                if valid and message.get('mail_kind')!='promotion':accepted.append(message)
            result['messages']=accepted
            source_state=result.get('status',{}).get('state')
            if source_state=='ready':
                dated=[m for m in accepted if m.get('mail_kind')!='automatic' and _timestamp(m.get('sent_at')) is not None]
                latest=max(dated,key=lambda m:_timestamp(m['sent_at']),default=None)
                result['reply_pending']=bool(latest and latest.get('direction')=='inbound')
                acknowledged=False
                if result['reply_pending']:
                    flow=self._workflow(object_id)
                    if flow.get('state')=='waiting_customer':
                        entered=next((h.get('at') for h in reversed(flow.get('history') or []) if h.get('to')=='waiting_customer'),None)
                        boundary=_timestamp(flow.get('waiting_since') or entered or flow.get('updated_at'))
                    else:boundary=None
                    if boundary is None:boundary=_timestamp(self._connected_at)
                    if boundary is not None and _timestamp(latest['sent_at'])<=boundary:result['reply_pending']=False
                    with self.app.lock:
                        ack=self.app.db.execute('SELECT message_id FROM gmail_acknowledged WHERE object_id=?',(object_id,)).fetchone()
                    if ack and str(latest.get('id'))==ack[0]:result['reply_pending']=False;acknowledged=True
                result['next_action']='查看客户新回复并准备答复' if result['reply_pending'] else '已标记处理，可继续跟进客户' if acknowledged else '等待客户回复' if latest else '暂无已同步邮件'
                if result['reply_pending'] is False and result['status'].get('thread_lookup_incomplete'):
                    result['reply_pending']=None;result['next_action']='部分邮件线程尚未读完，请稍后更新'
                result['status']['state']='connected'
            else:
                result['status']['state']='not_connected' if source_state=='not_configured' else 'error'
                result['reply_pending']=None
                result['next_action']='邮件同步尚未成功，请恢复连接后确认客户回复'
            with self.lock:
                if account!=self._account:return self._empty()
                previous=(self._state,self._error)
                self._state=result['status']['state'];self._error=result['status'].get('error')
                if self._state=='connected':self._last_success=result['status'].get('last_success_at')
                if previous!=(self._state,self._error):self.revision+=1
        if self.translator and account and result.get('messages'):
            messages=result['messages']
            if _context is None:
                selected=messages if result.get('status',{}).get('state')=='connected' else []
            else:
                incoming=[m for m in messages if m.get('direction')=='inbound' and m.get('mail_kind')!='automatic']
                selected=[max(incoming,key=lambda m:_timestamp(m.get('sent_at')) or 0)] if incoming and result.get('reply_pending') else []
            self.translator.apply(account,messages,[m.get('id') for m in selected],retry=bool(force and _context is None))
        # Persist an eligible event before exposing this reply via peek/UI.
        # The callback still runs after publication so it can read the cache.
        dispatch=self._claim_dispatch(object_id,result) if emails and result.get('status',{}).get('state')=='connected' else None
        if dispatch is not None and not dispatch[2] and dispatch[3] and dispatch[3][0]=='acknowledged':
            result['reply_pending']=False
            result['next_action']='已标记处理，可继续跟进客户'
        with self.lock:
            result['status'].update(self._authorization_details())
            old=self._cache.get(object_id)
            if old and old.get('callback_error'):result['callback_error']=old['callback_error']
            signature=lambda r: (r.get('reply_pending'),r.get('status',{}).get('state'),[(m.get('id'),m.get('direction')) for m in r.get('messages',[])])
            if old is None or signature(old)!=signature(result):self.revision+=1
            self._cache[object_id]=copy.deepcopy(result)
        self._execute_dispatch(object_id,result,dispatch)
        return self.peek(object_id)

    def acknowledge(self,object_id):
        current=self.peek(object_id)
        if current.get('reply_pending') is not True:raise ValueError('当前没有需要处理的新邮件')
        messages=[m for m in current.get('messages',[]) if m.get('direction')=='inbound' and m.get('mail_kind')!='automatic' and _timestamp(m.get('sent_at')) is not None]
        if not messages:raise ValueError('无法找到需要处理的新邮件')
        latest=max(messages,key=lambda m:_timestamp(m['sent_at']))
        with self.app.lock:
            self.app.db.execute('INSERT OR REPLACE INTO gmail_acknowledged VALUES (?,?)',(object_id,str(latest['id'])));self.app.db.commit()
        with self.lock:
            current=self._cache.get(object_id)
            if current:
                current['reply_pending']=False;current['next_action']='已标记处理，可继续跟进客户';self.revision+=1
        return self.peek(object_id)

    def _dispatch(self,object_id,context):
        self._execute_dispatch(object_id,context,self._claim_dispatch(object_id,context))

    def _claim_dispatch(self,object_id,context):
        """Choose and durably claim one eligible reply without invoking a job."""
        if not self.on_new_reply or not context.get('reply_pending'):return
        flow=self._workflow(object_id)
        if flow.get('bucket') == 'archive':return
        since=None
        if flow.get('saved_state',flow.get('state'))=='waiting_customer':
            entered=next((h.get('at') for h in reversed(flow.get('history') or []) if h.get('to')=='waiting_customer'),None)
            since=_timestamp(flow.get('waiting_since') or entered or flow.get('updated_at'))
        # Prospects and other active customers have no waiting timestamp. Treat
        # messages after Gmail was connected as new, without dispatching history.
        if since is None:since=_timestamp(self._connected_at)
        if since is None:return
        messages=context['messages']
        latest_sales=max((_timestamp(m.get('sent_at')) for m in messages if m.get('direction')=='outbound' and _timestamp(m.get('sent_at')) is not None),default=None)
        candidates=[m for m in messages if m.get('direction')=='inbound' and m.get('mail_kind')!='automatic' and m.get('id') and _timestamp(m.get('sent_at')) is not None and _timestamp(m['sent_at'])>since and (latest_sales is None or _timestamp(m['sent_at'])>latest_sales)]
        if not candidates:return
        message=max(candidates,key=lambda m:(_timestamp(m['sent_at']),str(m['id'])))
        mid=str(message['id'])
        with self.app.lock:
            now=datetime.fromtimestamp(self.clock(),timezone.utc).isoformat()
            cutoff=datetime.fromtimestamp(self.clock()-self.interval,timezone.utc).isoformat()
            # The claim must be one SQLite write, not a process-local lock or
            # SELECT followed by UPSERT: other services use their own locks.
            claim=self.app.db.execute('INSERT OR IGNORE INTO gmail_reply_events (object_id,message_id,dispatch_state,job_id,updated_at,last_error) SELECT ?,?,?,?,?,NULL WHERE NOT EXISTS (SELECT 1 FROM gmail_acknowledged WHERE object_id=? AND message_id=?)',(object_id,mid,'dispatching',None,now,object_id,mid))
            claimed=claim.rowcount==1
            if not claimed:
                # Only an explicit pre-creation deferral may be retried. A
                # conditional update makes the due claim atomic across services.
                claim=self.app.db.execute("UPDATE gmail_reply_events SET dispatch_state='dispatching',updated_at=?,last_error=NULL WHERE object_id=? AND message_id=? AND dispatch_state='deferred' AND updated_at IS NOT NULL AND updated_at<=? AND NOT EXISTS (SELECT 1 FROM gmail_acknowledged WHERE object_id=? AND message_id=?)",(now,object_id,mid,cutoff,object_id,mid))
                claimed=claim.rowcount==1
            self.app.db.commit()
            if claimed:existing=None
            elif self.app.db.execute('SELECT 1 FROM gmail_acknowledged WHERE object_id=? AND message_id=?',(object_id,mid)).fetchone():existing=('acknowledged',None)
            else:existing=self.app.db.execute('SELECT dispatch_state,job_id FROM gmail_reply_events WHERE object_id=? AND message_id=?',(object_id,mid)).fetchone()
        return message,mid,claimed,existing

    def _execute_dispatch(self,object_id,context,dispatch):
        """Run only an already-claimed callback, outside both locks."""
        if dispatch is None:return
        message,mid,claimed,existing=dispatch
        if not claimed:
            if existing and existing[0] in ('dispatching','failed','outcome_unknown','dispatched_unlinked','deferred'):
                self._dispatch_warning(object_id,deferred=existing[0]=='deferred')
            elif existing and existing[0]=='dispatched':
                if isinstance(existing[1],str) and existing[1].strip():self._clear_dispatch_warning(object_id)
                else:self._dispatch_warning(object_id)  # legacy dispatched rows predate job linkage
            elif existing and existing[0]=='acknowledged':
                self._clear_dispatch_warning(object_id)
            return
        job_id=None
        try:
            result=self.on_new_reply(object_id,copy.deepcopy(message),copy.deepcopy(context))
            job_id=result.get('id') if isinstance(result,dict) else None
            state='dispatched' if isinstance(job_id,str) and job_id.strip() else 'dispatched_unlinked'
            error=None if state=='dispatched' else '回调未返回可关联的任务ID'
        except GmailDispatchDeferred:
            state='deferred'
            error='已有工作进行中，稍后再次检查'
        except Exception as exc:
            # A callback can create a job and fail before returning its ID.
            # Never infer that it did not start, including after a restart.
            state='outcome_unknown'
            error=type(exc).__name__
        with self.app.lock:
            self.app.db.execute('UPDATE gmail_reply_events SET dispatch_state=?,job_id=?,updated_at=?,last_error=? WHERE object_id=? AND message_id=?',
                                (state,job_id if state=='dispatched' else None,datetime.fromtimestamp(self.clock(),timezone.utc).isoformat(),error,object_id,mid))
            self.app.db.commit()
        if state in ('outcome_unknown','dispatched_unlinked','deferred'):
            self._dispatch_warning(object_id,deferred=state=='deferred')
        else:
            self._clear_dispatch_warning(object_id)

    def _dispatch_warning(self,object_id,*,deferred=False):
        with self.lock:
            cached=self._cache.get(object_id)
            if cached is not None:
                note=('已有工作正在执行，客户回复已保留，稍后再次检查' if deferred else
                      '客户回复处理结果未确认，请核对原事件与任务，避免重复启动')
                if cached.get('callback_error')!=note:self.revision+=1
                cached['callback_error']=note

    def _clear_dispatch_warning(self,object_id):
        with self.lock:
            cached=self._cache.get(object_id)
            if cached and cached.get('callback_error') in ('已有工作正在执行，客户回复已保留，稍后再次检查',
                                                            '客户回复处理结果未确认，请核对原事件与任务，避免重复启动'):
                del cached['callback_error'];self.revision+=1

    def scan_once(self):
        if not self._mailbox:return self.status()
        targets=[];emails=set()
        business=self.app.business
        objects=business.mail_objects() if hasattr(business,'mail_objects') else [business.get_object(e['id']) for e in business.list_objects() if e.get('kind') in ('customer','prospect')]
        for obj in objects:
            addresses=set(self.addresses(obj))-{self._account}
            if addresses:targets.append((obj['id'],obj));emails.update(addresses)
        context={'messages':[]}
        if emails:
            try:context=self._mailbox.context(sorted(emails))
            except Exception as exc:context={'status':{'state':'error','error':'Gmail读取失败（'+type(exc).__name__+'）'},'messages':[],'reply_pending':None}
            for object_id,obj in targets:
                if self._stop.is_set():break
                try:self.customer(object_id,_context=context,_object=obj)
                except Exception:
                    with self.lock:self._state='error';self._error='部分客户邮件同步失败，请查看客户原资料与连接状态';self.revision+=1
        if hasattr(self._mailbox,'buyer_candidates') and not self._stop.is_set():
            linked=context.get('messages') or []
            found=self._mailbox.buyer_candidates(emails,{m.get('id') for m in linked})
            with self.app.lock:dismissed={row[0] for row in self.app.db.execute('SELECT message_id FROM gmail_inbox_dismissed WHERE account=?',(self._account,))}
            found['items']=[item for item in found.get('items',[]) if item.get('id') not in dismissed]
            boundary=_timestamp(self._connected_at)
            for item in found['items']:
                received=_timestamp(item.get('sent_at'))
                item['is_new']=bool(received is not None and boundary is not None and received>boundary)
            with self.lock:
                old=[(x.get('id'),x.get('summary')) for x in self._inbox.get('items',[])]
                new=[(x.get('id'),x.get('summary')) for x in found.get('items',[])]
                if old!=new or self._inbox.get('status',{}).get('state')!=found.get('status',{}).get('state'):self.revision+=1
                self._inbox=found
        return self.status()

    def start(self):
        with self.lock:
            if self._thread and self._thread.is_alive():return
            self._stop.clear()
            def run():
                while not self._stop.is_set():
                    try:self.scan_once()
                    except Exception:
                        with self.lock:self._state='error';self._error='Gmail同步未完成，请检查连接状态';self.revision+=1
                    self._stop.wait(self.interval)
            self._thread=threading.Thread(target=run,name='gmail-readonly-sync',daemon=True);self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():self._thread.join(timeout=2)
