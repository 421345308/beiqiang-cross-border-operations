"""Small local inquiry workflow. No source mutation, inferred deadlines or mail."""
from datetime import datetime,timezone
import hashlib
import json

STATES={'new':'待处理','preparing':'准备回复','waiting_customer':'等客户','internal_review':'内部评估',
        'quoting':'报价沟通','sampling':'样品推进','won':'已成交','lost':'不再推进','archived':'归档'}
PRIORITIES={'urgent':'紧急','high':'高','normal':'普通','low':'低'}
BUCKETS={'active':'当前询盘','history':'历史资料','archive':'已结束'}
ENDED={'won','lost','archived'}
GRAPH={'new':{'preparing','internal_review','quoting'},
       'preparing':{'waiting_customer','internal_review','quoting'},
       'waiting_customer':{'preparing','internal_review','quoting','sampling'},
       'internal_review':{'preparing','waiting_customer','quoting','sampling'},
       'quoting':{'preparing','waiting_customer','internal_review','sampling','won'},
       'sampling':{'preparing','waiting_customer','internal_review','quoting','won'},
       'won':{'new','preparing'},'lost':{'new','preparing'},'archived':{'new','preparing'}}

def transitions(row):
    allowed=set(GRAPH[row['state']])
    if row['state'] not in ENDED:allowed|={'lost','archived'}
    if row['bucket']=='history':allowed|=set(STATES)-ENDED
    return [{'state':key,'label':label} for key,label in STATES.items() if key in allowed and key!=row['state']]

def parse_time(value):
    if not value:return None
    if not isinstance(value,str):raise ValueError('时限须为ISO日期时间或留空')
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        return parsed.astimezone() if parsed.tzinfo is None else parsed
    except (ValueError,OverflowError):raise ValueError('时限须为有效ISO日期时间') from None

def _messages(record):
    return [m for m in (record or {}).get('messages',[]) if isinstance(m,dict) and isinstance(m.get('body'),str)]


def _message_key(message):
    # Include original content so reused IDs and legacy messages remain distinguishable.
    return hashlib.sha256(json.dumps({k:message.get(k) for k in ('id','sender','body','sentAt')},sort_keys=True).encode()).hexdigest()


def _message_time(message):
    try:return parse_time(message.get('sentAt'))
    except ValueError:return None


def decorate(object_id,source_type,saved=None,now=None,record=None):
    saved=saved or {};now=now or datetime.now(timezone.utc)
    row={'state':'new','priority':'normal','bucket':'active' if source_type in ('website','manual_import') else 'history',
         'due_at':None,'next_action':'','note':'','updated_at':None,**saved}
    if row['state'] in ENDED:row['bucket']='archive'
    messages=_messages(record)
    row['customer_reply_pending']=False
    if source_type=='website' and row['state']=='waiting_customer' and row['bucket']=='active':
        entered=next((h.get('at') for h in reversed(row.get('history') or []) if h.get('to')=='waiting_customer'),None)
        try:waiting_since=parse_time(row.get('waiting_since') or entered or row.get('updated_at'))
        except ValueError:waiting_since=None
        known=set(row.get('waiting_message_keys') or [])
        candidates=[m for m in messages if m.get('sender') in ('buyer','customer','visitor')
                    and waiting_since and _message_time(m) and _message_time(m)>waiting_since
                    and _message_key(m) not in known]
        # A later sales message already answers the customer; don't revive that reply.
        latest_sales=max((_message_time(m) for m in messages if m.get('sender') in ('sales','seller','admin','staff','assistant','us') and _message_time(m)),default=None)
        pending=[m for m in candidates if not latest_sales or _message_time(m)>latest_sales]
        if pending:
            row.update(saved_state='waiting_customer',state='new',customer_reply_pending=True,
                       saved_next_action=row.get('next_action',''),next_action='阅读客户新回复，安排后续处理',
                       customer_reply_label='客户有新回复',
                       latest_customer_reply_at=max(_message_time(m) for m in pending).isoformat())
    due=parse_time(row.get('due_at'))
    row.update(object_id=object_id,state_label=STATES[row['state']],priority_label=PRIORITIES[row['priority']],
        bucket_label=BUCKETS[row['bucket']],configured=bool(saved),excluded=source_type=='alibaba_order_buyer',
        overdue=bool(due and due<now and row['bucket']=='active' and row['state'] not in ENDED),
        allowed_transitions=transitions(row),
        pending_party=None if row['state'] in ENDED else 'customer' if row['state']=='waiting_customer' else 'internal',
        pending_label='已结束' if row['state'] in ENDED else '等客户' if row['state']=='waiting_customer' else '我方处理',
        labels={'states':dict(STATES),'priorities':dict(PRIORITIES),'buckets':dict(BUCKETS)},
        local_only=True,affects_original=False)
    return row

def update(current,body,now=None,record=None):
    if not isinstance(body,dict) or set(body)-{'state','priority','bucket','due_at','next_action','note'}:raise ValueError('不支持的询盘经营状态字段')
    if current.get('excluded'):raise ValueError('订单买家不加入询盘处理队列')
    row={key:current.get(key) for key in ('state','priority','bucket','due_at','next_action','note','updated_at')}
    row['state']=current.get('saved_state',current['state'])
    if (current.get('customer_reply_pending') or current.get('gmail_reply_pending')) and 'state' not in body:
        row['next_action']=current.get('saved_next_action','')
    row['history']=list(current.get('history') or [])
    for key in ('waiting_since','waiting_message_keys'):
        if key in current:row[key]=current[key]
    if row['state']=='waiting_customer' and not row.get('waiting_since'):
        row['waiting_since']=next((h.get('at') for h in reversed(row['history']) if h.get('to')=='waiting_customer'),None) or current.get('updated_at')
    for key in ('state','priority','bucket'):
        if key in body:
            allowed={'state':STATES,'priority':PRIORITIES,'bucket':BUCKETS}[key]
            if body[key] not in allowed:raise ValueError('询盘状态、优先级或分组无效')
            row[key]=body[key]
    if 'bucket' in body and body['bucket']=='active' and 'state' not in body and row['state'] in ENDED:row['state']='new'
    if 'state' in body and row['state'] not in ENDED and current['bucket']=='archive' and 'bucket' not in body:row['bucket']='active'
    if row['state'] in ENDED:row['bucket']='archive'
    elif row['bucket']=='archive':row['state']='archived'
    if 'state' in body and row['state'] not in {current['state'],current.get('saved_state',current['state'])} and row['state'] not in {item['state'] for item in current['allowed_transitions']}:
        raise ValueError('该状态不能直接推进，请按当前实际阶段处理或先重新打开')
    for key in ('next_action','note'):
        if key in body:
            if not isinstance(body[key],str) or len(body[key])>4000 or '\x00' in body[key]:raise ValueError('下一动作或备注过长/格式无效')
            row[key]=body[key]
    if 'due_at' in body:
        due=parse_time(body['due_at'])
        row['due_at']=due.isoformat() if due else None
    row['updated_at']=(now or datetime.now(timezone.utc)).isoformat()
    if body.get('state')=='waiting_customer':
        row['waiting_since']=row['updated_at']
        row['waiting_message_keys']=[_message_key(m) for m in _messages(record)]
    if row['state']!=current.get('saved_state',current['state']) or row['bucket']!=current['bucket']:
        row['history']=(row['history']+[{'from':current.get('saved_state',current['state']),'to':row['state'],'from_label':STATES[current.get('saved_state',current['state'])],
            'to_label':STATES[row['state']],'bucket_from':current['bucket'],'bucket_to':row['bucket'],'at':row['updated_at']}])[-20:]
    return row

def sort_key(row):
    workflow=row['workflow'];due=parse_time(workflow.get('due_at'))
    try:received=parse_time(row.get('received_at'))
    except ValueError:received=None
    return (workflow['priority']!='urgent',not workflow['overdue'],workflow['priority']!='high',
        due.timestamp() if due else float('inf'),workflow['priority']=='low',
        -received.timestamp() if received else float('inf'),row['object_id'])

def brief(analysis,cleaned):
    def clip(value,limit=240):return value[:limit-1]+'…' if isinstance(value,str) and len(value)>limit else value if isinstance(value,str) else ''
    result={key:clip(analysis.get(key,'')) for key in ('brief','core_need','intent','fit','next_action','recommended_reply')}
    if not result['core_need']:result['core_need']=clip(cleaned.get('need'))
    for key in ('missing','secondary_requests','conflicts','questions_now'):
        result[key]=[clip(value) for value in analysis.get(key,[])[:3] if isinstance(value,str)] if isinstance(analysis.get(key),list) else []
    return result


def business_summary(analysis, cleaned, workflow):
    """Business-facing projection; explicit operator action wins over AI advice."""
    summary=brief(analysis,cleaned)
    defaults={
        'new':'阅读客户需求，整理合作回复',
        'preparing':'审阅回复草稿，确认后安排回复',
        'waiting_customer':'查看客户是否回复，再安排后续跟进',
        'internal_review':'评估当前需求的承接方案',
        'quoting':'核对选款与商业条件，推进报价沟通',
        'sampling':'确认样品目的、交付内容与下一步',
    }
    action=(workflow.get('next_action') or '').strip()
    if workflow.get('gmail_reply_pending'):action=workflow.get('gmail_next_action') or '阅读客户新邮件，安排后续处理'
    elif workflow.get('customer_reply_pending'):action='阅读客户新回复，安排后续处理'
    if not action and workflow['state'] not in ENDED and workflow['bucket']!='history':
        action=summary['next_action'] or defaults.get(workflow['state'],'')
    if not action and workflow['bucket']=='history':action='查看历史资料；有当前机会时转入推进'
    return {'headline':summary['brief'] or summary['core_need'] or '尚未整理客户需求',
            'core_need':summary['core_need'], 'fit':summary['fit'],
            'next_action':action, 'questions_now':summary['questions_now'],
            'recommended_reply':summary['recommended_reply'],
            'status':workflow['state_label'],'pending_label':workflow['pending_label']}
