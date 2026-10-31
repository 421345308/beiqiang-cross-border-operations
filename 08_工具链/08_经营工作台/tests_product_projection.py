import unittest
from unittest.mock import patch
from tests_business import BusinessTests
class ProductProjectionTests(BusinessTests):
    def test_identity_and_conversation(self):
        self.product()
        import json
        rows=json.loads((self.root/'00_总控台/产品中心/数据/产品.json').read_text(encoding='utf8'))
        rows['products'][0]['notes']=['HR001 historical reference']
        rows['products'].append({'id':'HR001','source_state':'HOLD_SOURCE'})
        from business import PRODUCTS
        self.write(PRODUCTS,rows)
        objects=self.business.list_objects('product')
        self.assertEqual([o['product_series'] for o in objects],['其他','HR'])
        row={'reference':'REAL','messages':[{'sender':'buyer','body':'Need black','sentAt':'2026-10-31'}]}
        original=json.dumps(row)
        with patch.object(self.website,'records',return_value=[row]):
            self.assertEqual(self.business.get_object('customer:website-REAL')['conversation'],[{'sender':'buyer','body':'Need black','sent_at':'2026-10-31'}])
        self.assertEqual(json.dumps(row),original)
        with patch.object(self.website,'records',return_value=[{'reference':'EMPTY'}]):
            self.assertEqual(self.business.get_object('customer:website-EMPTY')['conversation'],[])
if __name__=='__main__':unittest.main()
