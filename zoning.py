"""zoning.py — Turkish zoning rules as executable code.

Part of Parcel Logic, a constraint-to-form lab for computational massing:
https://archicoder.com

Encodes the three numbers that govern what can be built on a Turkish
parcel, and makes any massing self-reporting against them:

    KAKS  (emsal / FAR)      — total GFA ceiling, as a multiple of parcel area
    TAKS                     — footprint ceiling, as a fraction of parcel area
    Hmaks (Yencok)           — maximum building height in meters

Study site: Merdivenkoy 3412/3, Kadikoy, Istanbul — 7,813.31 m2,
KAKS 4.00 / TAKS 0.50 / Hmaks 80 m (26.12.2017 1/1000 plan, build-era
rules of the Transform Fikirtepe towers). See SITE at the bottom.

Pure Python 3, standard library only. Runs identically standalone and
inside a Grasshopper Python 3 component.

    >>> from zoning import SITE, Massing, check
    >>> report = check(Massing(footprint=1250, floors=25, floor_height=3.2), SITE)
    >>> report.ok
    True

Units: meters and square meters throughout. GFA here is emsal GFA
counted as footprint x floors (the V01 simplification used across
Sessions 1-3; basement/common-area emsal rules are out of scope).
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

__version__ = "0.2.0"
__all__ = [
    "ZoningEnvelope",
    "Massing",
    "Check",
    "ComplianceReport",
    "check",
    "massing_from_coverage",
    "sweep_coverage",
    "variants_to_csv",
    "DaylightRule",
    "SpacingReport",
    "check_spacing",
    "DAYLIGHT",
    "SITE",
]


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ZoningEnvelope:
    """A parcel plus the plan rules that bind it.

    Attributes:
        parcel_area:  tapu (deed) area in m2.
        kaks:         FAR / emsal — max GFA = kaks * parcel_area.
        taks:         max footprint ratio — max footprint = taks * parcel_area.
        hmaks:        max building height in meters.
        name:         optional label for reports.
    """

    parcel_area: float
    kaks: float
    taks: float
    hmaks: float
    name: str = ""

    @property
    def max_footprint(self) -> float:
        """TAKS ceiling in m2."""
        return self.taks * self.parcel_area

    @property
    def max_gfa(self) -> float:
        """KAKS ceiling in m2 (emsal GFA)."""
        return self.kaks * self.parcel_area

    @property
    def min_floors_at_max_footprint(self) -> int:
        """Floors needed to consume max_gfa on the largest legal footprint.

        The 'fat slab' end of the legal spectrum.
        """
        return math.ceil(self.max_gfa / self.max_footprint)

    def max_floors(self, floor_height: float) -> int:
        """Most floors that fit under Hmaks at a given floor height."""
        if floor_height <= 0:
            raise ValueError("floor_height must be positive")
        return math.floor(self.hmaks / floor_height)


# ---------------------------------------------------------------------------
# A massing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Massing:
    """One candidate building (or set of towers) on the parcel.

    Attributes:
        footprint:    combined ground coverage in m2 (all towers together).
        floors:       floor count (uniform across towers in V01).
        floor_height: floor-to-floor height in meters.
        label:        optional name for reports ("twin towers", "fat slab"...).
    """

    footprint: float
    floors: int
    floor_height: float
    label: str = ""

    @property
    def gfa(self) -> float:
        """Emsal GFA, V01 counting: footprint x floors."""
        return self.footprint * self.floors

    @property
    def height(self) -> float:
        """Total height in meters."""
        return self.floors * self.floor_height

    def coverage(self, envelope: ZoningEnvelope) -> float:
        """Footprint as a fraction of parcel area (the achieved TAKS)."""
        return self.footprint / envelope.parcel_area

    def far(self, envelope: ZoningEnvelope) -> float:
        """GFA as a multiple of parcel area (the achieved KAKS)."""
        return self.gfa / envelope.parcel_area


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Check:
    """One rule checked against one massing."""

    rule: str        # "TAKS", "KAKS", "Hmaks", "Spacing-legal", ...
    value: float     # what the massing does
    limit: float     # what the rule demands
    ok: bool
    unit: str = "m2"
    relation: str = "<="  # "<=" ceiling rules, ">=" floor rules (spacing)

    def __str__(self) -> str:
        mark = "PASS" if self.ok else "FAIL"
        word = "required" if self.relation == ">=" else "allowed"
        return (f"{self.rule:<14} {mark}  "
                f"{self.value:,.2f} {self.unit} of {self.limit:,.2f} {self.unit} {word}")


@dataclass(frozen=True)
class ComplianceReport:
    """All checks for one massing against one envelope."""

    massing: Massing
    envelope: ZoningEnvelope
    checks: List[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def __str__(self) -> str:
        title = self.massing.label or "massing"
        head = (f"{title}: {self.massing.footprint:,.0f} m2 x {self.massing.floors} fl "
                f"@ {self.massing.floor_height} m -> "
                f"GFA {self.massing.gfa:,.0f} m2, H {self.massing.height:.1f} m")
        lines = [head] + ["  " + str(c) for c in self.checks]
        lines.append("  => " + ("COMPLIANT" if self.ok else "NON-COMPLIANT"))
        return "\n".join(lines)


TOLERANCE = 1e-6  # float slack so "exactly at the limit" counts as legal


def check(massing: Massing, envelope: ZoningEnvelope) -> ComplianceReport:
    """Check one massing against TAKS, KAKS and Hmaks. Returns a full report."""
    checks = [
        Check("TAKS", massing.footprint, envelope.max_footprint,
              massing.footprint <= envelope.max_footprint + TOLERANCE),
        Check("KAKS", massing.gfa, envelope.max_gfa,
              massing.gfa <= envelope.max_gfa + TOLERANCE),
        Check("Hmaks", massing.height, envelope.hmaks,
              massing.height <= envelope.hmaks + TOLERANCE, unit="m"),
    ]
    return ComplianceReport(massing=massing, envelope=envelope, checks=checks)


# ---------------------------------------------------------------------------
# Variant generation
# ---------------------------------------------------------------------------

def massing_from_coverage(envelope: ZoningEnvelope,
                          coverage: float,
                          floor_height: float,
                          target_gfa: Optional[float] = None,
                          label: str = "") -> Massing:
    """Build the massing implied by a coverage ratio.

    Given a coverage (fraction of parcel), the footprint follows, and the
    floor count is whatever consumes target_gfa (default: the full KAKS
    ceiling) on that footprint — floor count is floored, never rounded up,
    so the result cannot overshoot the GFA target by construction. It may
    still break Hmaks: that is exactly what check() is for.
    """
    if not 0 < coverage <= 1:
        raise ValueError("coverage must be in (0, 1]")
    footprint = coverage * envelope.parcel_area
    gfa_target = envelope.max_gfa if target_gfa is None else target_gfa
    floors = max(1, math.floor(gfa_target / footprint))
    return Massing(footprint=footprint, floors=floors,
                   floor_height=floor_height, label=label)


def sweep_coverage(envelope: ZoningEnvelope,
                   coverages: Iterable[float],
                   floor_height: float,
                   target_gfa: Optional[float] = None) -> List[ComplianceReport]:
    """One report per coverage ratio — the fat-slab <-> slim-tower spectrum."""
    reports = []
    for cov in coverages:
        m = massing_from_coverage(envelope, cov, floor_height,
                                  target_gfa, label=f"coverage {cov:.2f}")
        reports.append(check(m, envelope))
    return reports


def variants_to_csv(reports: Iterable[ComplianceReport],
                    path: Optional[str] = None) -> str:
    """Write variant metrics to CSV. Returns the CSV text; writes to path if given."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["label", "footprint_m2", "coverage", "floors",
                     "floor_height_m", "height_m", "gfa_m2", "far",
                     "taks_ok", "kaks_ok", "hmaks_ok", "compliant"])
    for r in reports:
        m, e = r.massing, r.envelope
        by_rule = {c.rule: c.ok for c in r.checks}
        writer.writerow([m.label, f"{m.footprint:.2f}", f"{m.coverage(e):.4f}",
                         m.floors, m.floor_height, f"{m.height:.2f}",
                         f"{m.gfa:.2f}", f"{m.far(e):.4f}",
                         by_rule["TAKS"], by_rule["KAKS"], by_rule["Hmaks"], r.ok])
    text = buf.getvalue()
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


# ---------------------------------------------------------------------------
# Daylight: spacing between facing blocks (Session 5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DaylightRule:
    """Two-level spacing rule between facing residential blocks.

    LEGAL level (Planli Alanlar Imar Yonetmeligi): the side-garden
    distance is side_min for buildings up to floor_threshold floors,
    plus side_per_floor for every floor above it. Blocks on the same
    parcel must stand at least the SUM of their two side distances
    apart. For twin 25-floor towers: (3 + 0.5*21) * 2 = 27 m.

    INTENT level (the lab's committed rule, stricter than code):
    daylight to the units. From the base of one block, the top of the
    facing block must stay below obstruction_angle_deg above the
    horizon: spacing >= shading_height / tan(angle). At the default
    45 degrees, an 80 m tower demands 80 m of clear space - which is
    exactly why protecting daylight costs floor area. The angle is a
    design commitment, not law; sweep it to see the cost curve.
    """

    side_min: float = 3.0
    side_per_floor: float = 0.5
    floor_threshold: int = 4
    obstruction_angle_deg: float = 45.0

    def side_distance(self, floors: int) -> float:
        """Legal side-garden distance for a block of `floors` floors."""
        extra = max(0, floors - self.floor_threshold)
        return self.side_min + self.side_per_floor * extra

    def legal_spacing(self, floors_a: int, floors_b: int) -> float:
        """Legal minimum distance between two blocks on one parcel."""
        return self.side_distance(floors_a) + self.side_distance(floors_b)

    def intent_spacing(self, shading_height: float) -> float:
        """Intent minimum distance so the facing block keeps its light."""
        if shading_height < 0:
            raise ValueError("shading_height must be >= 0")
        angle = math.radians(self.obstruction_angle_deg)
        if not 0 < angle < math.pi / 2:
            raise ValueError("obstruction_angle_deg must be in (0, 90)")
        return shading_height / math.tan(angle)


DAYLIGHT = DaylightRule()


@dataclass(frozen=True)
class SpacingReport:
    """Spacing between two facing blocks checked at both levels."""

    massing_a: Massing
    massing_b: Massing
    available: float
    rule: DaylightRule
    checks: List[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def __str__(self) -> str:
        a, b = self.massing_a, self.massing_b
        head = (f"spacing {a.label or 'A'} <-> {b.label or 'B'}: "
                f"{self.available:,.1f} m available")
        lines = [head] + ["  " + str(c) for c in self.checks]
        lines.append("  => " + ("DAYLIGHT OK" if self.ok else "DAYLIGHT VIOLATED"))
        return "\n".join(lines)


def check_spacing(massing_a: Massing, massing_b: Massing,
                  available: float,
                  rule: DaylightRule = DAYLIGHT) -> SpacingReport:
    """Check the gap between two facing blocks: legal floor, then intent.

    `available` is the clear distance between the facing facades.
    The intent check uses the taller block as the shading mass (worst
    case for the units at the base of the other).
    """
    legal = rule.legal_spacing(massing_a.floors, massing_b.floors)
    shading = max(massing_a.height, massing_b.height)
    intent = rule.intent_spacing(shading)
    checks = [
        Check("Spacing-legal", available, legal,
              available + TOLERANCE >= legal, unit="m", relation=">="),
        Check("Spacing-intent", available, intent,
              available + TOLERANCE >= intent, unit="m", relation=">="),
    ]
    return SpacingReport(massing_a=massing_a, massing_b=massing_b,
                         available=available, rule=rule, checks=checks)


# ---------------------------------------------------------------------------
# The study site
# ---------------------------------------------------------------------------

SITE = ZoningEnvelope(
    parcel_area=7_813.31,   # m2, tapu
    kaks=4.00,
    taks=0.50,
    hmaks=80.0,             # m
    name="Merdivenkoy 3412/3, Kadikoy (build-era 2017 plan)",
)


def _demo() -> None:  # pragma: no cover
    print(f"Site: {SITE.name}")
    print(f"  parcel        {SITE.parcel_area:,.2f} m2")
    print(f"  max footprint {SITE.max_footprint:,.2f} m2  (TAKS {SITE.taks})")
    print(f"  max GFA       {SITE.max_gfa:,.2f} m2  (KAKS {SITE.kaks})")
    print(f"  max height    {SITE.hmaks:.0f} m")
    print()
    print("Same GFA, three legal buildings:")
    # Note: the exact TAKS footprint is 3,906.655 m2. The rounded 3,906.66
    # from the diagrams overshoots the KAKS ceiling by 0.04 m2 across 8
    # floors. Rules are strict; diagrams round. The code doesn't.
    for m in (
        Massing(SITE.max_footprint, 8, 4.0, label="A - fat slab"),
        Massing(0.20 * SITE.parcel_area, 20, 4.0, label="B - slim tower"),
        Massing(1_250.00, 25, 3.2, label="C - twin towers (built reality)"),
    ):
        print()
        print(check(m, SITE))


if __name__ == "__main__":
    _demo()
