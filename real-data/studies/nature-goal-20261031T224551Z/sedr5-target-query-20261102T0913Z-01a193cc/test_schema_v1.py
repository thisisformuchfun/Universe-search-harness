import csv,io,unittest
import schema_v1 as s

def csv_bytes(header,rows=()):
    out=io.StringIO(newline=''); writer=csv.writer(out,lineterminator='\r\n')
    writer.writerow(header); writer.writerows(rows); return out.getvalue().encode()
def row(**kw):
    result={k:'' for k in s.FIELDS}; result.update(s.CONTROL_KEY); result['filename']=s.CONTROL; result.update(kw)
    return [result[k] for k in s.FIELDS]

class ExactSchemaTests(unittest.TestCase):
    def test_unprefixed_sample(self):
        name,rows=s.parse_csv(csv_bytes(s.FIELDS,[row()])); self.assertEqual(name,'SAMPLE_UNPREFIXED'); self.assertTrue(s.control_passes(rows))
    def test_observed_prefixed_query(self):
        name,rows=s.parse_csv(csv_bytes(s.PREFIXED,[row()])); self.assertEqual(name,'QUERY_PREFIXED'); self.assertTrue(s.control_passes(rows))
    def test_mixed_and_unknown_prefixes_rejected(self):
        mixed=s.PREFIXED.copy(); mixed[1]=s.FIELDS[1]
        with self.assertRaises(ValueError): s.parse_csv(csv_bytes(mixed))
        with self.assertRaises(ValueError): s.parse_csv(csv_bytes(['other_'+x for x in s.FIELDS]))
    def test_reordered_duplicate_extra_missing_rejected(self):
        headers=[s.PREFIXED[1:]+s.PREFIXED[:1],s.PREFIXED[:-1]+[s.PREFIXED[0]],s.PREFIXED+['extra'],s.PREFIXED[:-1]]
        for header in headers:
            with self.subTest(header=header),self.assertRaises(ValueError): s.parse_csv(csv_bytes(header))
    def test_size_row_width_and_empty(self):
        with self.assertRaises(ValueError): s.parse_csv(b'x'*(s.CAP+1))
        with self.assertRaises(ValueError): s.parse_csv(csv_bytes(s.PREFIXED,[['short']]))
        self.assertEqual(s.parse_csv(csv_bytes(s.PREFIXED))[1],[])
    def test_control_requires_exact_unique_tuple(self):
        _,r=s.parse_csv(csv_bytes(s.PREFIXED,[row(),row(iexp='1')]))
        self.assertTrue(s.control_passes(r)); self.assertFalse(s.control_passes(r+[r[0]]))
        self.assertFalse(s.control_passes(r+[dict(r[0],filename='foreign')]))
    def test_target_summary_preserves_strings_without_rv(self):
        _,r=s.parse_csv(csv_bytes(s.PREFIXED,[row(filename=s.TARGET,obsdate='null',rv='unreviewed')]))
        summary=s.identity_summary(r); self.assertTrue(summary['all_exact_filename'])
        self.assertEqual(summary['identity_rows'][0]['obsdate'],'null'); self.assertNotIn('rv',summary['identity_rows'][0])

if __name__=='__main__': unittest.main()
