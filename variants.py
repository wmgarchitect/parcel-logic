"""variants.py — the V01 variant generator (Session 6 scaffold).

Sweeps the design space the sliders define — coverage ratio, floor
height, one or two blocks — and evaluates every candidate against the
full rule set from zoning.py: TAKS/KAKS/Hmaks, plus (for twin blocks)
the two-level daylight spacing rule.

Geometry honesty: this module is geometry-free. The gap available
between twin blocks is estimated on a rectangle-equivalent of the
setback zone (solved from its measured area and perimeter), with
square block footprints placed at the rectangle's short ends. The
Grasshopper model measures the real polygon; this estimate exists so
the generator can rank candidates without a CAD kernel, and its
assumptions are printed into the CSV where they can be checked.

    >>> from variants import generate_grid, SITE_ZONE
    >>> rows = generate_grid()
    >>> sum(1 for r in rows if r.ok_intent)   # how many protect daylight
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from zoning import (DAYLIGHT, SITE, Check, DaylightRule, Massing,
                    SpacingReport, ZoningEnvelope, check, check_spacing,
                    massing_from_coverage)

__version__ = "0.1.0"
__all__ = [
    "SetbackZone",
    "VariantResult",
    "generate_grid",
    "grid_to_csv",
    "SITE_ZONE",
    "COVERAGES",
    "FLOOR_HEIGHTS",
]


# ---------------------------------------------------------------------------
# The buildable zone, geometry-free
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SetbackZone:
    """Rectangle-equivalent of the setback zone.

    From measured area A and perimeter P, the rectangle with the same
    A and P has sides solving x^2 - (P/2)x + A = 0. For the Session 1
    measurements (6,055.66 m2, 333.84 m) that gives ~113.6 x 53.3 m —
    an elongated zone, which matches the drawn polygon.
    """

    area: float
    perimeter: float

    @property
    def _sides(self) -> Tuple[float, float]:
        half_p = self.perimeter / 2.0
        disc = half_p * half_p - 4.0 * self.area
        if disc < 0:
            # No rectangle matches (very non-rectangular zone): fall
            # back to a square of the same area.
            s = math.sqrt(self.area)
            return (s, s)
        root = math.sqrt(disc)
        return ((half_p + root) / 2.0, (half_p - root) / 2.0)

    @property
    def length(self) -> float:
        """Long side of the rectangle-equivalent."""
        return self._sides[0]

    @property
    def width(self) -> float:
        """Short side of the rectangle-equivalent."""
        return self._sides[1]

    def twin_block_gap(self, block_area: float) -> float:
        """Estimated clear gap between two square blocks of block_area
        placed at the short ends of the zone."""
        if block_area <= 0:
            raise ValueError("block_area must be positive")
        side = math.sqrt(block_area)
        return self.length - 2.0 * side


SITE_ZONE = SetbackZone(area=6_055.66, perimeter=333.84)  # Session 1, 5 m setback


# ---------------------------------------------------------------------------
# One evaluated candidate
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VariantResult:
    """One point of the design space, fully evaluated."""

    index: int
    coverage: float
    floor_height: float
    blocks: int                      # 1 or 2
    massing: Massing                 # combined footprint x floors
    zoning: "object"                 # ComplianceReport
    spacing: Optional[SpacingReport] # None for single block
    gap_available: Optional[float]   # None for single block

    @property
    def ok_legal(self) -> bool:
        """Zoning compliant + legal spacing (if twin)."""
        if not self.zoning.ok:
            return False
        if self.spacing is None:
            return True
        legal = next(c for c in self.spacing.checks if c.rule == "Spacing-legal")
        return legal.ok

    @property
    def ok_intent(self) -> bool:
        """ok_legal + the daylight intent line (if twin)."""
        if not self.ok_legal:
            return False
        if self.spacing is None:
            return True
        return self.spacing.ok

    @property
    def label(self) -> str:
        return "v{:03d} cov {:.2f} fh {:.1f} x{}".format(
            self.index, self.coverage, self.floor_height, self.blocks)


# ---------------------------------------------------------------------------
# The generator
# ---------------------------------------------------------------------------

COVERAGES = tuple(round(0.10 + 0.05 * i, 2) for i in range(9))   # 0.10..0.50
FLOOR_HEIGHTS = (2.8, 3.2, 3.6, 4.0)


def generate_grid(envelope: ZoningEnvelope = SITE,
                  zone: SetbackZone = SITE_ZONE,
                  coverages: Sequence[float] = COVERAGES,
                  floor_heights: Sequence[float] = FLOOR_HEIGHTS,
                  blocks_options: Sequence[int] = (1, 2),
                  rule: DaylightRule = DAYLIGHT) -> List[VariantResult]:
    """Evaluate the full grid. Every candidate gets every check."""
    results: List[VariantResult] = []
    idx = 0
    for cov in coverages:
        for fh in floor_heights:
            for blocks in blocks_options:
                m = massing_from_coverage(envelope, cov, fh)
                m = Massing(m.footprint, m.floors, m.floor_height,
                            label="v{:03d}".format(idx))
                zoning_report = check(m, envelope)
                spacing_report = None
                gap = None
                if blocks == 2:
                    block = Massing(m.footprint / 2.0, m.floors,
                                    m.floor_height,
                                    label=m.label + " block")
                    gap = zone.twin_block_gap(block.footprint)
                    spacing_report = check_spacing(block, block,
                                                   available=max(gap, 0.0),
                                                   rule=rule)
                results.append(VariantResult(
                    index=idx, coverage=cov, floor_height=fh, blocks=blocks,
                    massing=m, zoning=zoning_report,
                    spacing=spacing_report, gap_available=gap))
                idx += 1
    return results


def grid_to_csv(results: Sequence[VariantResult],
                path: Optional[str] = None) -> str:
    """Write the evaluated grid to CSV. Returns the text."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "coverage", "floor_h_m", "blocks",
                "footprint_total_m2", "floors", "height_m", "gfa_m2", "far",
                "gap_available_m", "gap_legal_req_m", "gap_intent_req_m",
                "zoning_ok", "spacing_legal_ok", "spacing_intent_ok",
                "ok_legal", "ok_intent"])
    for r in results:
        m = r.massing
        legal_req = intent_req = gap = ""
        legal_ok = intent_ok = ""
        if r.spacing is not None:
            by_rule = {c.rule: c for c in r.spacing.checks}
            legal_req = "{:.2f}".format(by_rule["Spacing-legal"].limit)
            intent_req = "{:.2f}".format(by_rule["Spacing-intent"].limit)
            legal_ok = by_rule["Spacing-legal"].ok
            intent_ok = by_rule["Spacing-intent"].ok
            gap = "{:.2f}".format(r.gap_available)
        w.writerow([r.index, r.coverage, r.floor_height, r.blocks,
                    "{:.2f}".format(m.footprint), m.floors,
                    "{:.2f}".format(m.height), "{:.2f}".format(m.gfa),
                    "{:.4f}".format(m.far(SITE)),
                    gap, legal_req, intent_req,
                    r.zoning.ok, legal_ok, intent_ok,
                    r.ok_legal, r.ok_intent])
    text = buf.getvalue()
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


def _demo() -> None:  # pragma: no cover
    rows = generate_grid()
    legal = [r for r in rows if r.ok_legal]
    intent = [r for r in rows if r.ok_intent]
    print("variants evaluated: {}".format(len(rows)))
    print("legal (zoning + spacing floor): {}".format(len(legal)))
    print("protect daylight (intent):      {}".format(len(intent)))
    print()
    print("zone rectangle-equivalent: {:.1f} x {:.1f} m".format(
        SITE_ZONE.length, SITE_ZONE.width))
    print()
    for r in intent[:10]:
        m = r.massing
        gap = "gap {:.1f} m".format(r.gap_available) if r.gap_available else "single block"
        print("  {}  -> {} fl, GFA {:,.0f} m2, {}".format(
            r.label, m.floors, m.gfa, gap))


if __name__ == "__main__":
    _demo()
