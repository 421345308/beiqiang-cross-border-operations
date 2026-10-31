"""Small local inquiry workflow. No source mutation, inferred deadlines or mail."""
from datetime import datetime,timezone

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

def decorate(object_id,source_type,saved=None,now=None):
    saved=saved or {};now=now or datetime.now(timezone.utc)
    row={'state':'new','priority':'normal','bucket':'active' if source_type in ('website','manual_import') else 'history',
         'due_at':None,'next_action':'','note':'','updated_at':None,**saved}
    if row['state'] in ENDED:row['bucket']='archive'
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

def update(current,body,now=None):
    if not isinstance(body,dict) or set(body)-{'state','priority','bucket','due_at','next_action','note'}:raise ValueError('不支持的询盘经营状态字段')
    if current.get('excluded'):raise ValueError('订单买家不加入询盘处理队列')
    row={key:current.get(key) for key in ('state','priority','bucket','due_at','next_action','note','updated_at')}
    row['history']=list(current.get('history') or [])
    for key in ('state','priority','bucket'):
        if key in body:
            allowed={'state':STATES,'priority':PRIORITIES,'bucket':BUCKETS}[key]
            if body[key] not in allowed:raise ValueError('询盘状态、优先级或分组无效')
            row[key]=body[key]
    if 'bucket' in body and body['bucket']=='active' and 'state' not in body and row['state'] in ENDED:row['state']='new'
    if 'state' in body and row['state'] not in ENDED and current['bucket']=='archive' and 'bucket' not in body:row['bucket']='active'
    if row['state'] in ENDED:row['bucket']='archive'
    elif row['bucket']=='archive':row['state']='archived'
    if row['state']!=current['state'] and row['state'] not in {item['state'] for item in current['allowed_transitions']}:
        raise ValueError('该状态不能直接推进，请按当前实际阶段处理或先重新打开')
    for key in ('next_action','note'):
        if key in body:
            if not isinstance(body[key],str) or len(body[key])>4000 or '\x00' in body[key]:raise ValueError('下一动作或备注过长/格式无效')
            row[key]=body[key]
    if 'due_at' in body:
        due=parse_time(body['due_at'])
        row['due_at']=due.isoformat() if due else None
    row['updated_at']=(now or datetime.now(timezone.utc)).isoformat()
    if row['state']!=current['state'] or row['bucket']!=current['bucket']:
        row['history']=(row['history']+[{'from':current['state'],'to':row['state'],'from_label':STATES[current['state']],
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
