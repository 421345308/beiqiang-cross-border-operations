import importlib.util,tempfile,unittest,ssl
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('catalog',Path(__file__).with_name('read_only_catalog.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Client:
 class ClientError(Exception):pass
 def __init__(self,results):self.results=iter(results);self.calls=[]
 def top_call(self,c,method,p):
  self.calls.append((method,p));r=next(self.results)
  if isinstance(r,Exception):raise r
  return r
 def api_error(self,r):return r.get('error')
class Tests(unittest.TestCase):
 def test_write_never_sent(self):
  c=Client([])
  with self.assertRaises(ValueError):m.read_only_call(c,{},'alibaba.icbu.product.schema.add',{})
  self.assertEqual(c.calls,[])
 def test_certificate_never_retried(self):
  e=Client.ClientError('redacted');e.__cause__=ssl.SSLCertVerificationError('certificate')
  c=Client([e,{}])
  with self.assertRaises(Client.ClientError):m.read_only_call(c,{},'alibaba.icbu.product.list',{})
  self.assertEqual(len(c.calls),1)
 def test_transient_bounded(self):
  e=Client.ClientError('redacted');e.__cause__=ssl.SSLEOFError('EOF');c=Client([e,e,e,{}])
  with patch.object(m.time,'sleep'):
   with self.assertRaises(Client.ClientError):m.read_only_call(c,{},'alibaba.icbu.product.list',{})
  self.assertEqual(len(c.calls),3)
 def test_duplicate_page_rejected(self):
  p={'current_page':1,'total_item':2,'page_size':1,'products':[{'id':1}]};q=dict(p,current_page=2);c=Client([p,q])
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(RuntimeError):m.fetch_catalog(c,{},d)
   self.assertFalse((Path(d)/'catalog.json').exists())
 def test_complete_unique_catalog(self):
  c=Client([{'current_page':1,'total_item':2,'page_size':1,'products':[{'id':1}]},{'current_page':2,'total_item':2,'page_size':1,'products':[{'id':2}]}])
  with tempfile.TemporaryDirectory() as d:self.assertTrue(m.fetch_catalog(c,{},d)['complete'])
if __name__=='__main__':unittest.main()
