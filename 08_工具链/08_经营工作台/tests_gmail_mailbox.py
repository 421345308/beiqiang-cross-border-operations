import imaplib
import unittest
from email.message import EmailMessage
from gmail_mailbox import GmailMailbox, parse_message, test_credentials

ACCOUNT='me@example.com'
BUYER='buyer@example.com'

def mail(sender=BUYER, recipient=ACCOUNT, date='Sun, 01 Nov 2026 10:00:00 +0800', body='Hello'):
    m=EmailMessage();m['From']=sender;m['To']=recipient;m['Date']=date;m['Subject']='Test';m.set_content(body)
    return m.as_bytes()

class FakeIMAP:
    def __init__(self, rows=None, fail=False):
        self.rows=rows or [mail()];self.fail=fail;self.calls=[]
    def login(self, *args):
        if self.fail: raise imaplib.IMAP4.error('SECRET password rejected')
    def list(self): return 'OK',[b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"']
    def select(self, box, readonly=False):
        assert readonly;self.calls.append(('select',box,readonly));return 'OK',[b'1']
    def uid(self, action, *args):
        self.calls.append((action,*args))
        if action=='SEARCH':return 'OK',[b' '.join(str(i+1).encode() for i in range(len(self.rows)))]
        assert 'BODY.PEEK[]' in args[1]
        n=int(args[0]);return 'OK',[(f'{n} (X-GM-MSGID {100+n} X-GM-THRID 90 INTERNALDATE "01-Nov-2026 02:00:00 +0000"'.encode(), self.rows[n-1]),b')']
    def logout(self):self.calls.append(('logout',))

class Tests(unittest.TestCase):
    def mailbox(self,fake,clock=lambda:1800000000):
        return GmailMailbox(ACCOUNT,imap_factory=lambda:fake,password_reader=lambda _: 'secret',clock=clock)
    def test_inbound_readonly(self):
        f=FakeIMAP();r=self.mailbox(f).context([BUYER]);self.assertTrue(r['reply_pending']);self.assertEqual(r['status']['state'],'ready')
        self.assertIn('-in:drafts -in:spam -in:trash',f.calls[1][-1]);self.assertEqual(r['messages'][0]['sent_at'],'2026-11-01T02:00:00+00:00')
        self.assertEqual(r['messages'][0]['body'],'Hello')
    def test_outbound_later(self):
        f=FakeIMAP([mail(),mail(ACCOUNT,BUYER,'Sun, 01 Nov 2026 11:00:00 +0800')]);r=self.mailbox(f).context([BUYER]);self.assertFalse(r['reply_pending'])
    def test_same_account_ignored(self):
        f=FakeIMAP([mail(ACCOUNT,ACCOUNT)]);self.assertEqual(self.mailbox(f).context([ACCOUNT,BUYER])['messages'],[])
    def test_exact_sender_not_substring(self):
        f=FakeIMAP([mail('otherbuyer@example.com')]);self.assertEqual(self.mailbox(f).context([BUYER])['messages'],[])
    def test_other_mailbox_not_associated(self):
        f=FakeIMAP([mail(BUYER,'someone@example.com')]);self.assertEqual(self.mailbox(f).context([BUYER])['messages'],[])
    def test_failure_preserves_success(self):
        f=FakeIMAP();b=self.mailbox(f);first=b.context([BUYER]);f.fail=True;r=b.context([BUYER],force=True)
        self.assertEqual(r['status']['state'],'error');self.assertIsNone(r['reply_pending']);self.assertEqual(r['messages'],first['messages']);self.assertEqual(r['status']['last_success_at'],first['status']['last_success_at']);self.assertNotIn('SECRET',str(r))
    def test_cache_and_refresh(self):
        now=[1000];f=FakeIMAP();b=self.mailbox(f,lambda:now[0]);b.context([BUYER]);calls=len(f.calls);b.context([BUYER]);self.assertEqual(len(f.calls),calls);now[0]+=121;b.context([BUYER]);self.assertGreater(len(f.calls),calls)
    def test_missing_credentials(self):
        b=GmailMailbox(ACCOUNT,password_reader=lambda _:None);self.assertEqual(b.context([BUYER])['status']['state'],'not_configured')
    def test_bad_address(self):
        with self.assertRaises(ValueError):self.mailbox(FakeIMAP()).context(['bad" OR ALL'])
    def test_html_and_attachment(self):
        m=EmailMessage();m['From']=BUYER;m['To']=ACCOUNT;m.set_content('<p>Hello &amp; goodbye</p><script>bad()</script>',subtype='html');m.add_attachment(b'SECRET',maintype='application',subtype='octet-stream',filename='private.txt')
        r=parse_message(m.as_bytes(),b'X-GM-MSGID 1',b'1',ACCOUNT,{BUYER});self.assertIn('Hello & goodbye',r['body']);self.assertNotIn('SECRET',r['body']);self.assertNotIn('bad()',r['body']);self.assertEqual(r['attachments'][0]['filename'],'private.txt')
    def test_limit_loads_recent_with_notice(self):
        b=self.mailbox(FakeIMAP([mail(),mail(ACCOUNT,BUYER,'Sun, 01 Nov 2026 11:00:00 +0800')]));b.max_messages=1
        r=b.context([BUYER]);self.assertEqual(r['status']['state'],'ready');self.assertTrue(r['status']['history_limited']);self.assertEqual(len(r['messages']),1);self.assertFalse(r['reply_pending'])
    def test_credentials_only_login_logout(self):
        f=FakeIMAP();self.assertTrue(test_credentials(ACCOUNT,'abcdefghijklmnop',imap_factory=lambda:f));self.assertEqual(f.calls,[('logout',)])
    def test_credentials_failure_redacts_password(self):
        with self.assertRaises(ValueError) as c:test_credentials(ACCOUNT,'abcdefghijklmnop',imap_factory=lambda:FakeIMAP(fail=True))
        self.assertNotIn('SECRET',str(c.exception));self.assertNotIn('abcdefghijklmnop',str(c.exception))
    def test_partial_body_notice(self):
        r=parse_message(mail(),b'X-GM-MSGID 1 RFC822.SIZE 9000000',b'1',ACCOUNT,{BUYER});self.assertTrue(r['body_truncated'])

if __name__=='__main__': unittest.main()
