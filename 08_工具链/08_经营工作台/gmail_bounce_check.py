"""Bounded read-only Gmail DSN checks; never stores message bodies or credentials."""
import base64
import json
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
import re
import threading
from collections import OrderedDict
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import uuid4

from gmail_mailbox import normalize_email
from gmail_oauth import GMAIL_URL, _request as _oauth_request

MAX_PAGES = 3
PAGE_SIZE = 25
MAX_MESSAGES = 75
MAX_RAW_BYTES = 12 * 1024 * 1024
MAX_BATCH_BYTES = 16 * 1024 * 1024
BATCH_URL = 'https://www.googleapis.com/batch/gmail/v1'
MAX_CACHE_BYTES = 32 * 1024 * 1024
MAX_CACHE_ACCOUNTS = 4
_candidate_cache = OrderedDict()
_cache_lock = threading.RLock()
_account_locks = [threading.RLock() for _ in range(16)]
QUERY = ('in:anywhere {from:mailer-daemon from:postmaster '
         'subject:"delivery status notification" subject:"delivery failed" '
         'subject:"delivery failure" subject:undeliverable subject:"returned mail" '
         'subject:"address not found" subject:"mail delivery subsystem" '
         'subject:"delivery has failed" subject:"邮件退信" subject:"投递失败"}')
FAILURE = re.compile(r'(?i)(?:delivery\s+(?:has\s+)?fail(?:ed|ure)|undeliverable|'
                     r'address\s+(?:not\s+found|rejected|invalid)|invalid\s+(?:recipient|address)|'
                     r'user\s+unknown|no\s+such\s+(?:user|recipient)|'
                     r'could(?:n.t|\s+not)\s+(?:be\s+)?deliver|permanent\s+(?:error|failure)|投递失败|地址不存在|退信)')


def _batch_request(ids, *, token):
    """Official Gmail HTTP batch; only readonly GETs inside the POST envelope.

    https://developers.google.com/workspace/gmail/api/guides/batch
    Token is only on the outer request. Redirects never forward credentials.
    """
    if not ids or len(ids) > PAGE_SIZE or any(not re.fullmatch(r'[0-9a-fA-F]+', mid) for mid in ids):
        raise ValueError('invalid batch IDs')
    boundary = 'bounce_' + uuid4().hex
    chunks = []
    for mid in ids:
        chunks.append(('--' + boundary + '\r\nContent-Type: application/http\r\n'
                       'Content-ID: <bounce-' + mid + '>\r\n\r\n'
                       'GET /gmail/v1/users/me/messages/' + mid + '?format=raw HTTP/1.1\r\n'
                       'Accept: application/json\r\n\r\n').encode('ascii'))
    chunks.append(('--' + boundary + '--\r\n').encode('ascii'))
    request = Request(BATCH_URL, data=b''.join(chunks), method='POST', headers={
        'Authorization':'Bearer ' + token, 'Content-Type':'multipart/mixed; boundary=' + boundary,
        'Accept':'multipart/mixed'})
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    with build_opener(NoRedirect).open(request, timeout=30) as response:
        raw = response.read(MAX_BATCH_BYTES + 1)
        if len(raw) > MAX_BATCH_BYTES:
            raise ValueError('batch response too large')
        return {'content_type':response.headers.get('Content-Type',''), 'body':raw}


def _parse_batch(response, ids):
    """Reject incomplete/duplicate/error subresponses without trusting order."""
    if not isinstance(response,dict):
        return {}, True
    content_type, raw = response.get('content_type'), response.get('body')
    if (not isinstance(content_type,str) or '\r' in content_type or '\n' in content_type or
            not isinstance(raw,bytes) or len(raw) > MAX_BATCH_BYTES):
        return {}, True
    try:
        outer = BytesParser(policy=policy.default).parsebytes(
            ('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode('ascii') + raw)
        if outer.get_content_type() != 'multipart/mixed' or not outer.is_multipart() or outer.defects:
            return {}, True
        values, seen, duplicate = {}, set(), set()
        incomplete = False
        for part in outer.iter_parts():
            cid = str(part.get('Content-ID') or '')
            match = re.fullmatch(r'<response-bounce-([0-9a-fA-F]+)>',cid)
            if len(part.get_all('Content-ID',[])) != 1 or not match or match[1] not in ids:
                incomplete = True
                continue
            mid = match[1]
            if mid in seen:
                duplicate.add(mid)
                incomplete = True
                continue
            seen.add(mid)
            if part.defects or part.get_content_type() != 'application/http' or part.is_multipart():
                incomplete = True
                continue
            payload = part.get_payload(decode=True)
            if not isinstance(payload,bytes):
                incomplete = True
                continue
            status, separator, rest = payload.partition(b'\r\n')
            if not separator or not re.fullmatch(rb'HTTP/1\.[01] 200(?: [^\r\n]*)?',status):
                incomplete = True
                continue
            headers_raw, separator, body = rest.partition(b'\r\n\r\n')
            if not separator:
                incomplete = True
                continue
            headers = BytesParser(policy=policy.default).parsebytes(headers_raw+b'\r\n\r\n')
            if headers.defects or headers.get_content_type() != 'application/json' or len(headers.get_all('Content-Type',[])) != 1:
                incomplete = True
                continue
            lengths = headers.get_all('Content-Length',[])
            if lengths and (len(lengths) != 1 or not str(lengths[0]).isdigit() or int(lengths[0]) != len(body)):
                incomplete = True
                continue
            try:
                value = json.loads(body)
            except (ValueError,UnicodeError):
                incomplete = True
                continue
            if not isinstance(value,dict) or 'error' in value or value.get('id') != mid:
                incomplete = True
                continue
            values[mid] = value
        for mid in duplicate:
            values.pop(mid,None)
        return values, incomplete or set(values) != set(ids) or bool((outer.epilogue or '').strip())
    except (ValueError,TypeError,UnicodeError):
        return {}, True


def _exact_pattern(address):
    # Chinese prose may touch a Latin email without whitespace; Unicode \w
    # would incorrectly treat adjacent Han characters as part of the address.
    chars = r"[A-Za-z0-9_.!#$%&'*+/=?^`{|}~@-]"
    return re.compile(r'(?<!' + chars + ')' + re.escape(address) + r'(?!' + chars + ')', re.I)


def _at(message, value):
    try:
        return datetime.fromtimestamp(int(value['internalDate']) / 1000, timezone.utc).isoformat()
    except (ValueError, TypeError, KeyError, OverflowError, OSError):
        try:
            date = parsedate_to_datetime(message.get('Date', ''))
            return date.astimezone(timezone.utc).isoformat() if date.tzinfo else None
        except (ValueError, TypeError, OverflowError):
            return None


def _parse(value, address):
    """Returns blocked, clean or incomplete. Raw MIME avoids omitted DSN attachments."""
    encoded = value.get('raw') if isinstance(value, dict) else None
    if not isinstance(encoded, str) or not encoded or len(encoded) > (MAX_RAW_BYTES * 4 // 3 + 8):
        return 'incomplete', None
    try:
        raw = base64.b64decode(encoded + '=' * (-len(encoded) % 4), altchars=b'-_', validate=True)
        if len(raw) > MAX_RAW_BYTES:
            return 'incomplete', None
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except (ValueError, TypeError):
        return 'incomplete', None
    if not message.get('From') or not message.get('Subject'):
        return 'incomplete', None
    exact = _exact_pattern(address)
    incomplete = bool(message.defects)
    saw_body = False
    # Never use the returned original email as evidence that its recipient failed.
    def parts(part):
        if part.get_content_type() == 'message/rfc822':
            return
        yield part
        if part.is_multipart() and part.get_content_type() != 'message/delivery-status':
            for child in part.iter_parts():
                yield from parts(child)
    sender = getaddresses([message.get('From', '')])
    daemon = any(a.lower().split('@', 1)[0] in {'mailer-daemon', 'postmaster'} for _, a in sender)
    known_nonfailure = False
    for part in sorted(parts(message), key=lambda p:p.get_content_type() != 'message/delivery-status'):
        if part.defects:
            incomplete = True
        if part.get_content_type() == 'message/delivery-status':
            saw_body = True
            blocks = part.get_payload()
            if not isinstance(blocks, list) or not blocks:
                incomplete = True
                continue
            for block in blocks:
                recipient = str(block.get('Final-Recipient') or block.get('Original-Recipient') or '')
                if not recipient:
                    if str(block.get('Action') or '').lower() == 'failed' or str(block.get('Status') or '').startswith('5.'):
                        incomplete = True
                    continue
                if not exact.search(recipient):
                    continue
                action = str(block.get('Action') or '').strip().lower()
                status = str(block.get('Status') or '').strip()
                if action == 'failed' or re.match(r'^5\.\d+\.\d+', status):
                    return 'blocked', _at(message, value)
                if action in {'delivered', 'relayed', 'expanded', 'delayed'} or status.startswith(('2.', '4.')):
                    known_nonfailure = True
                if action not in {'delivered', 'relayed', 'expanded', 'delayed'} and not status.startswith(('2.', '4.')):
                    incomplete = True
        elif part.get_content_type() == 'text/plain' and not part.get_filename():
            try:
                body = part.get_content()
            except (ValueError, LookupError, UnicodeError):
                incomplete = True
                continue
            if not isinstance(body, str) or '\ufffd' in body:
                incomplete = True
                continue
            saw_body = saw_body or bool(body.strip())
            # A clear daemon diagnostic must name this exact recipient on the
            # same line; unrelated recipients and quoted original mail do not count.
            for line in body.splitlines():
                if re.search(r'(?i)(?:original\s+message|message\s+header\s+follows|forwarded\s+message)', line):
                    break
                if line.lstrip().startswith('>'):
                    continue
                if daemon and not known_nonfailure and exact.search(line) and FAILURE.search(line):
                    if not re.search(r'(?i)\b(?:temporar\w*|delay\w*|retry\w*|retrying|not\s+(?:a\s+)?(?:bounce|invalid|undeliverable)|no\s+(?:bounce|delivery failure)|successfully\s+delivered)\b', line):
                        return 'blocked', _at(message, value)
            if not known_nonfailure and exact.search(body) and FAILURE.search(body):
                # The address and failure may describe different recipients or
                # span a multi-line diagnostic; absence of proof is not a clean bill.
                incomplete = True
    return ('incomplete' if incomplete or not saw_body else 'clean'), None


def _check_bounces_uncached(mailbox, address, *, batch_request=None, token=None, candidates=None):
    """Check one exact address in one authorized account; no send/modify calls.

    clear means only this bounded candidate query completed without a matching
    failure. It never asserts deliverability or absence of bounces elsewhere.
    """
    checked = datetime.now(timezone.utc).isoformat()
    coverage = {'provider': 'gmail_oauth', 'scope': 'single_account_in_anywhere_dsn_candidates',
                'complete': False, 'candidate_transport_complete': False, 'pages': 0, 'messages_checked': 0,
                'max_pages': MAX_PAGES, 'max_messages': MAX_MESSAGES,
                'other_accounts_checked': False, 'deliverability_verified': False}
    result = {'status': 'unknown', 'checked_at': checked, 'coverage': coverage, 'events': []}
    try:
        address = normalize_email(address)
        # Restrict the strict address parser before using it in a diagnostic regex.
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}", address):
            raise ValueError('address')
    except ValueError:
        return {**result, 'reason': 'invalid_address'}
    if not callable(getattr(mailbox, '_access_token', None)) or not callable(getattr(mailbox, 'request', None)):
        return {**result, 'reason': 'gmail_oauth_required_imap_not_supported'}
    incomplete = False
    transport_incomplete = False
    seen = set()
    page_token = None
    page_tokens = set()
    # Existing injected request stubs keep their established readonly interface;
    # the production OAuth transport uses batch by default. Tests/alternate
    # transports may explicitly inject the same batch envelope contract.
    batch_transport = batch_request or (_batch_request if mailbox.request is _oauth_request else None)
    coverage['message_transport'] = 'official_http_batch' if batch_transport else 'injected_single_request'
    coverage['batch_requests'] = 0
    try:
        token = token if token is not None else mailbox._access_token()
        for _ in range(MAX_PAGES):
            params = {'q': QUERY, 'maxResults': PAGE_SIZE, 'includeSpamTrash': 'true'}
            if page_token:
                params['pageToken'] = page_token
            listing = mailbox.request(GMAIL_URL + 'messages?' + urlencode(params), token=token)
            coverage['pages'] += 1
            if not isinstance(listing, dict) or 'error' in listing:
                raise ValueError('listing')
            rows = listing.get('messages', [])
            if not isinstance(rows, list):
                raise ValueError('messages')
            if not rows and listing.get('resultSizeEstimate', 0) and not listing.get('nextPageToken'):
                incomplete = True
                transport_incomplete = True
            ids = []
            for row in rows:
                mid = row.get('id') if isinstance(row, dict) else None
                if not isinstance(mid, str) or not re.fullmatch(r'[0-9a-fA-F]+', mid):
                    incomplete = True
                    transport_incomplete = True
                    continue
                if mid in seen:
                    continue
                if len(seen) >= MAX_MESSAGES:
                    incomplete = True
                    transport_incomplete = True
                    break
                seen.add(mid)
                ids.append(mid)
            values = {}
            if batch_transport:
                # A defensive chunk also handles a provider returning more than
                # maxResults; limits and incomplete semantics remain unchanged.
                for offset in range(0,len(ids),PAGE_SIZE):
                    chunk = ids[offset:offset+PAGE_SIZE]
                    coverage['batch_requests'] += 1
                    try:
                        loaded, partial = _parse_batch(batch_transport(chunk,token=token),chunk)
                        values.update(loaded)
                        incomplete = incomplete or partial
                        transport_incomplete = transport_incomplete or partial
                    except Exception:
                        incomplete = True
                        transport_incomplete = True
            else:
                for mid in ids:
                    values[mid] = mailbox.request(GMAIL_URL + 'messages/' + mid + '?format=raw', token=token)
            for mid in ids:
                value = values.get(mid)
                if not isinstance(value, dict) or value.get('id') != mid or not isinstance(value.get('raw'),str) or not value.get('raw'):
                    incomplete = True
                    transport_incomplete = True
                    continue
                if candidates is not None:
                    candidates.append({k:value[k] for k in ('id','raw','internalDate') if k in value})
                status, at = _parse(value, address)
                coverage['messages_checked'] += 1
                if status == 'blocked':
                    result['events'].append({'id': mid, 'at': at})
                elif status == 'incomplete':
                    incomplete = True
            page_token = listing.get('nextPageToken')
            if not page_token:
                coverage['complete'] = not incomplete
                coverage['candidate_transport_complete'] = not transport_incomplete
                break
            if not isinstance(page_token, str) or page_token in page_tokens:
                incomplete = True
                transport_incomplete = True
                break
            page_tokens.add(page_token)
        else:
            incomplete = bool(page_token) or incomplete
    except Exception:
        incomplete = True
        result['reason'] = 'gmail_query_or_message_read_failed'
    if result['events']:
        result['status'] = 'blocked'
        result['reason'] = 'exact_recipient_delivery_failure_found'
    elif coverage['complete'] and not incomplete:
        result['status'] = 'clear'
        result['reason'] = 'no_exact_recipient_failure_in_this_account_query'
    else:
        result.setdefault('reason', 'bounded_query_or_message_content_incomplete')
    return result


def _native_unknown(reason):
    return {'status':'unknown','checked_at':datetime.now(timezone.utc).isoformat(),'events':[],
        'reason':reason,'coverage':{'provider':'gmail_oauth',
            'scope':'single_account_in_anywhere_dsn_candidates','complete':False,
            'candidate_transport_complete':False,
            'pages':0,'messages_checked':0,'max_pages':MAX_PAGES,'max_messages':MAX_MESSAGES,
            'message_transport':'official_http_batch','batch_requests':0,
            'other_accounts_checked':False,'deliverability_verified':False,'candidate_cache':'unavailable'}}


def _profile(mailbox, token, account):
    value=mailbox.request(GMAIL_URL+'profile',token=token)
    if (not isinstance(value,dict) or normalize_email(value.get('emailAddress'))!=account or
            not re.fullmatch(r'\d+',str(value.get('historyId') or ''))):
        raise ValueError('mailbox observation incomplete')
    return str(value['historyId'])


def _store_candidates(account, history, candidates, coverage):
    # Only readonly message data is retained; tokens and credentials never enter
    # the cache. Account count and total raw payload bytes are both bounded.
    size=sum(len(json.dumps(v,ensure_ascii=True).encode('ascii')) for v in candidates)
    with _cache_lock:
        _candidate_cache.pop(account,None)
        if size>MAX_CACHE_BYTES:return False
        while _candidate_cache and (len(_candidate_cache)>=MAX_CACHE_ACCOUNTS or
                sum(v['size'] for v in _candidate_cache.values())+size>MAX_CACHE_BYTES):
            _candidate_cache.popitem(last=False)
        _candidate_cache[account]={'history':history,'messages':candidates,'coverage':dict(coverage),'size':size}
        return True


def check_bounces(mailbox, address, *, batch_request=None):
    """Exact per-address analysis over bounded native OAuth DSN candidates.

    Candidate reuse is process-local only, guarded by matching official account
    and before/after historyId observations. Injected request transports retain
    their established uncached interface, avoiding accidental real HTTP in tests.
    """
    if getattr(mailbox,'request',None) is not _oauth_request:
        return _check_bounces_uncached(mailbox,address,batch_request=batch_request)
    try:
        address=normalize_email(address)
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}",address):
            raise ValueError('invalid address')
        account=normalize_email(getattr(mailbox,'account_email',''))
    except ValueError:
        return _native_unknown('invalid_address_or_mailbox_identity')
    # Stable stripes bound lock memory and serialize every refresh/publication
    # for the same account, including independent mailbox service instances.
    with _account_locks[hash(account)%len(_account_locks)]:
        try:
            token=mailbox._access_token()
            before=_profile(mailbox,token,account)
            with _cache_lock:
                cached=_candidate_cache.get(account)
                if cached and cached['history']!=before:
                    _candidate_cache.pop(account,None)
                    cached=None
            if cached:
                result={'status':'clear','checked_at':datetime.now(timezone.utc).isoformat(),'events':[],
                        'coverage':dict(cached['coverage'])}
                # Transfer completeness is shared; semantic completeness is
                # recomputed independently for this address on every call.
                result['coverage'].update(candidate_cache='hit',batch_requests=0,complete=True)
                for value in cached['messages']:
                    state,at=_parse(value,address)
                    if state=='blocked':result['events'].append({'id':value['id'],'at':at})
                    elif state=='incomplete':result['coverage']['complete']=False
                if result['events']:
                    result.update(status='blocked',reason='exact_recipient_delivery_failure_found')
                elif not result['coverage']['complete']:
                    result.update(status='unknown',reason='bounded_query_or_message_content_incomplete')
                else:result['reason']='no_exact_recipient_failure_in_this_account_query'
                candidates=cached['messages']
            else:
                candidates=[]
                result=_check_bounces_uncached(mailbox,address,batch_request=batch_request,token=token,candidates=candidates)
                result['coverage']['candidate_cache']='refresh'
            after=_profile(mailbox,token,account)
            result['coverage'].update(history_id_before=before,history_id_after=after)
            if before!=after:
                with _cache_lock:_candidate_cache.pop(account,None)
                result['coverage']['complete']=False
                if result['status']=='clear':result['status']='unknown'
                result['reason']='mailbox_changed_during_bounce_check'
                return result
            if not cached and result['coverage']['candidate_transport_complete']:
                result['coverage']['cache_stored']=_store_candidates(account,after,candidates,result['coverage'])
            return result
        except Exception:
            # Even an old successful cache is not usable when the current
            # identity/watermark read fails. No hidden fallback or blind clear.
            with _cache_lock:_candidate_cache.pop(account,None)
            return _native_unknown('mailbox_watermark_or_query_failed')
