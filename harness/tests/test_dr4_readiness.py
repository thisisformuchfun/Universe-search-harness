"""DR4 readiness checker. Offline: the NSS columns come from the bundled real DR3
TAP_SCHEMA snapshot; every other archive row here is synthetic test data."""

import csv
import importlib.util
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness2.universe.connectors.public_archives import ArchiveError, PublicSkyConnector

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dr4_readiness", ROOT / "scripts/dr4_readiness.py")
dr4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr4)


def dr3_like(release="gaiadr3", drop=()):
    """TAP_SCHEMA rows: real DR3 NSS column names, gaia_source columns from requirements."""
    text = (ROOT / "data/pilot/nss_schema.csv").read_text(encoding="utf-8")
    nss = [r["column_name"] for r in csv.DictReader(text.splitlines())]
    src = dr4.requirements(release)["tables"][f"{release}.gaia_source"]["selected_columns"]
    tables = [{"table_name": f"{release}.{t}"} for t in ("gaia_source", "nss_two_body_orbit", "dr2_neighbourhood")]
    columns = [{"table_name": f"{release}.nss_two_body_orbit", "column_name": c} for c in nss if c not in drop]
    columns += [{"table_name": f"{release}.gaia_source", "column_name": c} for c in src if c not in drop]
    return tables, columns


def sample(kind="Orbital", bit=8191, length=66, nan=0):
    return {"nss_solution_type": kind, "bit_index": bit, "corr_vec": [0.1] * (length - nan) + [None] * nan}


class ReadinessTests(unittest.TestCase):
    def test_release_name_is_validated(self):
        self.assertEqual(dr4.check_release("gaiadr4"), "gaiadr4")
        for bad in ["gaiadr4; DROP", "GAIADR4", "gaiadr4.gaia_source", "dr4", "", "gaiadr4'"]:
            with self.assertRaises(ValueError):
                dr4.check_release(bad)

    def test_dr3_schema_is_compatible(self):
        tables, columns = dr3_like()
        report = dr4.assess("gaiadr3", tables, columns, [sample(), sample("AstroSpectroSB1", 65535, 105)])
        self.assertEqual(report["status"], "SCHEMA_COMPATIBLE")
        self.assertEqual(report["layout"]["status"], "MATCHES")
        self.assertEqual(report["candidate_tables"]["cross_release_match"], ["gaiadr3.dr2_neighbourhood"])

    def test_unpublished_release(self):
        report = dr4.assess("gaiadr4", [], [])
        self.assertEqual(report["status"], "NOT_PUBLISHED")

    def test_missing_columns_are_incompatible(self):
        tables, columns = dr3_like("gaiadr4", drop=("a_thiele_innes", "ipd_gof_harmonic_amplitude"))
        report = dr4.assess("gaiadr4", tables, columns)
        self.assertEqual(report["status"], "INCOMPATIBLE")
        nss = report["tables"]["gaiadr4.nss_two_body_orbit"]
        self.assertEqual(nss["missing_core_columns"], ["a_thiele_innes"])
        src = report["tables"]["gaiadr4.gaia_source"]
        self.assertEqual(src["missing_selected_columns"], ["ipd_gof_harmonic_amplitude"])
        self.assertEqual(src["missing_core_columns"], [])

    def test_missing_table_is_incompatible(self):
        tables, columns = dr3_like("gaiadr4")
        tables = [t for t in tables if not t["table_name"].endswith("nss_two_body_orbit")]
        report = dr4.assess("gaiadr4", tables, columns)
        self.assertEqual(report["status"], "INCOMPATIBLE")
        self.assertFalse(report["tables"]["gaiadr4.nss_two_body_orbit"]["present"])

    def test_unqualified_and_uppercase_names(self):
        tables, columns = dr3_like("gaiadr4")
        tables = [{"table_name": t["table_name"].split(".")[1].upper()} for t in tables]
        columns = [{"table_name": c["table_name"], "column_name": c["column_name"].upper()} for c in columns]
        self.assertEqual(dr4.assess("gaiadr4", tables, columns)["status"], "SCHEMA_COMPATIBLE")

    def test_layouts_the_parser_would_reject(self):
        tables, columns = dr3_like("gaiadr4")
        for rows in (
            [sample(length=231, nan=165)],  # padded storage
            [sample(bit=4095)],  # reduced parameterization
            [sample(length=66, nan=1)],
            [],  # supported solution types absent or renamed
        ):
            report = dr4.assess("gaiadr4", tables, columns, rows)
            self.assertEqual(report["status"], "NEEDS_PARSER_REVIEW", rows[:1])
        layout = dr4.summarize_layouts([sample(), sample(length=231, nan=165)])
        self.assertEqual(layout["status"], "MISMATCH")
        accepted = {g["corr_vec_length"]: g["accepted_by_current_parser"] for g in layout["layouts"]}
        self.assertEqual(accepted, {66: True, 231: False})

    def test_string_corr_vec(self):
        layout = dr4.summarize_layouts([{**sample(), "corr_vec": "[" + ", ".join(["0.1"] * 66) + "]"}])
        self.assertEqual(layout["status"], "MATCHES")

    def test_discovery_hints(self):
        names = ["gaiadr4.epoch_astrometry", "gaiadr4.epoch_rv", "gaiadr4.dr3_neighbourhood", "gaiadr4.gaia_source"]
        found = dr4.discover(names)
        self.assertEqual(found["epoch_astrometry"], ["gaiadr4.epoch_astrometry"])
        self.assertEqual(found["epoch_radial_velocity"], ["gaiadr4.epoch_rv"])
        self.assertEqual(found["cross_release_match"], ["gaiadr4.dr3_neighbourhood"])
        self.assertNotIn("gaiadr4.gaia_source", sum(found.values(), []))

    def test_requirements_track_connector_and_policy(self):
        source = inspect.getsource(PublicSkyConnector.gaia_context)
        for column in dr4.CONTEXT_COLUMNS:
            self.assertIn(column, source)
        policy = json.loads((ROOT / "policy/agent_tools.json").read_text())
        selected = dr4.requirements("gaiadr4")["tables"]["gaiadr4.gaia_source"]["selected_columns"]
        self.assertTrue(set(policy["gaia_quality_columns"]) <= set(selected))

    def test_fetch_builds_bounded_queries_and_reports_archive_failure(self):
        tables, columns = dr3_like("gaiadr4")
        queries = []

        def fake_tap(self, endpoint, query, maxrec=1000, **kw):
            queries.append((query, maxrec))
            if "TAP_SCHEMA.tables" in query:
                return type("R", (), {"rows": tables, "provenance": {"q": 1}})()
            if "TAP_SCHEMA.columns" in query:
                return type("R", (), {"rows": columns, "provenance": {"q": 2}})()
            return type("R", (), {"rows": [sample()] * 3, "provenance": {"q": 3}})()

        with tempfile.TemporaryDirectory() as d, patch.object(PublicSkyConnector, "tap", fake_tap):
            out = dr4.fetch_metadata(PublicSkyConnector(d), "gaiadr4", sample=3)
        self.assertEqual(dr4.assess("gaiadr4", *out[:3])["status"], "SCHEMA_COMPATIBLE")
        self.assertIn("schema_name = 'gaiadr4'", queries[0][0])
        self.assertTrue(queries[2][0].startswith("SELECT TOP 3 nss_solution_type,bit_index,corr_vec FROM gaiadr4."))
        self.assertEqual(queries[2][1], 3)
        with self.assertRaises(ValueError):
            dr4.fetch_metadata(PublicSkyConnector(tempfile.gettempdir()), "gaiadr4", sample=dr4.MAX_SAMPLE + 1)

        def failing_tap(self, *a, **kw):
            raise ArchiveError("synthetic outage")

        with tempfile.TemporaryDirectory() as d, patch.object(PublicSkyConnector, "tap", failing_tap):
            with patch("sys.stdout"):
                code = dr4.main(["check", "--release", "gaiadr4", "--cache", d])
        self.assertEqual(code, 2)

    def test_watchlist_matches_committed_file(self):
        rows = dr4.watchlist(ROOT / "runs/verified-release", ROOT / "data/controls/controls_v1.json")
        roles = [r["roles"] for r in rows]
        self.assertEqual(len(rows), 54)
        self.assertEqual(sum("held" in r for r in roles), 14)
        self.assertEqual(sum("control" in r for r in roles), 42)
        self.assertTrue(all(isinstance(r["dr3_source_id"], str) for r in rows))
        committed = (ROOT / "data/dr4/watchlist.csv").read_text(encoding="utf-8")
        self.assertEqual(dr4.watchlist_csv(rows), committed, "regenerate with scripts/dr4_readiness.py watchlist")


if __name__ == "__main__":
    unittest.main()
