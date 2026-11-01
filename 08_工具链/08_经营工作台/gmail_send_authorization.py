"""Explicitly granted, refreshable Gmail send access in the OS credential store.

This module does not compose or send messages. Every outbound message still
requires the owner's approval of the recipient, body and actual attachment.
"""
from datetime import datetime, timezone
import json

from gmail_mailbox import normalize_email
from gmail_oauth import GMAIL_URL, TOKEN_URL, _request

READ_SCOPE='https://www.googleapis.com/auth/gmail.readonly'
SEND_SCOPE='https://www.googleapis.com/auth/gmail.send'
SEND_SERVICE='Beiqiang.Workdesk.GmailOAuth.Send'
REQUIRED_SCOPES={READ_SCOPE,SEND_SCOPE}


def _read(account):
    import keyring
    data=keyring.get_password(SEND_SERVICE,normalize_email(account))
    return json.loads(data) if data else None


def _write(account,value):
    import keyring
    keyring.set_password(SEND_SERVICE,normalize_email(account),json.dumps(value))


def _scopes(value):
    return set(value.split() if isinstance(value,str) else value or [])


def _refresh_and_check(account,saved,request):
    if not saved or not saved.get('client_id') or not saved.get('refresh_token'):
        raise ValueError('尚未保存 Gmail 发送授权')
    if not REQUIRED_SCOPES.issubset(_scopes(saved.get('scopes'))):
        raise ValueError('保存的 Gmail 发送授权范围不足')
    form={'client_id':saved['client_id'],'refresh_token':saved['refresh_token'],'grant_type':'refresh_token'}
    if saved.get('client_secret'):form['client_secret']=saved['client_secret']
    result=request(TOKEN_URL,form=form)
    if not result.get('access_token') or not REQUIRED_SCOPES.issubset(_scopes(result.get('scope'))):
        raise ValueError('Google 未返回可用的读取和发送权限')
    profile=request(GMAIL_URL+'profile',token=result['access_token'])
    if normalize_email(profile.get('emailAddress'))!=normalize_email(account):
        raise ValueError('Google 授权账号与目标账号不一致')
    return result['access_token']


def save_grant(account,client,tokens,*,request=_request,saver=_write):
    """Validate the granted offline token before storing it separately from read-only access."""
    account=normalize_email(account)
    if not account or not client.get('client_id') or not tokens.get('refresh_token'):
        raise ValueError('Google 未提供完整的离线发送授权')
    if not REQUIRED_SCOPES.issubset(_scopes(tokens.get('scope'))):
        raise ValueError('Google 未授予完整的读取和发送权限')
    saved={'client_id':client['client_id'],'client_secret':client.get('client_secret',''),
        'refresh_token':tokens['refresh_token'],'scopes':sorted(REQUIRED_SCOPES),
        'authorized_at':datetime.now(timezone.utc).isoformat()}
    _refresh_and_check(account,saved,request)
    saver(account,saved)
    return {'account':account,'scopes':sorted(REQUIRED_SCOPES),'authorized_at':saved['authorized_at']}


def access_token(account,*,request=_request,reader=_read):
    """Obtain an access token for an already authorized and reviewed operation."""
    account=normalize_email(account)
    return _refresh_and_check(account,reader(account),request)
