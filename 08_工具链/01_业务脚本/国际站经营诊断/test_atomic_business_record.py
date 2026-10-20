import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import revise_catalog_content as s

class AtomicRecordTests(unittest.TestCase):
    def test_successful_unicode_record(self):
        with tempfile.TemporaryDirectory()as root:
            p=Path(root)/'record.json';s.save(p,{'颜色':'灰色','state':'PASS'})
            self.assertEqual(s.load(p),{'颜色':'灰色','state':'PASS'})
            self.assertEqual(list(Path(root).glob('*.tmp')),[])

    def test_failed_replace_preserves_existing_truth(self):
        with tempfile.TemporaryDirectory()as root:
            p=Path(root)/'record.json';s.save(p,{'state':'ORIGINAL'})
            with patch.object(s.os,'replace',side_effect=OSError(22,'local lock')),patch.object(s.time,'sleep'):
                with self.assertRaises(OSError):s.save(p,{'state':'UNCOMMITTED'})
            self.assertEqual(s.load(p),{'state':'ORIGINAL'})
            self.assertEqual(list(Path(root).glob('*.tmp')),[])

if __name__=='__main__':unittest.main()
