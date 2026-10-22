import csv
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.sax.saxutils import escape

from core import csv_export, new_candidate
from crm import CRMReader, domains, stop_reason, stop_state


ACCOUNT = ["Lead ID", "Website / identity source", "Business email/form", "CRM stage", "Last touch", "Stop / opt-out", "Next action"]
ACTION = ["Lead ID", "Actual date", "Status", "Outcome", "Notes", "Evidence / URL"]


def workbook(path, accounts, actions=(), headers=ACCOUNT):
    def sheet(headers, rows):
        values = [["Synthetic test title"], [], [], [], headers, *rows]
        body = []
        for n, row in enumerate(values, 1):
            cells = ''.join(f'<c r="{chr(65+i)}{n}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>' for i, v in enumerate(row))
            body.append(f'<row r="{n}">{cells}</row>')
        return '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + ''.join(body) + '</sheetData></worksheet>'
    with ZipFile(path, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Account Pool" r:id="r1"/><sheet name="Outreach Log" r:id="r2"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/><Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', sheet(headers, accounts))
        z.writestr('xl/worksheets/sheet2.xml', sheet(ACTION, actions))


class CRMTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'crm.xlsx'
        self.reader = CRMReader(self.path)
        self.candidate = new_candidate({'website': 'https://www.company.example/'})

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_match_stop_history_and_original_unchanged(self):
        workbook(self.path, [['L1', 'https://company.example/about', '', 'CONTACTED', '2026-09-01', 'YES', 'Wait']], [
            ['L1', '2026-10-01', 'SENT', 'Delivery unknown', '', 'receipt-local'],
            ['L1', '', 'RESEARCH_REQUIRED', '', 'Contacted previously; date absent', ''],
        ])
        before = self.path.read_bytes()
        result = self.reader.check(self.candidate)
        self.assertEqual(result['match_status'], '已匹配')
        self.assertEqual(result['stop_state'], '明确停止')
        self.assertIn('停止联系', result['next_action'])
        match = result['matches'][0]
        self.assertEqual((match['lead_id'], match['row']), ('L1', 6))
        self.assertEqual(match['methods'][0]['field'], 'Website / identity source')
        self.assertEqual(match['latest_touch']['raw_date'], '2026-10-01')
        self.assertEqual(len(match['history']), 2)
        self.assertIn('Contacted', match['history'][1]['notes'])
        self.assertEqual(result['sha256'], hashlib.sha256(before).hexdigest())
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_blank_and_ambiguous_stop_never_authorizes(self):
        for value in ['', 'no/unsubscribed false', 'TECHNICAL_GATE', 'EMAIL_INVALID', 'CATEGORY_MISMATCH', 'PAUSED_NOT_NOW']:
            with self.subTest(value=value):
                self.assertEqual(stop_state(value), '未知')
        self.assertEqual(stop_state('NO'), '未发现明确停止')
        self.assertEqual(stop_reason('TECHNICAL_GATE'), '技术门槛待解决')
        self.assertEqual(stop_reason('EMAIL_INVALID'), '联系入口无效')
        self.assertEqual(stop_reason('CATEGORY_MISMATCH'), '品类不匹配')
        self.assertEqual(stop_reason('PAUSED_NOT_NOW'), '时机暂缓')
        workbook(self.path, [['L1', 'company.example', '', '', '', '', '']])
        result = self.reader.check(self.candidate)
        self.assertEqual(result['stop_state'], '未知')
        self.assertIn('先核', result['next_action'])

    def test_no_match_no_substring_subdomain_or_name_guess(self):
        workbook(self.path, [['L1', 'https://notcompany.example', 'sales@company.example', '', '', 'NO', ''], ['L2', 'https://sub.company.example', '', '', '', 'NO', '']])
        self.candidate['company'] = 'L1'
        result = self.reader.check(self.candidate)
        self.assertEqual(result['match_status'], '未匹配')
        self.assertEqual(result['stop_state'], '未知')
        self.assertIn('非新增或可联系确认', result['next_action'])

    def test_exact_email_with_different_domain_and_conflict(self):
        workbook(self.path, [['L1', 'https://company.example', '', '', '', 'NO', ''], ['L2', 'https://other.example', 'Buying@other.example', '', '', 'YES', '']])
        self.candidate['contacts'] = [{'kind': 'email', 'value': 'buying@other.example'}]
        result = self.reader.check(self.candidate)
        self.assertEqual(result['match_status'], '冲突待核')
        self.assertEqual({m['lead_id'] for m in result['matches']}, {'L1', 'L2'})
        self.assertEqual(result['stop_state'], '明确停止')

    def test_shared_domain_multiple_leads_and_negative_not_permission(self):
        workbook(self.path, [['L1', 'company.example', '', '', '', 'NO', ''], ['L2', 'www.company.example', '', '', '', 'NO', '']])
        result = self.reader.check(self.candidate)
        self.assertEqual(result['match_status'], '冲突待核')
        self.assertIn('人工核对', result['next_action'])
        self.assertIn('未确认', result['contact_permission'])

    def test_missing_file_header_and_changed_file_invalidate_cache(self):
        self.assertEqual(self.reader.check(self.candidate)['match_status'], '读取失败')
        workbook(self.path, [], headers=['Lead ID'])
        self.assertIn('表头缺失', self.reader.check(self.candidate)['error'])
        workbook(self.path, [['L1', 'company.example', '', '', '', 'NO', '']])
        first = self.reader.check(self.candidate)
        workbook(self.path, [['L1', 'company.example', '', '', '', 'YES', 'Stop']])
        second = self.reader.check(self.candidate)
        self.assertNotEqual(first['sha256'], second['sha256'])
        self.assertEqual(second['stop_state'], '明确停止')
        self.path.unlink()
        self.assertEqual(self.reader.check(self.candidate)['match_status'], '读取失败')

    def test_export_carries_stop_provenance_and_no_formulas(self):
        workbook(self.path, [['=L1', 'company.example', '', 'CONTACTED', '2026-10-01', 'YES', '']])
        self.candidate['company'] = '=DANGEROUS()'
        rows = self.reader.annotate([self.candidate])
        exported = list(csv.DictReader(io.StringIO(csv_export(rows).lstrip('\ufeff'))))[0]
        self.assertEqual(exported['CRM停止状态'], '明确停止')
        self.assertIn('Account Pool!6', exported['CRM匹配出处'])
        self.assertEqual(exported['CRM Lead ID'], "'=L1")
        self.assertEqual(exported['公司'], "'=DANGEROUS()")
        self.assertEqual(rows[0]['review'], self.candidate['review'])

    def test_date_ambiguity_and_public_mail_domains_not_company_match(self):
        self.assertNotIn('gmail.com', domains('buyer@gmail.com'))
        workbook(self.path, [['L1', 'company.example', '', '', '10/11/2026', '', '']])
        match = self.reader.check(self.candidate)['matches'][0]
        self.assertIsNone(match['latest_touch'])
        self.assertEqual(len(match['undated_touches']), 1)

    def test_local_stop_survives_unmatched_or_negative_crm_value(self):
        self.candidate['review']['state'] = '停止联系'
        workbook(self.path, [])
        result = self.reader.check(self.candidate)
        self.assertTrue(result['local_stop'])
        self.assertIn('停止联系', result['next_action'])
        workbook(self.path, [['L1', 'company.example', '', '', '', 'NO', '']])
        result = self.reader.check(self.candidate)
        self.assertEqual(result['stop_state'], '未发现明确停止')
        self.assertTrue(result['local_stop'])
        self.assertIn('停止联系', result['next_action'])


if __name__ == '__main__':
    unittest.main()
