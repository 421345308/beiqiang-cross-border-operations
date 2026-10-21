"""Fresh read failures cannot be hidden by old successful response files."""
from pathlib import Path
import json,tempfile,unittest
from verify_current_store_image_closure import latest_read_states


class ReadEvidenceTest(unittest.TestCase):
    def run_states(self,older,newer):
        with tempfile.TemporaryDirectory()as directory:
            p=Path(directory)
            for name,data in [('读取结果.json',older),('增量读取结果.json',newer)]:
                (p/name).write_text(json.dumps(data),encoding='utf8')
            return latest_read_states(p)

    def test_failed_fresh_read_does_not_reuse_old_success(self):
        states=self.run_states({'at':'2026-10-20','items':[{'id':'1','state':'READ'}]}, {'at':'2026-10-21','items':[{'id':'1','state':'READ_FAILED'}]})
        self.assertEqual(states['1']['state'],'READ_FAILED')

    def test_targeted_recovery_preserves_untouched_success(self):
        states=self.run_states({'at':'2026-10-20','items':[{'id':'1','state':'READ_FAILED'},{'id':'2','state':'READ'}]}, {'at':'2026-10-21','items':[{'id':'1','state':'READ'}]})
        self.assertEqual({k:v['state']for k,v in states.items()},{'1':'READ','2':'READ'})

    def test_observed_time_precedes_filename_order(self):
        states=self.run_states({'at':'2026-10-22','items':[{'id':'1','state':'READ_FAILED'}]}, {'at':'2026-10-21','items':[{'id':'1','state':'READ'}]})
        self.assertEqual(states['1']['state'],'READ_FAILED')


if __name__=='__main__':unittest.main()
