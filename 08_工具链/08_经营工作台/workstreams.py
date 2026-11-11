"""Read-through views of business entries and explicitly linked conversations.

Workstreams are projections, not tasks or a second source of business facts.
No relationship is inferred from a title, object name, or similar wording.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re


def _now():
    return datetime.now(timezone.utc).isoformat()


_SPECS = (
    ('tools', '总控与工具', '工作台、受控任务与接续', '经营工作台业务入口',
     '08_工具链/08_经营工作台/README.md'),
    ('alibaba', '国际站运营', '国际站经营、选款及商品验收', '国际站经营诊断',
     '02_Alibaba运营/01_店铺与全店诊断/店铺经营诊断.md'),
    ('website', '独立站增长', '独立站产品与国际站对齐', '独立站项目入口',
     '03_独立站/README.md'),
    ('outreach', '外贸开发', '精准开发与逐封审核', '客户开发业务入口',
     '04_客户开发/README.md'),
)

_DIRECTION_IDS = {'国际 B2B': 'international', '国内抖店': 'domestic', '内容与创作': 'creation'}
_DIRECTION_PATH = '00_总控台/当前状态.md'


def _excerpt(text, limit=800):
    """Render a bounded excerpt of the source, not a newly asserted fact."""
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'[`*]', '', text)
    text = re.sub(r'^\s*[-#]+\s*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + '…（原文节选）'


def _read_entry(root, relative):
    """Read one unchanged, bounded workspace source and retain its modification time."""
    reason = '原业务档案不可读取。'
    try:
        root = Path(root).resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return None, None, reason
        before = path.stat()
        if before.st_size > 2_000_000:
            return None, None, '原业务档案超过读取上限。'
        with path.open('rb') as source:
            content = source.read(2_000_001)
        if len(content) > 2_000_000:
            return None, None, '原业务档案超过读取上限。'
        content = content.decode('utf-8-sig')
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            return None, None, '原业务档案正在更新，请重新读取。'
        modified = datetime.fromtimestamp(after.st_mtime, timezone.utc).isoformat()
        return content, modified, ''
    except (OSError, UnicodeError, ValueError):
        return None, None, reason


def _unique_field(lines, name):
    prefixes = (f'**{name}：**', f'{name}：')
    values = [line.strip().removeprefix(prefix).strip() for line in lines for prefix in prefixes
              if line.strip().startswith(prefix)]
    return values[0] if len(values) == 1 else ''


def _structured_workstream(lines):
    """Use only an explicit, unambiguous current-state block if one exists."""
    headings = [i for i, line in enumerate(lines) if line.strip() == '## 工作线当前状态']
    if len(headings) != 1:
        return None
    block = []
    for line in lines[headings[0] + 1:]:
        if re.match(r'^#{1,2}\s+', line.strip()):
            break
        block.append(line)
    fields = {}
    for name in ('当前工作', '已验证结果', '下一步', '阻塞'):
        prefixes = (f'**{name}：**', f'{name}：')
        values = [line.strip().removeprefix(prefix).strip() for line in block for prefix in prefixes
                  if line.strip().startswith(prefix)]
        if len(values) > 1:
            return None
        fields[name] = values[0] if values else ''
    return fields if any(fields.values()) else None


def _source(root, name, relative):
    observed = _now()
    result = {'label': name, 'observed_at': observed, 'modified_at': None,
              'state': 'unavailable', 'focus': '', 'result': '', 'next_action': '', 'blocker': '',
              'path': relative, 'reason': '原业务档案不可读取。'}
    content, modified, reason = _read_entry(root, relative)
    if content is None:
        result['reason'] = reason
        return result
    result['modified_at'] = modified
    lines = content.splitlines()
    fields = _structured_workstream(lines)
    if fields is None:
        result.update(state='unknown', read_state='ok',
                      reason='业务来源可读，但没有明确、唯一的结构化当前状态；请查看原业务入口或已关联任务。')
        return result
    focus, evidence = fields['当前工作'], fields['已验证结果']
    next_action, blocker = fields['下一步'], fields['阻塞']
    result.update(state='ok', reason='', focus=_excerpt(focus), result=_excerpt(evidence),
                  next_action=_excerpt(next_action), blocker=_excerpt(blocker))
    return result


def _direction_rows(root, snapshot, jobs, jobs_available=True):
    """Read the global direction table without treating goals as task outcomes."""
    observed = _now()
    content, modified, reason = _read_entry(root, _DIRECTION_PATH)
    def unavailable(why):
        source = {'label':'总控方向与长期目标', 'path':_DIRECTION_PATH, 'state':'unknown',
                  'observed_at':observed, 'modified_at':modified, 'reason':why,
                  'focus':'', 'result':'', 'next_action':'', 'blocker':'', 'scope':'direction_registry'}
        return [{'id':'direction-registry-unavailable', 'title':'经营方向', 'focus':'经营方向暂不可读',
                 'source':source, 'conversation':None, 'related_jobs':[]}]
    if content is None:
        # Test or partial workspaces may have no global directory at all.
        return unavailable(reason) if (Path(root) / '00_总控台').is_dir() else []
    lines = content.splitlines()
    header = next((i for i, line in enumerate(lines)
                   if [cell.strip() for cell in line.strip().strip('|').split('|')] ==
                      ['方向', '长期结果', '看什么判断进展']), None)
    if header is None or header + 1 >= len(lines):
        return unavailable('业务来源可读，但没有可识别的方向表。')
    separator = lines[header + 1].strip()
    if not re.fullmatch(r'\|?(?:\s*:?-{3,}:?\s*\|){2}\s*:?-{3,}:?\s*\|?', separator):
        return unavailable('业务来源可读，但方向表结构无法确认。')
    rows = []
    for line in lines[header + 2:]:
        if not line.strip().startswith('|'):
            break
        columns = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(columns) != 3 or not all(columns):
            continue
        title, goal, metric = columns
        if title == '共同工作能力':  # Already represented by the existing tools row.
            continue
        key = _DIRECTION_IDS.get(title) or 'direction-' + sha256(title.encode('utf8')).hexdigest()[:16]
        duplicate = next((row for row in rows if row['id'] == key), None)
        if duplicate:
            duplicate.update(focus='方向重复登记，请核对总控原表。', conversation=None, related_jobs=[])
            duplicate['source'].update(state='unknown', reason='方向名称重复，不能判断对应目标。',
                                       focus='', long_term_goal='', progress_measure='')
            duplicate['related_jobs_observation'] = {'state':'ambiguous', 'reason':'方向重复，未关联任务。',
                                                     'source':'AgentJobs', 'observed_at':observed}
            continue
        current_direction = (_unique_field(lines, '海外 B2B 现行方向') if key == 'international' else '')
        focus = ('现行方向（原文摘录）：' + current_direction if current_direction else
                 '长期目标（不代表当前进度）：' + goal)
        source = {'label':'总控方向与长期目标', 'path':_DIRECTION_PATH, 'state':'ok',
                  'observed_at':observed, 'modified_at':modified, 'reason':'',
                  'focus':_excerpt(focus), 'result':'', 'next_action':'', 'blocker':'',
                  'scope':'direction_only', 'long_term_goal':_excerpt(goal), 'progress_measure':_excerpt(metric)}
        conversation = _conversation(key, snapshot)
        related, link_observation = _related_jobs(jobs, conversation.get('host_id') if conversation else None,
                                                 conversation.get('id') if conversation else None)
        if not jobs_available:
            link_observation.update(state='unavailable', reason='AgentJobs 不可读，无法核对关联任务。')
        rows.append({'id':key, 'title':_excerpt(title, 120), 'focus':source['focus'], 'source':source,
                     'conversation':conversation, 'related_jobs':related,
                     'related_jobs_observation':link_observation})
    return rows


def _valid_host_bound_reference(ref):
    host = ref.get('host_id')
    if not isinstance(host, str) or not host.strip() or ref.get('control') != 'reference_only':
        return False
    try:
        bound_at = datetime.fromisoformat(ref['host_bound_at'].replace('Z', '+00:00'))
        return bound_at.tzinfo is not None and bound_at.utcoffset() is not None
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError):
        return False


def _related_jobs(jobs, host_id, thread_id):
    """Join only an unambiguous, explicitly host-bound reference-only link."""
    observation = {'state':'unregistered', 'reason':'未登记唯一的主机和会话引用。',
                   'source':'AgentJobs', 'observed_at':_now()}
    if not isinstance(host_id, str) or not host_id or not isinstance(thread_id, str) or not thread_id:
        return [], observation
    candidates = []
    ambiguous = False
    for job in jobs:
        if not isinstance(job, dict):
            ambiguous = True
            continue
        job_id = job.get('id')
        references = job.get('conversations', [])
        if references is None:
            references = []
        if not isinstance(references, list):
            ambiguous = True
            continue
        matching = [ref for ref in references if isinstance(ref, dict) and ref.get('provider') == 'codex'
                    and ref.get('conversation_id') == thread_id]
        if any(not _valid_host_bound_reference(ref) for ref in matching):
            ambiguous = True
        bound = [ref for ref in matching if ref.get('host_id') == host_id]
        if bound:
            if (len(matching) != 1 or len(bound) != 1 or not _valid_host_bound_reference(bound[0]) or
                    not isinstance(job_id, str) or not job_id):
                ambiguous = True
                continue
            candidates.append((job, bound[0]))
        elif job.get('session_id') == thread_id:
            # A bare local session id does not establish its desktop host.
            ambiguous = True
    if ambiguous or len(candidates) > 1:
        observation.update(state='ambiguous', reason='会话主机未绑定、引用重复或归属不唯一；未关联任务。')
        return [], observation
    if not candidates:
        observation.update(state='not_linked', reason='没有同主机、同会话的明确任务引用。')
        return [], observation
    job, ref = candidates[0]
    observation.update(state='ok', reason='')
    return [{'id': 'local:' + job['id'], 'title': job.get('title') or '本机任务',
             'status': job.get('status') or 'unknown', 'result':job.get('summary') or '',
             'next_action':job.get('next_action') or '', 'blocker':job.get('error') or '',
             'updated_at':job.get('updated_at'), 'observed_at':observation['observed_at'],
             'source':'AgentJobs', 'relation':'conversation_ref', 'host_id':host_id,
             'thread_id':thread_id, 'host_bound_at':ref['host_bound_at']}], observation


def _batch_work(jobs, batches, jobs_available=True):
    """Join jobs only through a readable batch ID and current object membership."""
    observed = _now()
    observation = {'state':'unavailable', 'source':'客户开发批次与 AgentJobs', 'observed_at':observed,
                   'reason':'客户批次关联资料不可读，不能判断批次任务。'}
    if not isinstance(batches, list):
        return [], [], observation
    indexed = {}
    for batch in batches:
        if not isinstance(batch, dict):
            return [], [], observation
        key, members = batch.get('id'), batch.get('object_ids')
        if (not isinstance(key, str) or not key or key in indexed or not isinstance(members, list)
                or any(not isinstance(oid, str) or not oid for oid in members) or len(set(members)) != len(members)):
            return [], [], observation
        indexed[key] = batch
    rows = [{'id':key, 'title':batch.get('title') or '客户开发批次', 'count':len(batch['object_ids']),
             'updated_at':batch.get('updated_at'), 'observed_at':observed, 'source':'客户开发批次'}
            for key, batch in indexed.items()]
    if not jobs_available:
        observation.update(state='partial', reason='AgentJobs 不可读，批次关联任务状态未知。')
        return rows, [], observation
    id_counts = {}
    for job in jobs:
        if isinstance(job, dict) and isinstance(job.get('id'), str) and job['id']:
            id_counts[job['id']] = id_counts.get(job['id'], 0) + 1
    related, incomplete = [], False
    for job in jobs:
        if not isinstance(job, dict) or not job.get('batch_id'):
            continue
        batch_id, job_id = job.get('batch_id'), job.get('id')
        if (not isinstance(batch_id, str) or batch_id not in indexed or
                not isinstance(job_id, str) or not job_id or id_counts[job_id] != 1 or
                job.get('object_id') not in indexed[batch_id]['object_ids']):
            incomplete = True
            continue
        related.append({'id':'local:' + job_id, 'title':job.get('title') or '本机任务',
                        'status':job.get('status') or 'unknown', 'result':job.get('summary') or '',
                        'next_action':job.get('next_action') or '', 'blocker':job.get('error') or '',
                        'artifact_id':job.get('artifact_id'), 'batch_id':batch_id,
                        'updated_at':job.get('updated_at'), 'observed_at':observed,
                        'source':'AgentJobs', 'relation':'customer_batch_membership'})
    observation.update(state='partial' if incomplete else 'ok',
                       reason='部分批次任务关联缺失或不明确，未展示。' if incomplete else '')
    return rows, related, observation


def _conversation(key, snapshot):
    links = [link for link in snapshot.get('workstream_links', [])
             if isinstance(link, dict) and link.get('workstream') == key]
    if len(links) != 1:
        return None
    link = links[0]
    host, thread_id = link.get('host_id'), link.get('thread_id')
    if not isinstance(host, str) or not host or not isinstance(thread_id, str) or not thread_id:
        return None
    matches = [row for row in snapshot.get('threads', []) if isinstance(row, dict)
               and row.get('hostId') == host and row.get('id') == thread_id]
    individual = matches[0].get('individual_observation') if len(matches) == 1 else None
    if not isinstance(individual, dict):
        individual = None
    freshness = individual.get('state') if individual else snapshot.get('state', 'missing')
    if freshness not in ('ok', 'stale', 'unavailable', 'missing'):
        freshness = 'unavailable'
    if len(matches) != 1:
        freshness = 'missing'
    row = matches[0] if len(matches) == 1 else {}
    observed_at = (individual.get('observed_at') if individual else
                   snapshot.get('snapshot_observed_at') or snapshot.get('observed_at')) if row else None
    attempted_at = (individual.get('attempted_at') if individual else
                    snapshot.get('observed_at')) if row else None
    status = row.get('status') or 'unknown'
    return {'id': thread_id, 'host_id': host, 'title': row.get('title') or '已登记会话',
            'state': freshness, 'observed_status': status, 'last_observed_status': status,
            'observed_at': observed_at, 'attempted_at': attempted_at,
            'updated_at': row.get('updatedAt'),
            'source': individual.get('source') if individual else snapshot.get('source'),
            'attempt_source': individual.get('attempt_source') if individual else snapshot.get('source'),
            'observation_scope': individual.get('value_scope') if individual else 'complete_snapshot',
            'registration_state': link.get('registration_state') or ('present_in_snapshot' if row else 'not_in_latest_snapshot'),
            'association_source': link.get('source_note'), 'associated_at': link.get('linked_at'),
            'control': 'reference_only'}


def build_workstreams(root, jobs, desktop_snapshot, customer_batches=None, jobs_available=True):
    """Project existing workstream entries and separately labelled business directions."""
    jobs = jobs if isinstance(jobs, list) else []
    snapshot = desktop_snapshot if isinstance(desktop_snapshot, dict) else {}
    output = []
    for key, title, focus, label, path in _SPECS:
        conversation = _conversation(key, snapshot)
        source = _source(root, label, path)
        batches, batch_observation = [], None
        if key == 'outreach':
            # A conversation identifies a reference, not the customer to whom
            # a job belongs. Only the explicit batch/member join can attach it.
            batches, related, batch_observation = _batch_work(jobs, customer_batches, jobs_available)
            link_observation = dict(batch_observation)
            if not jobs_available:
                link_observation['state'] = 'unavailable'
            elif batch_observation['state'] == 'unavailable':
                link_observation['state'] = 'unknown'
            elif batch_observation['state'] == 'partial':
                link_observation['state'] = 'ambiguous'
            else:
                link_observation['state'] = 'ok' if related else 'not_linked'
        else:
            related, link_observation = _related_jobs(jobs, conversation.get('host_id') if conversation else None,
                                                     conversation.get('id') if conversation else None)
            if not jobs_available:
                link_observation.update(state='unavailable', reason='AgentJobs 不可读，无法核对关联任务。')
        displayed_focus = source.get('focus') or (focus if source.get('state') == 'ok' else '当前工作未登记')
        output.append({'id': key, 'title': title, 'focus': displayed_focus,
                       'source': source,
                       'conversation': conversation, 'related_jobs':related,
                       'related_jobs_observation':link_observation,
                       **({'related_batches':batches, 'batch_observation':batch_observation} if key == 'outreach' else {})})
    return output + _direction_rows(root, snapshot, jobs, jobs_available)
