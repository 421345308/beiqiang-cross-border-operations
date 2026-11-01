import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from resource_library import ResourceLibrary


class ResourceLibraryTest(unittest.TestCase):
    def test_agent_reads_only_current_customer_or_shared_material(self):
        from desk_mcp import DeskTools
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); folder=root/'04_客户开发'; folder.mkdir()
            (folder/'shared.md').write_text('工厂资料',encoding='utf8')
            (folder/'private.md').write_text('客户乙资料',encoding='utf8')
            business=SimpleNamespace(list_objects=lambda:[{'id':'customer:a'},{'id':'customer:b'}],
                                     get_object=lambda oid:{'id':oid,'kind':'customer'})
            app=SimpleNamespace(root=root,db=sqlite3.connect(':memory:'),lock=threading.RLock(),business=business)
            library=ResourceLibrary(app);app.library=library;business.app=app
            shared=library.add({'path':'04_客户开发/shared.md','object_ids':[]})
            other=library.add({'path':'04_客户开发/private.md','object_ids':['customer:b']})
            tools=DeskTools(business,root,'customer:a')
            self.assertEqual([x['id'] for x in tools.call('list_customer_materials',{})['materials']],[shared['id']])
            self.assertEqual(tools.call('read_customer_material',{'material_id':shared['id']})['content'],'工厂资料')
            with self.assertRaises(ValueError):tools.call('read_customer_material',{'material_id':other['id']})

    def test_search_finds_product_images_from_existing_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); image=root/'01_产品资产'/'BQ001'/'shoe.jpg'
            image.parent.mkdir(parents=True); image.write_bytes(b'image')
            relative=image.relative_to(root).as_posix()
            business=SimpleNamespace(list_objects=lambda **kw:[{'id':'product:BQ001','title':'BQ001'}],
                                     get_object=lambda oid:{'assets':[{'path':relative}]})
            app=SimpleNamespace(root=root,db=sqlite3.connect(':memory:'),lock=threading.Lock(),business=business)
            library=ResourceLibrary(app)
            found=library.candidates('BQ001')
            self.assertEqual(len(found),1);self.assertEqual(found[0]['path'],relative)

    def test_client_and_shared_materials_reference_original_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / '04_客户开发' / '.local' / '网站询盘' / 'inquiry'
            folder.mkdir(parents=True)
            pdf = folder / 'factory.pdf'
            pdf.write_bytes(b'%PDF-example')
            qa = folder / 'pdf-qa'
            qa.mkdir()
            (qa / 'page-1.png').write_bytes(b'preview')
            db = sqlite3.connect(':memory:')
            business = SimpleNamespace(list_objects=lambda: [{'id': 'customer:1'}])
            library = ResourceLibrary(SimpleNamespace(root=root, db=db, lock=threading.Lock(), business=business))
            relative = pdf.relative_to(root).as_posix()
            client = library.add({'title': '客户资料', 'path': relative, 'object_ids': ['customer:1']})
            with self.assertRaisesRegex(ValueError, '已在资料包'):
                library.add({'title': '重复资料', 'path': relative.replace('/', '\\'), 'object_ids': []})
            shared = library.update({'id': client['id'], 'title': '通用资料', 'object_ids': []})
            self.assertEqual(library.locate(client['path']).read_bytes(), b'%PDF-example')
            self.assertEqual({r['id'] for r in library.list()}, {client['id']})
            self.assertEqual([r['path'] for r in library.candidates()], [relative])
            self.assertEqual(shared['title'], '通用资料')
            self.assertEqual(shared['object_ids'], [])
            edited = library.update({'id': client['id'], 'object_ids': ['customer:1', 'customer:1']})
            self.assertEqual(edited['object_ids'], ['customer:1'])
            for fields in ({'title': ''}, {'title': 'x' * 161}, {'object_ids': ['missing']}, {'object_ids': [None]}):
                with self.assertRaises(ValueError):
                    library.update({'id': client['id'], **fields})
            self.assertEqual(library.list(), [edited])
            for invalid in ('', '../secret.txt', '04_客户开发/missing.pdf'):
                with self.assertRaises(ValueError):
                    library.add({'path': invalid})
            library.remove(client['id'])
            self.assertEqual(library.list(), [])
            self.assertEqual(pdf.read_bytes(), b'%PDF-example')
            with self.assertRaisesRegex(ValueError, '不存在'):
                library.remove(client['id'])
            with self.assertRaisesRegex(ValueError, '不存在'):
                library.update({'id': client['id'], 'title': '消失的资料'})


if __name__ == '__main__':
    unittest.main()
