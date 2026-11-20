import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'rename_invoices.py'
spec = importlib.util.spec_from_file_location('rename_invoices', MODULE)
rename_invoices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rename_invoices)


class RenameInvoicesTest(unittest.TestCase):
    def test_date_and_time_normalization(self):
        self.assertEqual(rename_invoices.normalize_time_separators('2026-11-13'), '2026-11-13')
        self.assertEqual(rename_invoices.normalize_time_separators('2026-11-13 14-30-52'), '2026-11-13 14:30:52')

    def test_railway_filename(self):
        name = rename_invoices.build_target_name({'type': '高铁', 'origin':'北京南站', 'destination':'天津站', 'date': '2026-11-16', 'amount': '54.50'}, '.pdf')
        self.assertEqual(name, '【发票】高铁-北京南站-天津站-54.50-26-11-16.pdf')

    def test_ambiguous_air_or_rail_is_not_renamed(self):
        (status, _), _ = self.run_case('rail.pdf', b'original', type='高铁/飞机')
        self.assertEqual(status, 'skip')
        self.assertTrue((self.folder / 'rail.pdf').exists())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def run_case(self, filename, data, **fields):
        path = self.folder / filename
        path.write_bytes(data)
        record = {'filename': filename, 'type': '打车费', 'date': '2026-11-13', 'amount': 21.42, **fields}
        result = rename_invoices.rename_one(str(path), record)
        return result, self.folder / '备份' / ('_备份_' + filename)

    def test_missing_person_and_zero_amount(self):
        (status, _), backup = self.run_case('a.pdf', b'first', amount=0)
        self.assertEqual(status, 'ok')
        self.assertEqual((self.folder / '【发票】打车费-26-11-13-0.pdf').read_bytes(), b'first')
        self.assertEqual(backup.read_bytes(), b'first')

    def test_substitute_ticket_with_person_and_name_collision(self):
        target = self.folder / '【替票】打车费-26-11-13-21.42.pdf'
        target.write_bytes(b'existing')
        (status, _), backup = self.run_case('b.pdf', b'new', is_ticket=True, person='小王')
        self.assertEqual(status, 'ok')
        self.assertEqual(target.read_bytes(), b'existing')
        self.assertEqual((self.folder / '【替票】打车费-26-11-13-21.42_2.pdf').read_bytes(), b'new')
        self.assertEqual(backup.read_bytes(), b'new')

    def test_substitute_detected_from_original_filename(self):
        (status, _), backup = self.run_case('【替票】原票.pdf', b'original')
        self.assertEqual(status, 'ok')
        self.assertEqual((self.folder / '【替票】打车费-26-11-13-21.42.pdf').read_bytes(), b'original')
        self.assertEqual(backup.read_bytes(), b'original')

    def test_cli_shows_only_problem_and_summary(self):
        (self.folder / 'normal.pdf').write_bytes(b'normal')
        (self.folder / 'bad.pdf').write_bytes(b'bad')
        records = [
            {'filename': 'normal.pdf', 'type': '餐费', 'date': '2026-11-13', 'amount': 10},
            {'filename': 'bad.pdf', 'type': '餐费', 'date': '', 'amount': 10},
        ]
        data_file = self.folder / 'fields.json'
        data_file.write_text(json.dumps(records, ensure_ascii=False), encoding='utf-8')
        result = subprocess.run([sys.executable, '-X', 'utf8', str(MODULE), str(self.folder), str(data_file)],
                                check=True, capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONUTF8': '1'})
        self.assertIn('字段缺失', result.stdout)
        self.assertIn('成功 1，跳过 1', result.stdout)
        self.assertNotIn('[完成]', result.stdout)
        self.assertNotIn('[备份]', result.stdout)
        self.assertNotIn('[提示]', result.stdout)

    def test_missing_date_skips_and_preserves_file(self):
        (status, _), backup = self.run_case('c.pdf', b'unchanged', date='')
        self.assertEqual(status, 'skip')
        self.assertEqual((self.folder / 'c.pdf').read_bytes(), b'unchanged')
        self.assertFalse(backup.exists())

    def test_existing_different_backup_is_not_reused(self):
        backup = self.folder / '备份' / '_备份_d.pdf'
        backup.parent.mkdir()
        backup.write_bytes(b'old version')
        (status, _), _ = self.run_case('d.pdf', b'new version')
        self.assertEqual(status, 'ok')
        self.assertEqual(backup.read_bytes(), b'old version')
        self.assertEqual((backup.parent / '_备份_d_2.pdf').read_bytes(), b'new version')


if __name__ == '__main__':
    unittest.main()
