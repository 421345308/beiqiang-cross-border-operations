"""Read-through views of business entries and explicitly linked conversations.

Workstreams are projections, not tasks or a second source of business facts.
No relationship is inferred from a title, object name, or similar wording.
"""
from datetime import datetime, timezone
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
)


def _excerpt(text, limit=800):
    """Render a bounded excerpt of the source, not a newly asserted fact."""
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'[`*]', '', text)
    text = re.sub(r'^\s*[-#]+\s*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + '…（原文节选）'


def _line(lines, prefix):
    return next((line.strip() for line in lines if line.strip().startswith(prefix)), '')


def _sentence(line, marker):
    start = line.find(marker)
    if start < 0:
        return ''
    end = line.find('。', start)
    return line[start:end + 1] if end >= 0 else line[start:]


def _source(root, name, relative, key):
    observed = _now()
    result = {'label': name, 'observed_at': observed, 'modified_at': None,
              'state': 'unavailable', 'focus': '', 'result': '', 'next_action': '', 'blocker': '',
              'path': relative, 'reason': '原业务档案不可读取。'}
    try:
        root = Path(root).resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return result
        before = path.stat()
        if before.st_size > 2_000_000:
            result['reason'] = '原业务档案超过读取上限。'
            return result
        with path.open('rb') as source:
            content = source.read(2_000_001)
        if len(content) > 2_000_000:
            result['reason'] = '原业务档案超过读取上限。'
            return result
        content = content.decode('utf-8-sig')
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            result['reason'] = '原业务档案正在更新，请重新读取。'
            return result
        result['modified_at'] = datetime.fromtimestamp(after.st_mtime, timezone.utc).isoformat()
    except (OSError, UnicodeError, ValueError):
        return result
    lines = content.splitlines()
    if key == 'tools':
        focus = _line(lines, '**总控当前工作：**').removeprefix('**总控当前工作：**').strip()
        evidence = _line(lines, '**总控已验证结果：**').removeprefix('**总控已验证结果：**').strip()
        next_action = _line(lines, '**总控下一步：**').removeprefix('**总控下一步：**').strip()
        blocker = _line(lines, '**总控阻塞：**').removeprefix('**总控阻塞：**').strip()
    elif key == 'alibaba':
        focus = ''
        evidence = _line(lines, '本轮研究七号仓库')
        next_action = _line(lines, '负责人要求优先使用真实适配的现有鞋靴类目')
        blocker = _sentence(evidence, '11月11日授权后')
    else:
        focus = ''
        evidence = _line(lines, '**持续推进：国际站与独立站产品对齐')
        next_action = _sentence(evidence, '继续逐款')
        blocker = ''
    if not evidence or not next_action or (key != 'website' and not blocker) or (key == 'tools' and not focus):
        result['reason'] = '原业务档案结构或所需段落已变化，请查看业务入口。'
        return result
    result.update(state='ok', reason='', focus=_excerpt(focus), result=_excerpt(evidence),
                  next_action=_excerpt(next_action), blocker=_excerpt(blocker))
    return result


def _related_jobs(jobs, thread_id):
    if not thread_id:
        return []
    related = []
    for job in jobs:
        job_id = job.get('id')
        if not isinstance(job_id, str) or not job_id:
            continue
        session = job.get('session_id') == thread_id
        references = job.get('conversations') or []
        explicit = any(isinstance(ref, dict) and ref.get('provider') == 'codex'
                       and ref.get('conversation_id') == thread_id for ref in references)
        if session or explicit:
            related.append({'id': 'local:' + job_id, 'title': job.get('title') or '本机任务',
                            'status': job.get('status') or 'unknown',
                            'relation': 'session_id' if session else 'conversation_ref'})
    return related


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


def build_workstreams(root, jobs, desktop_snapshot):
    """Project current source excerpts and explicit references into three rows."""
    jobs = jobs if isinstance(jobs, list) else []
    snapshot = desktop_snapshot if isinstance(desktop_snapshot, dict) else {}
    output = []
    for key, title, focus, label, path in _SPECS:
        conversation = _conversation(key, snapshot)
        source = _source(root, label, path, key)
        output.append({'id': key, 'title': title, 'focus': source.get('focus') or focus,
                       'source': source,
                       'conversation': conversation,
                       'related_jobs': _related_jobs(jobs, conversation['id'] if conversation else None)})
    return output
