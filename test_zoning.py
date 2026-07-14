"""Tests for zoning.py — pinned to the verified Session 0-3 numbers.

Run:  python3 test_zoning.py   (or pytest)
"""

import math
import unittest

from zoning import (DAYLIGHT, SITE, DaylightRule, Massing, ZoningEnvelope,
                    check, check_spacing, massing_from_coverage,
                    sweep_coverage, variants_to_csv)


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


class TestDaylightRule(unittest.TestCase):
    """Session 5: spacing between facing blocks, legal + intent levels."""

    def test_side_distance_regulation_values(self):
        # Planli Alanlar Imar Yonetmeligi: 3.00 m up to 4 floors,
        # +0.50 m for each floor above.
        self.assertAlmostEqual(DAYLIGHT.side_distance(1), 3.0)
        self.assertAlmostEqual(DAYLIGHT.side_distance(4), 3.0)
        self.assertAlmostEqual(DAYLIGHT.side_distance(5), 3.5)
        self.assertAlmostEqual(DAYLIGHT.side_distance(25), 13.5)  # 3 + 0.5*21

    def test_legal_spacing_twin_towers(self):
        # Two 25-floor blocks on one parcel: 13.5 + 13.5 = 27 m
        self.assertAlmostEqual(DAYLIGHT.legal_spacing(25, 25), 27.0)

    def test_intent_spacing_45deg(self):
        # 45 degrees: spacing >= shading height
        self.assertAlmostEqual(DAYLIGHT.intent_spacing(80.0), 80.0, places=6)

    def test_intent_spacing_steeper_angle_is_laxer(self):
        rule60 = DaylightRule(obstruction_angle_deg=60.0)
        self.assertAlmostEqual(rule60.intent_spacing(80.0), 80.0 / math.tan(math.radians(60)), places=6)
        self.assertLess(rule60.intent_spacing(80.0), DAYLIGHT.intent_spacing(80.0))

    def test_built_reality_gap_fails_intent_passes_legal(self):
        # Twin 25-floor towers with a 30 m gap: legal (27 m) OK,
        # intent at 45 degrees (80 m) violated. The note's argument in numbers.
        tower = Massing(625.0, 25, 3.2, label="tower")
        r = check_spacing(tower, tower, available=30.0)
        by_rule = {c.rule: c.ok for c in r.checks}
        self.assertTrue(by_rule["Spacing-legal"])
        self.assertFalse(by_rule["Spacing-intent"])
        self.assertFalse(r.ok)

    def test_generous_gap_passes_both(self):
        tower = Massing(625.0, 25, 3.2)
        r = check_spacing(tower, tower, available=80.0)
        self.assertTrue(r.ok, str(r))

    def test_below_legal_fails_both(self):
        tower = Massing(625.0, 25, 3.2)
        r = check_spacing(tower, tower, available=20.0)
        self.assertFalse(any(c.ok for c in r.checks))

    def test_asymmetric_blocks_use_taller_as_shading(self):
        tall = Massing(625.0, 25, 3.2)    # 80 m
        low = Massing(3906.0, 8, 4.0)     # 32 m
        r = check_spacing(tall, low, available=50.0)
        intent = next(c for c in r.checks if c.rule == "Spacing-intent")
        self.assertAlmostEqual(intent.limit, 80.0)  # taller block shades
        # legal: 13.5 + (3 + 0.5*4) = 18.5
        legal = next(c for c in r.checks if c.rule == "Spacing-legal")
        self.assertAlmostEqual(legal.limit, 18.5)

    def test_bad_angle_raises(self):
        with self.assertRaises(ValueError):
            DaylightRule(obstruction_angle_deg=0).intent_spacing(80)
        with self.assertRaises(ValueError):
            DaylightRule(obstruction_angle_deg=90).intent_spacing(80)


if __name__ == "__main__":
    unittest.main(verbosity=2)
