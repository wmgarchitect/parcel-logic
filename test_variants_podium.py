"""Tests for variants_podium.py — pinned to hand-checked numbers."""

import unittest

from variants_podium import (PODIUM_FLOOR_HEIGHT, TOWER_WIDTH,
                             generate_podium_grid, podium_grid_to_csv,
                             twin_rect_gap)
from variants import SITE_ZONE
from zoning import PLATE, SITE


class TestPodiumGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = generate_podium_grid()
        cls.by_key = {(r.podium_floors, r.podium_coverage,
                       r.tower_length, r.tower_floor_height): r
                      for r in cls.rows}

    def test_tower_width_is_the_plate_rule(self):
        self.assertEqual(TOWER_WIDTH, PLATE.max_depth)

    def test_hand_checked_p030_class_scheme(self):
        # podium 2 fl x cov 0.50, towers 28x22 @ 2.8
        r = self.by_key[(2, 0.50, 28.0, 2.8)]
        self.assertEqual(r.tower_floors, 19)          # solved, not guessed
        self.assertAlmostEqual(r.massing.gfa, 31_221.25, delta=1.0)
        self.assertAlmostEqual(r.massing.height, 62.2, places=1)
        self.assertTrue(r.ok_intent)

    def test_gfa_never_overshoots_kaks(self):
        for r in self.rows:
            self.assertLessEqual(r.massing.gfa, SITE.max_gfa + 1e-6, r.label)

    def test_height_never_overshoots_hmaks(self):
        for r in self.rows:
            self.assertLessEqual(r.massing.height, SITE.hmaks + 1e-6, r.label)

    def test_all_tower_plates_buildable(self):
        for r in self.rows:
            for t in r.massing.towers:
                self.assertLessEqual(min(t.length, t.width),
                                     PLATE.max_depth + 1e-6, r.label)

    def test_no_toothless_towers(self):
        for r in self.rows:
            self.assertGreaterEqual(r.tower_floors, 4, r.label)

    def test_gap_estimate_geometry(self):
        self.assertAlmostEqual(twin_rect_gap(SITE_ZONE, 28.0),
                               SITE_ZONE.length - 56.0, places=6)

    def test_csv_shape(self):
        text = podium_grid_to_csv(self.rows)
        lines = text.strip().splitlines()
        self.assertEqual(len(lines), len(self.rows) + 1)
        self.assertIn("sellable_est_m2", lines[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
