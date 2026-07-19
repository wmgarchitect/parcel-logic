"""variants_podium.py — the built typology enters the grid (Session 10).

Generates podium+towers candidates: a shared low base (commercial floor
heights, deep plates allowed) carrying two residential towers whose
plates respect the 22 m depth rule, with tower floors SOLVED so total
above-ground GFA lands under the KAKS ceiling instead of overshooting.

This is the pattern the real project on parcel 3412/3 uses (C+D blocks:
joined through the lower floors, separating into towers above), so the
grid finally contains the developer's own typology, judged by the same
rules as everything else.

Geometry honesty: gaps here are estimates on the zone's long axis
(length minus two tower plate lengths). The Grasshopper viewer measures
real in-polygon placement; these estimates exist to rank candidates
before Rhino is open, and the viewer's drawn gap is the truth.
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass
from typing import List, Optional, Sequence

from zoning import (DAYLIGHT, PLATE, SITE, DaylightRule, PlateRule,
                    PodiumMassing, PodiumReport, Tower, YieldModel, YIELD,
                    ZoningEnvelope, check_podium)
from variants import SITE_ZONE, SetbackZone

__version__ = "0.1.0"
__all__ = ["PodiumVariantResult", "generate_podium_grid",
           "podium_grid_to_csv", "PODIUM_FLOORS", "PODIUM_COVERAGES",
           "TOWER_LENGTHS", "TOWER_FLOOR_HEIGHTS"]


PODIUM_FLOORS = (1, 2, 3)
PODIUM_COVERAGES = (0.30, 0.40, 0.50)        # podium footprint / parcel
TOWER_LENGTHS = (28.0, 34.0, 40.0)           # tower plate long side, m
TOWER_FLOOR_HEIGHTS = (2.8, 3.2)
PODIUM_FLOOR_HEIGHT = 4.5                    # ticaret-class (plan: <= 6.5)
TOWER_WIDTH = PLATE.max_depth                # 22 m — the rule drives the plate


def twin_rect_gap(zone: SetbackZone, tower_length: float) -> float:
    """Estimated clear gap between two tower plates of `tower_length`
    placed at the ends of the zone's long axis."""
    return zone.length - 2.0 * tower_length


@dataclass(frozen=True)
class PodiumVariantResult:
    """One podium+towers candidate, fully evaluated."""

    index: int
    podium_floors: int
    podium_coverage: float
    tower_length: float
    tower_floor_height: float
    tower_floors: int
    massing: PodiumMassing
    report: PodiumReport
    gap_estimate: float

    @property
    def ok_legal(self) -> bool:
        base = all(c.ok for c in self.report.checks)
        if self.report.spacing is None:
            return base
        legal = next(c for c in self.report.spacing.checks
                     if c.rule == "Spacing-legal")
        return base and legal.ok

    @property
    def ok_intent(self) -> bool:
        return self.ok_legal and (self.report.spacing.ok
                                  if self.report.spacing else True)

    @property
    def label(self) -> str:
        return "p{:03d} pod{}x{:.2f} twr{:.0f} fh{:.1f} x{}".format(
            self.index, self.podium_floors, self.podium_coverage,
            self.tower_length, self.tower_floor_height, self.tower_floors)


def generate_podium_grid(envelope: ZoningEnvelope = SITE,
                         zone: SetbackZone = SITE_ZONE,
                         daylight: DaylightRule = DAYLIGHT,
                         plate: PlateRule = PLATE) -> List["PodiumVariantResult"]:
    """Evaluate the podium grid. Tower floors are SOLVED, never guessed:

        remaining = max_gfa - podium_gfa
        floors    = floor(remaining / (2 * tower_plate_area))

    then capped by what Hmaks leaves above the podium. Candidates whose
    towers would get fewer than 4 floors are dropped (that is a podium
    scheme without towers, which the flat grid already covers).
    """
    results: List[PodiumVariantResult] = []
    idx = 0
    for pf in PODIUM_FLOORS:
        for pcov in PODIUM_COVERAGES:
            podium_fp = pcov * envelope.parcel_area
            if podium_fp > envelope.max_footprint:
                continue  # podium itself would break TAKS
            podium_gfa = podium_fp * pf
            podium_h = pf * PODIUM_FLOOR_HEIGHT
            for tl in TOWER_LENGTHS:
                plate_area = tl * TOWER_WIDTH
                for tfh in TOWER_FLOOR_HEIGHTS:
                    remaining = envelope.max_gfa - podium_gfa
                    if remaining <= 0:
                        continue
                    floors_gfa = int(remaining // (2.0 * plate_area))
                    floors_h = int((envelope.hmaks - podium_h) // tfh)
                    floors = min(floors_gfa, floors_h)
                    if floors < 4:
                        continue
                    towers = (Tower(tl, TOWER_WIDTH, floors, tfh),
                              Tower(tl, TOWER_WIDTH, floors, tfh))
                    pm = PodiumMassing(podium_fp, pf, PODIUM_FLOOR_HEIGHT,
                                       towers,
                                       label="p{:03d}".format(idx))
                    gap = twin_rect_gap(zone, tl)
                    rep = check_podium(pm, envelope,
                                       tower_gap=max(gap, 0.0),
                                       daylight=daylight, plate=plate)
                    results.append(PodiumVariantResult(
                        index=idx, podium_floors=pf, podium_coverage=pcov,
                        tower_length=tl, tower_floor_height=tfh,
                        tower_floors=floors, massing=pm, report=rep,
                        gap_estimate=gap))
                    idx += 1
    return results


def podium_grid_to_csv(results: Sequence[PodiumVariantResult],
                       path: Optional[str] = None) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "podium_floors", "podium_cov", "podium_fp_m2",
                "tower_plate", "tower_floors", "tower_fh",
                "height_m", "gfa_m2", "sellable_est_m2", "gap_est_m",
                "ok_legal", "ok_intent"])
    for r in results:
        m = r.massing
        w.writerow([r.index, r.podium_floors, r.podium_coverage,
                    "{:.0f}".format(m.podium_footprint),
                    "{:.0f}x{:.0f}".format(r.tower_length, TOWER_WIDTH),
                    r.tower_floors, r.tower_floor_height,
                    "{:.1f}".format(m.height), "{:.0f}".format(m.gfa),
                    "{:.0f}".format(YIELD.sellable(m.gfa)),
                    "{:.1f}".format(r.gap_estimate),
                    r.ok_legal, r.ok_intent])
    text = buf.getvalue()
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


def _demo() -> None:  # pragma: no cover
    rows = generate_podium_grid()
    legal = [r for r in rows if r.ok_legal]
    intent = [r for r in rows if r.ok_intent]
    print("podium candidates: {}".format(len(rows)))
    print("legal: {}   protect daylight: {}".format(len(legal), len(intent)))
    if intent:
        best = max(intent, key=lambda r: r.massing.gfa)
        m = best.massing
        print()
        print("best daylight-protecting podium scheme:")
        print("  {}  -> GFA {:,.0f} m2 (~{:,.0f} m2 sellable), H {:.1f} m, gap est {:.1f} m".format(
            best.label, m.gfa, YIELD.sellable(m.gfa), m.height, best.gap_estimate))


if __name__ == "__main__":
    _demo()
