"""Independent scientific regression tests. Covariance rows here are synthetic UNIT fixtures.
These tests establish arithmetic and claim boundaries, not astrophysical validation.
"""

import json
import math
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
import numpy as np
from harness2.universe.detectors.signal_pipeline import (
    COVARIANCE_ORDERS,
    TERMS,
    covariance,
    identity,
    measure,
    propagate,
)
from harness2.cli.universe import ROOT, evaluate_holdout, snapshot
from harness2.core.guards import disposition, sha
from harness2.core.recursion import partition
from harness2.core.components import HarnessBundle
from harness2.universe.novelty import bundled_catalogs


def covariance_fixture(kind="Orbital"):
    names = COVARIANCE_ORDERS[kind]
    r = {k: "1" for k in names}
    r.update({k + "_error": ".01" for k in names})
    r.update(
        source_id="4373465352415301633",
        nss_solution_type=kind,
        corr_vec=[0.0] * (len(names) * (len(names) - 1) // 2),
        bit_index="8191" if kind == "Orbital" else "65535",
        period="186",
        efficiency=".9",
    )
    return r


class ScienceTests(unittest.TestCase):
    def test_snapshot_observables_and_fail_closed_dispositions(self):
        rows, _ = snapshot()
        known, _ = bundled_catalogs()
        out = []
        baseline = json.loads((ROOT / "data/pilot/gaia_pilot_report.json").read_text())
        expected = {r["source_id"]: r["f_phot_solar"] for r in baseline["held_rows"]}
        for row in rows:
            r = measure(row, 128)
            r.update(disposition(r, known))
            out.append(r)
        high = [r for r in out if r["f_phot_solar"] > 3]
        self.assertEqual((len(out), len(high)), (500, 17))
        for r in high:
            self.assertTrue(math.isclose(r["f_phot_solar"], expected[r["source_id"]], rel_tol=1e-12))
        self.assertEqual(sum(r["status"] == "HOLD_QUALITY_AND_NOVELTY" for r in high), 14)
        self.assertEqual(sum(r["status"] == "EXCLUDE_KNOWN_BH" for r in high), 2)
        self.assertEqual(sum(r["status"] == "EXCLUDE_PRIOR_REFUTED_CANDIDATE" for r in high), 1)
        self.assertTrue(all(r["uncertainty"]["status"] == "UNAVAILABLE" for r in out))
        self.assertTrue(all(r["observable_not_companion_mass"] for r in out))

    def test_covariance_orders_and_column_major(self):
        for kind in COVARIANCE_ORDERS:
            r = covariance_fixture(kind)
            r["corr_vec"][2 + 5 * 4 // 2] = 0.25
            m, c = covariance(r)
            self.assertEqual(m.tolist(), [1, 1, 1, 1, 1, 186])
            self.assertAlmostEqual(c[0, 1], 0.000025)
            self.assertAlmostEqual(c[1, 0], 0.000025)
            self.assertTrue(np.allclose(np.diag(c), 0.0001))

    def test_invalid_parameterizations_hold(self):
        for bit in ["8191.9", "8179", "65435", "nan", "inf"]:
            r = covariance_fixture()
            r["bit_index"] = bit
            with self.subTest(bit=bit), self.assertRaises(ValueError):
                covariance(r)
        for kind in ["OrbitalAlternative", "OrbitalAlternativeValidated", "OrbitalTargetedSearchValidated"]:
            r = covariance_fixture()
            r["nss_solution_type"] = kind
            self.assertEqual(measure(r, 128)["uncertainty"]["status"], "UNAVAILABLE")

    def test_invalid_correlation_rejected_not_silently_fixed(self):
        for raw in [[0.0] * 65, [0.0] * 67, [None] * 66, [float("nan")] * 66, [1.1] * 66]:
            r = covariance_fixture()
            r["corr_vec"] = raw
            with self.subTest(raw=str(raw)[:30]), self.assertRaises((ValueError, TypeError)):
                covariance(r)
        r = covariance_fixture()
        r["corr_vec"][0] = 0.9
        r["corr_vec"][1] = 0.9
        r["corr_vec"][2] = -0.9
        with self.assertRaises(ValueError):
            covariance(r)

    def test_ids_are_exact_ascii_strings(self):
        vals = []
        for sid in ["4373465352415301632", "4373465352415301633"]:
            r = covariance_fixture()
            r["source_id"] = sid
            vals.append(identity(r))
        self.assertNotEqual(*vals)
        for sid in [4373465352415301632, 4.3734653524153016e18, "４３７", "-1", "4.373e18", "0", " 123"]:
            with self.subTest(sid=sid), self.assertRaises(ValueError):
                identity(dict(covariance_fixture(), source_id=sid))

    def test_invalid_physical_inputs_rejected(self):
        for k, v in [
            ("parallax", "nan"),
            ("parallax", "0"),
            ("period", "-1"),
            ("period_error", "0"),
            ("parallax_error", "-1"),
            ("a_thiele_innes", "inf"),
        ]:
            r = covariance_fixture()
            r[k] = v
            with self.subTest(k=k, v=v), self.assertRaises(ValueError):
                measure(r, 128)

    def test_mc_reproducible_and_not_mass_posterior(self):
        a = propagate(covariance_fixture(), 128)
        b = propagate(covariance_fixture(), 128)
        self.assertEqual(a, b)
        self.assertEqual(a["method"], "joint_gaussian_catalog_covariance_not_orbit_refit")
        self.assertTrue(all(math.isfinite(a[x]) for x in ["f_phot_q05", "f_phot_q50", "f_phot_q95"]))
        self.assertNotIn("companion_mass", a)
        self.assertNotIn("black_hole_probability", a)

    def test_mc_overflow_fails_closed(self):
        r = covariance_fixture()
        r.update({term: "1e200" for term in TERMS})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with self.assertRaises(ValueError):
                propagate(r, 128)

    def test_no_match_is_not_novel_and_bh3_is_excluded(self):
        known, _ = bundled_catalogs()
        r = measure(covariance_fixture(), 128)
        self.assertEqual(disposition(r, {})["novelty_status"], "UNKNOWN_NOT_CLEARED")
        r["source_id"] = "4318465066420528000"
        self.assertEqual(disposition(r, known)["status"], "EXCLUDE_KNOWN_BH")

    def test_frozen_budget_and_overlap_gate(self):
        # Synthetic protocol fixture only. Never evaluate real sky holdouts in
        # disposable test ledgers. This tests the evaluator, not science yield.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "run"
            ledger = root / "ledger.json"
            out.mkdir()
            ids = [str(i) for i in range(1, 100) if partition(str(i)) == "test"][:2]
            records = [
                {
                    "source_id": sid,
                    "record_id": sid + ":Orbital",
                    "nss_solution_type": "Orbital",
                    "status": "HOLD_QUALITY_AND_NOVELTY",
                    "f_phot_solar": 4.0,
                    "parallax_relative_error": 0.01,
                    "period_relative_error": 0.01,
                    "efficiency": 0.8,
                    "fixture": "SYNTHETIC_PROTOCOL_ONLY",
                }
                for sid in ids
            ]
            (out / "records.json").write_text(json.dumps(records))
            (out / "recursion.json").write_text(
                json.dumps({"review_budget": 1, "adopted_configuration": HarnessBundle().to_dict()})
            )
            manifest = {
                "guard_hash": "synthetic-fixture-guard",
                "dataset_sha256": "synthetic-protocol-only",
                "output_hashes": {name: sha(out / name) for name in ["records.json", "recursion.json"]},
            }
            (out / "run_manifest.json").write_text(json.dumps(manifest))
            with patch("harness2.cli.universe.verify_guard", return_value="synthetic-fixture-guard"):
                first = evaluate_holdout(out, ledger)
            self.assertEqual(first["review_budget"], 1)
            self.assertLessEqual(first["heldout_utility"]["evaluated"], 1)
            self.assertTrue(first["test_source_ids"])
            manifest = json.loads((out / "run_manifest.json").read_text())
            manifest["dataset_sha256"] = "changed-dataset-with-identical-test-sources"
            (out / "run_manifest.json").write_text(json.dumps(manifest))
            with patch("harness2.cli.universe.verify_guard", return_value="synthetic-fixture-guard"):
                with self.assertRaisesRegex(ValueError, "Overlapping"):
                    evaluate_holdout(out, ledger)


if __name__ == "__main__":
    unittest.main()
