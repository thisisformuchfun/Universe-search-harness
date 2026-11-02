import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import verify_public_review as review


class EvidenceSafetyTests(unittest.TestCase):
    def test_ids_are_exact_decimal_tokens(self):
        self.assertTrue(review.whole_id("source 824344003814438528 &", "824344003814438528"))
        self.assertFalse(review.whole_id("source 1824344003814438528 &", "824344003814438528"))
        self.assertFalse(review.whole_id("source 8243440038144385280 &", "824344003814438528"))

    def test_changed_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "li-2026-source.raw").write_bytes(b"tampered")
            with patch.object(review, "EVIDENCE", Path(tmp)):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    review.checked_bytes("li-2026-source.raw")


if __name__ == "__main__":
    unittest.main()
