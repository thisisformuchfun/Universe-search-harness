import unittest
from inspect_article import inspect

class InspectTests(unittest.TestCase):
    def test_redacts_query_and_does_not_follow(self):
        body = (b'<meta name="citation_doi" content="10.3847/1538-4357/aeaa3a">'
                b'<meta name="citation_title" content="A Sample of Long-period Binaries with Dormant Compact-object Candidates">'
                b'<a href="/table.txt?secret=redacted">Machine-readable (MRT)</a>')
        result = inspect(body)
        self.assertTrue(result['citation_doi_exact'])
        self.assertEqual(result['candidate_table_links'][0]['host_category'], 'iopscience.iop.org')
        self.assertTrue(result['candidate_table_links'][0]['query_present'])
        self.assertNotIn('secret', str(result))

    def test_path_and_label_contents_not_echoed(self):
        body = (b'<meta name="citation_doi" content="10.3847/1538-4357/aeaa3a">'
                b'<meta name="citation_title" content="A Sample of Long-period Binaries with Dormant Compact-object Candidates">'
                b'<a href="/CANARYPATH">Machine-readable CANARYLABEL</a>')
        result = inspect(body)
        self.assertEqual(len(result['candidate_table_links']),1)
        self.assertNotIn('CANARY',str(result))

    def test_malformed_hostname_does_not_echo_canary(self):
        body = ('<meta name="citation_doi" content="10.3847/1538-4357/aeaa3a">'
                '<meta name="citation_title" content="A Sample of Long-period Binaries with Dormant Compact-object Candidates">'
                '<a href="https://CANARY／bad/table">Machine-readable</a>').encode('utf-8')
        result = inspect(body)
        self.assertEqual(result['candidate_table_links'], [])
        self.assertNotIn('CANARY',str(result))

    def test_conflicting_identity_suppresses_links(self):
        body = (b'<meta name="citation_doi" content="10.3847/1538-4357/aeaa3a">'
                b'<meta name="citation_doi" content="other">'
                b'<meta name="citation_title" content="A Sample of Long-period Binaries with Dormant Compact-object Candidates">'
                b'<a href="/table">Machine-readable</a>')
        self.assertEqual(inspect(body)['candidate_table_links'], [])

    def test_duplicate_meta_attribute_suppresses_links(self):
        body = (b'<meta name="citation_doi" content="wrong" content="10.3847/1538-4357/aeaa3a">'
                b'<meta name="citation_title" content="A Sample of Long-period Binaries with Dormant Compact-object Candidates">'
                b'<a href="/table">Machine-readable</a>')
        self.assertEqual(inspect(body)['candidate_table_links'], [])

    def test_lexical_ids_do_not_verify_table_controls(self):
        result = inspect(b'<script>1893474166810285952</script><!--18934741668102859520-->')
        self.assertFalse(result['table_controls_verified'])
        self.assertEqual(result['lexical_id_occurrences_not_table_validation']['1893474166810285952'],1)
        longer_only = inspect(b'<script>18934741668102859520</script>')
        self.assertEqual(longer_only['lexical_id_occurrences_not_table_validation']['1893474166810285952'],0)

    def test_challenge_is_flagged(self):
        self.assertTrue(inspect(b'<html>Verify you are human</html>')['challenge_marker_present'])

    def test_challenge_or_missing_identity_suppresses_links(self):
        a = b'<a href="/table.txt">Machine-readable (MRT)</a>'
        self.assertEqual(inspect(a)['candidate_table_links'], [])
        body = (b'<meta name="citation_doi" content="10.3847/1538-4357/aeaa3a">'
                b'<meta name="citation_title" content="A Sample of Long-period Binaries with Dormant Compact-object Candidates">'
                b'Verify you are human' + a)
        self.assertEqual(inspect(body)['candidate_table_links'], [])

    def test_invalid_bytes_fail(self):
        with self.assertRaises(ValueError): inspect(b'\x00')
        with self.assertRaises(UnicodeError): inspect(b'\xff')

if __name__ == '__main__': unittest.main()
