import subprocess
import unittest
from unittest.mock import patch
from buyer_discovery import search_buyers
class Tests(unittest.TestCase):
    def test_validation(self):
        for keyword,limit in [('',1),('x',0),('x',True)]:
            with self.assertRaises(ValueError):search_buyers(keyword,limit)
    def test_timeout(self):
        with patch('buyer_discovery.subprocess.run',side_effect=subprocess.TimeoutExpired('worker',1)):
            self.assertEqual(search_buyers()['status'],'timeout')
    def test_failure(self):
        with patch('buyer_discovery.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','private')):
            result=search_buyers();self.assertEqual(result['records'],[]);self.assertNotIn('private',str(result))
    def test_result(self):
        with patch('buyer_discovery.subprocess.run',return_value=subprocess.CompletedProcess([],0,'{"status":"success","records":[]}','')):
            self.assertEqual(search_buyers()['status'],'success')
if __name__=='__main__':unittest.main()
