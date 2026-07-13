"""Tests for zoning.py — pinned to the verified Session 0-3 numbers.

Run:  python3 test_zoning.py   (or pytest)
"""

import math
import unittest

from zoning import (SITE, Massing, ZoningEnvelope, check,
                    massing_from_coverage, sweep_coverage, variants_to_csv)


class TestEnvelope(unittest.TestCase):
    """The derived envelope must match the appraisal-verified numbers."""

    def test_max_footprint_taks(self):
        # Session 0: TAKS 0.50 x 7,813.31 = 3,906.66 m2 (rounded)
        self.assertAlmostEqual(SITE.max_footprint, 3_906.655, places=2)

    def test_max_gfa_kaks(self):
        # Session 0: KAKS 4.00 x 7,813.31 = 31,253.24 m2
        self.assertAlmostEqual(SITE.max_gfa, 31_253.24, places=2)

    def test_fat_slab_floor_count(self):
        # Consuming full GFA on the max footprint needs 8 floors
        self.assertEqual(SITE.min_floors_at_max_footprint, 8)

    def test_max_floors_under_hmaks(self):
        self.assertEqual(SITE.max_floors(3.2), 25)   # 25 x 3.2 = 80.0 exactly
        self.assertEqual(SITE.max_floors(4.0), 20)   # 20 x 4.0 = 80.0 exactly
        self.assertEqual(SITE.max_floors(3.5), 22)   # 22 x 3.5 = 77.0


class TestThreeLegalBuildings(unittest.TestCase):
    """Session 2's diagram: same GFA, three legal buildings."""

    def test_a_fat_slab(self):
        r = check(Massing(3_906.66, 8, 4.0, label="fat slab"), SITE)
        # 8 floors x 3,906.66 = 31,253.28 — a hair over the 31,253.24 ceiling
        # from the rounded footprint; use the exact TAKS footprint instead.
        r_exact = check(Massing(SITE.max_footprint, 8, 4.0), SITE)
        self.assertTrue(r_exact.ok, str(r_exact))
        self.assertAlmostEqual(r_exact.massing.height, 32.0)

    def test_b_slim_tower(self):
        r = check(Massing(1_562.66, 20, 4.0, label="slim tower"), SITE)
        self.assertTrue(r.ok, str(r))
        self.assertAlmostEqual(r.massing.height, 80.0)
        self.assertAlmostEqual(r.massing.coverage(SITE), 0.20, places=2)

    def test_c_twin_towers_built_reality(self):
        r = check(Massing(1_250.00, 25, 3.2, label="twin towers"), SITE)
        self.assertTrue(r.ok, str(r))
        self.assertAlmostEqual(r.massing.gfa, 31_250.0)
        self.assertAlmostEqual(r.massing.height, 80.0)
        self.assertAlmostEqual(r.massing.coverage(SITE), 0.16, places=2)


class TestViolationsCaught(unittest.TestCase):
    def test_taks_violation(self):
        r = check(Massing(4_000.0, 7, 4.0), SITE)  # footprint > 3,906.66
        self.assertFalse(r.ok)
        self.assertFalse(next(c for c in r.checks if c.rule == "TAKS").ok)

    def test_kaks_violation(self):
        r = check(Massing(3_000.0, 11, 3.0), SITE)  # 33,000 > 31,253.24
        self.assertFalse(r.ok)
        self.assertFalse(next(c for c in r.checks if c.rule == "KAKS").ok)

    def test_hmaks_violation(self):
        r = check(Massing(1_200.0, 26, 3.2), SITE)  # 83.2 m > 80 m
        self.assertFalse(r.ok)
        self.assertFalse(next(c for c in r.checks if c.rule == "Hmaks").ok)

    def test_at_the_limit_is_legal(self):
        r = check(Massing(SITE.max_footprint, 8, 4.0), SITE)
        self.assertTrue(r.ok, str(r))


class TestVariantGeneration(unittest.TestCase):
    def test_from_coverage_reproduces_built_reality(self):
        m = massing_from_coverage(SITE, 0.16, 3.2)
        self.assertAlmostEqual(m.footprint, 1_250.13, places=2)
        self.assertEqual(m.floors, 25)  # floor(31,253.24 / 1,250.13) = 25
        self.assertTrue(check(m, SITE).ok)

    def test_never_overshoots_gfa(self):
        for cov in (0.10, 0.16, 0.20, 0.30, 0.50):
            m = massing_from_coverage(SITE, cov, 3.2)
            self.assertLessEqual(m.gfa, SITE.max_gfa + 1e-6)

    def test_low_coverage_breaks_hmaks_and_is_caught(self):
        # 8% coverage needs 50 floors x 3.2 = 160 m -> illegal, must be flagged
        r = check(massing_from_coverage(SITE, 0.08, 3.2), SITE)
        self.assertFalse(r.ok)

    def test_sweep_and_csv(self):
        reports = sweep_coverage(SITE, [0.10, 0.16, 0.20, 0.35, 0.50], 3.2)
        self.assertEqual(len(reports), 5)
        text = variants_to_csv(reports)
        lines = text.strip().splitlines()
        self.assertEqual(len(lines), 6)  # header + 5 rows
        self.assertIn("footprint_m2", lines[0])

    def test_bad_inputs_raise(self):
        with self.assertRaises(ValueError):
            massing_from_coverage(SITE, 0.0, 3.2)
        with self.assertRaises(ValueError):
            SITE.max_floors(0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
