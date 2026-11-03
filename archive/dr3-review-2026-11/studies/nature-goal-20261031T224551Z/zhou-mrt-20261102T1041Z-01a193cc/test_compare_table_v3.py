import json
import unittest
import compare_table_v3 as c
import io
from unittest.mock import Mock

def fixture():
    entries = list(c.PREVIEW.items()) + [(str(10000000000000000+i), 'II' if i<3 else 'III') for i in range(13)]
    rows = []
    for ident, typ in entries:
        row = bytearray(b' '*197)
        row[:19] = ident.rjust(19).encode('ascii')
        row[62:65] = typ.ljust(3).encode('ascii')
        rows.append(bytes(row))
    return list(c.HEADER_MARKERS),rows

def body(header,rows): return b'\n'.join(header)+b'\n# Data table:\n'+b'\n'.join(rows)+b'\n'

class TableTests(unittest.TestCase):
    def test_bounded_single_read_uses_verified_bytes(self):
        good=b'abc'; bad=b'def'; source=Mock()
        source.open.side_effect=[io.BytesIO(good),io.BytesIO(bad)]
        self.assertEqual(c.read_verified(source,c.sha(good),limit=3),good)
        self.assertEqual(source.open.call_count,1)
        oversized=Mock(); oversized.open.return_value=io.BytesIO(b'abcdef')
        with self.assertRaises(ValueError): c.read_verified(oversized,c.sha(b'abcdef'),limit=3)

    def test_valid_with_17_digit_id(self):
        h,r = fixture(); parsed = c.parse_table(body(h,r))
        self.assertEqual(len(parsed),17)
        self.assertIn('10000000000000000',parsed)

    def test_missing_header_rejected(self):
        h,r = fixture(); h.pop()
        with self.assertRaises(ValueError): c.parse_table(body(h,r))

    def test_duplicate_id_rejected(self):
        h,r = fixture(); row = bytearray(r[4]); row[:19] = r[5][:19]; r[4] = bytes(row)
        with self.assertRaises(ValueError): c.parse_table(body(h,r))

    def test_missing_record_rejected(self):
        h,r = fixture()
        with self.assertRaises(ValueError): c.parse_table(body(h,r[:-1]))

    def test_wrong_width_rejected(self):
        h,r = fixture(); r[0] = r[0][:-1]
        with self.assertRaises(ValueError): c.parse_table(body(h,r))

    def test_invalid_decimal_rejected(self):
        h,r = fixture(); row=bytearray(r[0]); row[0]=ord('x'); r[0]=bytes(row)
        with self.assertRaises(ValueError): c.parse_table(body(h,r))

    def test_tab_padding_rejected(self):
        for position in (0,64):
            h,r = fixture(); row=bytearray(r[1]); row[position]=9; r[1]=bytes(row)
            with self.subTest(position=position), self.assertRaises(ValueError): c.parse_table(body(h,r))

    def test_wrong_type_distribution_rejected(self):
        h,r = fixture(); row=bytearray(r[0]); row[62:65]=b'III'; r[0]=bytes(row)
        with self.assertRaises(ValueError): c.parse_table(body(h,r))

    def test_preview_type_swap_rejected_even_if_counts_match(self):
        h,r = fixture(); a=bytearray(r[0]); b=bytearray(r[2]); a[62:65]=b'III'; b[62:65]=b'II '; r[0]=bytes(a); r[2]=bytes(b)
        with self.assertRaises(ValueError): c.parse_table(body(h,r))

    def test_frozen_targets_valid(self):
        raw=json.dumps({'sources':[{'source_id':x} for x in c.TARGET_IDS]}).encode()
        self.assertEqual(set(c.parse_targets(raw)),set(c.TARGET_IDS))

    def test_float_target_rejected(self):
        values=list(c.TARGET_IDS); values[0]=float(values[0])
        raw=json.dumps({'sources':[{'source_id':x} for x in values]}).encode()
        with self.assertRaises(ValueError): c.parse_targets(raw)

if __name__ == '__main__': unittest.main()
