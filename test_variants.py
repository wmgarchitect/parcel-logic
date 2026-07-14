"""Tests for variants.py — the Session 6 generator scaffold.

Run:  python3 test_variants.py   (or pytest)
"""

import math
import unittest

from variants import (COVERAGES, FLOOR_HEIGHTS, SITE_ZONE, SetbackZone,
                      generate_grid, grid_to_csv)


class TestSetbackZone(unittest.TestCase):
    def test_rectangle_equivalent_matches_measurements(self):
        # Session 1: area 6,055.66 m2, perimeter 333.84 m
        self.assertAlmostEqual(SITE_ZONE.length * SITE_ZONE.width,
                               SITE_ZONE.area, places=6)
        self.assertAlmostEqual(2 * (SITE_ZONE.length + SITE_ZONE.width),
                               SITE_ZONE.perimeter, places=6)
        self.assertAlmostEqual(SITE_ZONE.length, 113.6, delta=0.1)
        self.assertAlmostEqual(SITE_ZONE.width, 53.3, delta=0.1)

    def test_twin_block_gap(self):
        # two 625 m2 square blocks (25 m side): 113.6 - 50 = ~63.6 m
        self.assertAlmostEqual(SITE_ZONE.twin_block_gap(625.0), 63.63, delta=0.05)

    def test_degenerate_zone_falls_back_to_square(self):
        z = SetbackZone(area=100.0, perimeter=10.0)  # impossible rectangle
        self.assertAlmostEqual(z.length, 10.0)
        self.assertAlmostEqual(z.width, 10.0)

    def test_bad_block_area_raises(self):
        with self.assertRaises(ValueError):
            SITE_ZONE.twin_block_gap(0)


class TestGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = generate_grid()
        cls.by_key = {(r.coverage, r.floor_height, r.blocks): r
                      for r in cls.rows}

    def test_grid_size(self):
        self.assertEqual(len(self.rows),
                         len(COVERAGES) * len(FLOOR_HEIGHTS) * 2)  # 72

    def test_single_block_has_no_spacing(self):
        r = self.by_key[(0.25, 3.2, 1)]
        self.assertIsNone(r.spacing)
        self.assertIsNone(r.gap_available)
        self.assertTrue(r.ok_legal and r.ok_intent)

    def test_twin_19fl_low_floors_protects_daylight(self):
        # cov 0.20, fh 2.8, twin: 19 fl, 53.2 m tall, gap ~57.7 m
        r = self.by_key[(0.20, 2.8, 2)]
        self.assertTrue(r.zoning.ok)
        self.assertTrue(r.ok_legal)
        self.assertTrue(r.ok_intent, str(r.spacing))

    def test_twin_near_miss_by_centimeters(self):
        # cov 0.25, fh 3.2, twin: height 51.2 m vs gap ~51.1 m —
        # fails the intent line by ~10 cm. Rules are strict.
        r = self.by_key[(0.25, 3.2, 2)]
        self.assertTrue(r.ok_legal)
        self.assertFalse(r.ok_intent)

    def test_twin_overheight_fails_zoning_not_just_spacing(self):
        # cov 0.10, fh 2.8, twin: 40 fl = 112 m > Hmaks
        r = self.by_key[(0.10, 2.8, 2)]
        self.assertFalse(r.zoning.ok)
        self.assertFalse(r.ok_legal)

    def test_intent_implies_legal(self):
        for r in self.rows:
            if r.ok_intent:
                self.assertTrue(r.ok_legal, r.label)

    def test_csv_shape(self):
        text = grid_to_csv(self.rows)
        lines = text.strip().splitlines()
        self.assertEqual(len(lines), len(self.rows) + 1)
        self.assertIn("gap_intent_req_m", lines[0])
        # single-block rows leave spacing columns empty
        first_single = lines[1].split(",")
        self.assertEqual(first_single[9], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
