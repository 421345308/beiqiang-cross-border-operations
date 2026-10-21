"""Regression checks for price-only updates with a missing trade object."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

import reprice_verified_catalog as pricing


class TradeEvidenceTests(unittest.TestCase):
    def test_alternate_price_is_separate_but_shipping_and_skus_are_preserved(self):
        before = {'wholesale_trade': {'price': '9.09', 'weight': '0.50',
                                     'shipping_line_template_id': 123},
                  'product_sku': {'skus': [{'sku_id': 77, 'inventory': 999,
                                          'bulk_discount_prices': [{'price': '9.09'}]}]}}
        after = copy.deepcopy(before)
        after['wholesale_trade']['price'] = '7.80'
        after['product_sku']['skus'][0]['bulk_discount_prices'][0]['price'] = '7.80'
        self.assertEqual(pricing.stable(before), pricing.stable(after))
        for field, new in [('weight', '0.60'), ('shipping_line_template_id', 456)]:
            altered = copy.deepcopy(after)
            altered['wholesale_trade'][field] = new
            self.assertNotEqual(pricing.stable(before), pricing.stable(altered))
        altered = copy.deepcopy(after)
        altered['product_sku']['skus'][0]['inventory'] = 0
        self.assertNotEqual(pricing.stable(before), pricing.stable(altered))

    def test_missing_trade_requires_exact_supplement_and_current_pair_option(self):
        schema = ET.fromstring('<itemSchema><field id="priceUnit"><value>5</value>'
            '<options><option value="5" displayName="Pair/Pairs"/></options></field></itemSchema>')
        with self.assertRaises(AssertionError):
            pricing.check_trade_basis({}, {'basis': {}}, schema)
        with TemporaryDirectory() as tmp, patch.object(pricing, 'ROOT', Path(tmp)):
            Path(tmp, 'exact.json').write_text(json.dumps({'currency': 'USD', 'unit': 'Pair'}))
            plan = {'basis': {'trade_supplement_evidence': 'exact.json'}}
            self.assertEqual(pricing.check_trade_basis({}, plan, schema),
                             'SCHEMA_PAIR_AND_EXACT_ID_PUBLIC_CURRENCY_SUPPLEMENT')
            schema.find('./field/options/option').set('displayName', 'Piece/Pieces')
            with self.assertRaises(AssertionError):
                pricing.check_trade_basis({}, plan, schema)


if __name__ == '__main__':
    unittest.main()
