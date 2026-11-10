"""The local research request carries only a selected product's public identity."""
import unittest
from types import SimpleNamespace
from tests_desk_http import DeskHTTPTests


class PublicResearchHTTPTests(unittest.TestCase):
    setUp=DeskHTTPTests.setUp
    tearDown=DeskHTTPTests.tearDown
    request=DeskHTTPTests.request
    write=DeskHTTPTests.write

    def test_public_product_context_is_derived_from_existing_object(self):
        captured=[]
        self.app.cloud_review=SimpleNamespace(enqueue=lambda *args,**kwargs:captured.append((args,kwargs)) or {'status':'queued'})
        body={'action':'enqueue','task_id':'a'*32,'task_version':1,'source_version':None,
              'instruction':'查找公开鞋款','model':'gpt-6-luna','public_research':True,'product_id':'product:BQ009'}
        code,_=self.request('/api/desk/cloud-review',body);self.assertEqual(code,200)
        context=captured[0][1]['product_context']
        self.assertEqual(context['id'],'product:BQ009')
        self.assertEqual(set(context),{'id','model','title','category'})
        self.assertNotIn('supplier',str(context))
        self.assertEqual(self.request('/api/desk/cloud-review',{**body,'public_research':False})[0],400)


if __name__=='__main__':unittest.main()
