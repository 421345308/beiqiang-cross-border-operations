"""Separate buyer correspondence from mailing lists and automatic responses."""
from __future__ import annotations
import re
from email.utils import getaddresses

_BUYER_ACTION = re.compile(r'\b(?:we\s+are\s+(?:looking|seeking|interested)|we\s+(?:need|want)\s+(?:(?:to\s+)?(?:buy|purchase|source|order|find|manufacture)|\d+|shoes?|footwear|sneakers?|suppliers?)|would\s+like\s+to\s+(?:buy|purchase|source|order|discuss)|could\s+you|can\s+you|please\s+(?:send|share|provide|quote)|looking\s+for|request\s+(?:a\s+)?(?:quote|quotation|pricing)|interested\s+in\s+(?:buying|ordering|sourcing|your)|work(?:ing)?\s+with\s+you)\b',re.I)
_BUYER_TOPIC = re.compile(r'\b(?:shoes?|footwear|sneakers?|slippers?|sandals?|boots?|pairs?|manufactur(?:e|er|ing)|suppliers?|wholesale|bulk\s+order|MOQ|quotation|catalog(?:ue)?|price\s+list|samples?)\b',re.I)
_SHOE_TOPIC = re.compile(r'\b(?:shoes?|footwear|sneakers?|slippers?|sandals?|boots?|beiqiang)\b|鞋',re.I)
_SELLER_PITCH = re.compile(r'\b(?:introduce\s+(?:you\s+to\s+)?our\s+(?:company|products)|we\s+(?:are\s+)?(?:producing|manufacturing|supplying|exporting)\b|we\s+are\s+(?:a|an|one\s+of\s+the|the)?\s*(?:leading\s+)?(?:manufacturers?|producers?|suppliers?|factories|exporters?))',re.I)
_BUYER_SPECIFIC = re.compile(r'\b(?:looking\s+for\s+(?:a\s+|an\s+)?(?:supplier|factory|manufacturer)|(?:need|want|plan)\s+to\s+(?:buy|purchase|source|order)|(?:please|could\s+you|can\s+you).{0,50}(?:quote|quotation|manufacture|produce\s+for\s+us|supply\s+us)|(?:purchase|order)\s+\d+\s+pairs?)\b',re.I)
_TICKET_NOTICE = re.compile(r"\b(?:we(?:'ll|\s+will)\s+(?:pick\s+up|respond\s+to|review)\s+your\s+(?:support\s+)?(?:ticket|request)|your\s+(?:support\s+)?(?:ticket|request)\s+(?:has\s+been|was)\s+(?:received|created|submitted))\b",re.I)


def authored_text(body):
    """Ignore quoted earlier correspondence when judging a new message."""
    value=str(body or '')
    value=re.split(r'(?im)^\s*(?:from\s*:|发件人\s*[：:]|on .{3,160} wrote\s*:|-{2,}\s*(?:original|forwarded) message\s*-{2,})',value,maxsplit=1)[0]
    return '\n'.join(line for line in value.splitlines() if not line.lstrip().startswith('>'))


def buyer_intent(subject, body):
    text=(str(subject or '')+'\n'+authored_text(body))[:12000]
    chinese=re.search(r'(?:想要|寻找|需要|希望|咨询).{0,20}(?:采购|批发|订购|定制|报价|供应商)|(?:采购|批发|订购|定制).{0,15}鞋',text)
    return bool((_BUYER_ACTION.search(text) and _BUYER_TOPIC.search(text)) or chinese)


def new_buyer_summary(subject, body):
    text=(str(subject or '')+'\n'+authored_text(body))[:12000]
    if not (_SHOE_TOPIC.search(text) and buyer_intent(subject,body)):return ''
    if _TICKET_NOTICE.search(text) or (_SELLER_PITCH.search(text) and not _BUYER_SPECIFIC.search(text)):return ''
    topics=[]
    for pattern,label in (
        (r'\b(?:quot(?:e|ation)|pric(?:e|es|ing))\b|报价|价格','价格'),
        (r'\b(?:MOQ|minimum\s+order(?:\s+quantity)?)\b|起订|最低订购','起订量'),
        (r'\b(?:sizes?|sizing)\b|尺码|尺寸','尺码'),
        (r'\b(?:samples?|sampling)\b|样品|打样','样品'),
        (r'\b(?:catalog(?:ue)?s?)\b|产品目录|产品册','产品目录'),
    ):
        if re.search(pattern,text,re.I):topics.append(label)
    if topics:return '咨询鞋类'+('、'.join(topics[:-1])+'和' if len(topics)>1 else '')+topics[-1]
    return '邮件提出鞋类采购或供应合作咨询'


def classify_mail(headers, *, direction, labels=(), subject='', body=''):
    if direction=='outbound':return 'conversation'
    headers={str(k).lower():str(v or '') for k,v in headers.items()}
    auto=headers.get('auto-submitted','').strip().lower()
    precedence=headers.get('precedence','').strip().lower()
    subject=str(subject or headers.get('subject','')).strip()
    direct_reply=bool(headers.get('in-reply-to') or headers.get('references'))
    clear_intent=buyer_intent(subject,body)
    if not direct_reply and not clear_intent and (precedence in ('bulk','list','junk')
            or headers.get('list-unsubscribe') or 'CATEGORY_PROMOTIONS' in labels):
        return 'promotion'
    if not direct_reply and _SELLER_PITCH.search(authored_text(body)) and not _BUYER_SPECIFIC.search(authored_text(body)):
        return 'promotion'
    if ((auto and auto!='no') or headers.get('x-autoreply') or headers.get('x-autorespond')
            or precedence in ('auto_reply','autoreply')
            or _TICKET_NOTICE.search(authored_text(body)[:2000])
            or re.match(r'^(?:automatic reply|auto(?:matic)?[- ]reply|out of office|自动回复|自动答复)(?:\s*[:：-]|\s*$)',subject,re.I)):
        return 'automatic'
    # A personal reply in an existing conversation takes precedence over a
    # broad Gmail category or a mailing footer inserted by the sender's system.
    if not direct_reply and not clear_intent:
        senders=[addr.lower().split('@',1)[0] for _,addr in getaddresses([headers.get('from','')]) if '@' in addr]
        if any(re.fullmatch(r'(?:no[-_.]?reply|do[-_.]?not[-_.]?reply|mailer[-_.]?daemon|postmaster)',sender) for sender in senders):
            return 'automatic'
    return 'conversation'
