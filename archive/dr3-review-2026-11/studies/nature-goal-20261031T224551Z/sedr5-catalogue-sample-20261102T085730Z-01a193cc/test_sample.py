import unittest

from sample_fetch import BODY_CAP, sample_schema


class SampleSchemaTests(unittest.TestCase):
    def test_valid_sample_header_and_row_count(self):
        value = sample_schema(b"specid,iexp,mjm,rv,rverr,filename\na,0,1,2,3,f\n")
        self.assertEqual(value["data_rows"], 1)
        self.assertEqual(value["fields"][0], "specid")

    def test_missing_required_field_fails(self):
        with self.assertRaises(ValueError):
            sample_schema(b"specid,iexp,mjm,rv,filename\na,0,1,2,f\n")

    def test_duplicate_header_fails(self):
        with self.assertRaises(ValueError):
            sample_schema(b"specid,iexp,mjm,rv,rverr,filename,rv\n")

    def test_invalid_bytes_or_oversize_fail(self):
        for value in (b"\xff", b"x" * (BODY_CAP + 1)):
            with self.assertRaises((ValueError, UnicodeDecodeError)):
                sample_schema(value)

    def test_row_width_mismatch_fails(self):
        with self.assertRaises(ValueError):
            sample_schema(b"specid,iexp,mjm,rv,rverr,filename\na,0\n")


if __name__ == "__main__":
    unittest.main()
