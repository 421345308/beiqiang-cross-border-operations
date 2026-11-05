import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from desk_mcp import DeskTools, PRODUCTS


class DossierAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.file=self.root/PRODUCTS
        self.file.parent.mkdir(parents=True)
        self.product={'id':'BQ009','local_assets':{'state':'SINGLE_CURRENT_FACT_ENTRY'}}
        self.write_product()
        self.relative='02_Alibaba运营/02_单品优化记录/商品档案/BQ009/README.md'
        self.dossier=self.root/self.relative
        self.dossier.parent.mkdir(parents=True)
        self.dossier.write_text('# BQ009 商品档案\n\n最新负责人决定。',encoding='utf8')
        self.business=SimpleNamespace(get_object=lambda oid:{'id':oid,'kind':'product','source':PRODUCTS,'content':'{}'})
        self.tool=DeskTools(self.business,self.root,'product:BQ009',read_only=True)

    def write_product(self):
        self.file.write_text(json.dumps({'products':[self.product]},ensure_ascii=False),encoding='utf8')

    def test_explicit_current_exact_id_dossier_is_discoverable_and_readable(self):
        self.assertIn(self.relative,[row['path'] for row in self.tool.sources()])
        self.assertEqual(self.tool.sources(q=self.relative)[0]['role'],'current-product-dossier')
        self.assertIn('最新负责人决定',self.tool.read(self.relative)['content'])

    def test_unmarked_or_wrong_title_cannot_expose_dossier(self):
        self.product['local_assets']['state']='OTHER'
        self.write_product()
        with self.assertRaises(ValueError):self.tool.read(self.relative)
        self.product['local_assets']['state']='SINGLE_CURRENT_FACT_ENTRY'
        self.write_product()
        self.dossier.write_text('# BQ008 商品档案\n',encoding='utf8')
        with self.assertRaises(ValueError):self.tool.read(self.relative)

    def test_other_dossier_and_path_traversal_remain_unavailable(self):
        other='02_Alibaba运营/02_单品优化记录/商品档案/BQ008/README.md'
        for path in (other,'../outside.md'):
            with self.assertRaises(ValueError):self.tool.read(path)


if __name__=='__main__':unittest.main()
