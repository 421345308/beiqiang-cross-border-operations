import unittest

from gmail_send_authorization import READ_SCOPE,SEND_SCOPE,access_token,save_grant


class GmailSendAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.saved={}
        self.client={'client_id':'desktop-client','client_secret':'fixture-secret'}
        self.grant={'refresh_token':'fixture-refresh','scope':READ_SCOPE+' '+SEND_SCOPE}

    def request(self,url,*,form=None,token=None):
        if form is not None:
            self.assertEqual(form['grant_type'],'refresh_token')
            return {'access_token':'fixture-access','scope':READ_SCOPE+' '+SEND_SCOPE}
        return {'emailAddress':'owner@example.com'}

    def test_saves_separate_grant_only_after_refresh_and_account_check(self):
        result=save_grant('owner@example.com',self.client,self.grant,request=self.request,
            saver=lambda account,value:self.saved.update({account:value}))
        self.assertEqual(result['account'],'owner@example.com')
        self.assertNotIn('refresh_token',result)
        self.assertEqual(access_token('owner@example.com',request=self.request,reader=self.saved.get),'fixture-access')

    def test_refuses_missing_scope_without_saving(self):
        self.grant['scope']=READ_SCOPE
        with self.assertRaises(ValueError):
            save_grant('owner@example.com',self.client,self.grant,request=self.request,
                saver=lambda account,value:self.saved.update({account:value}))
        self.assertFalse(self.saved)

    def test_refuses_wrong_account_without_saving(self):
        with self.assertRaises(ValueError):
            save_grant('different@example.com',self.client,self.grant,request=self.request,
                saver=lambda account,value:self.saved.update({account:value}))
        self.assertFalse(self.saved)


if __name__=='__main__':unittest.main()
