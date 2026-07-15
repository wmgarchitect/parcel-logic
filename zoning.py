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
from typing import Iterable, List, Optional, Tuple

__version__ = "0.3.0"
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
    "PlateRule",
    "SpacingReport",
    "check_spacing",
    "Tower",
    "PodiumMassing",
    "PodiumReport",
    "check_podium",
    "DAYLIGHT",
    "PLATE",
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
    """Three-level spacing rule between facing residential blocks.

    LEGAL level (Planli Alanlar Imar Yonetmeligi): the side-garden
    distance is side_min for buildings up to floor_threshold floors,
    plus side_per_floor for every floor above it. Blocks on the same
    parcel must stand at least the SUM of their two side distances
    apart. For twin 25-floor towers: (3 + 0.5*21) * 2 = 27 m.

    INTENT level (the lab's committed pass/fail line): spacing >=
    shading_height / tan(intent_angle_deg). The default 60 degrees is
    the h/2-class heuristic used in planning practice: an 80 m tower
    demands ~46 m of clear space. Calibrated 2026-07-16 after the
    first full grid run showed 45 degrees rejecting every twin option
    the parcel can hold (see project log, Session 9).

    ASPIRATION level (reported, never pass/fail): the original 45
    degree line from the opening note - spacing >= full height. Kept
    on every report so the gap between what passes and what would be
    ideal stays visible instead of quietly disappearing.
    """

    side_min: float = 3.0
    side_per_floor: float = 0.5
    floor_threshold: int = 4
    intent_angle_deg: float = 60.0
    aspiration_angle_deg: float = 45.0

    @property
    def obstruction_angle_deg(self) -> float:
        """Backward-compatible alias for the committed intent angle."""
        return self.intent_angle_deg

    def side_distance(self, floors: int) -> float:
        """Legal side-garden distance for a block of `floors` floors."""
        extra = max(0, floors - self.floor_threshold)
        return self.side_min + self.side_per_floor * extra

    def legal_spacing(self, floors_a: int, floors_b: int) -> float:
        """Legal minimum distance between two blocks on one parcel."""
        return self.side_distance(floors_a) + self.side_distance(floors_b)

    def _angle_spacing(self, shading_height: float, angle_deg: float) -> float:
        if shading_height < 0:
            raise ValueError("shading_height must be >= 0")
        angle = math.radians(angle_deg)
        if not 0 < angle < math.pi / 2:
            raise ValueError("angle must be in (0, 90) degrees")
        return shading_height / math.tan(angle)

    def intent_spacing(self, shading_height: float) -> float:
        """Committed pass/fail spacing (intent_angle_deg)."""
        return self._angle_spacing(shading_height, self.intent_angle_deg)

    def aspiration_spacing(self, shading_height: float) -> float:
        """Reported-only spacing at the aspiration angle."""
        return self._angle_spacing(shading_height, self.aspiration_angle_deg)


DAYLIGHT = DaylightRule()


@dataclass(frozen=True)
class PlateRule:
    """Buildability floor for residential floor plates.

    A double-loaded residential plate deeper than ~22 m puts the
    middle of every unit too far from a window: legal massing, dark
    architecture. The efficiency floor from the opening note, encoded.
    Non-residential podium levels are exempt (commercial plates can
    run deep).
    """

    max_depth: float = 22.0

    def check(self, length: float, width: float) -> Check:
        depth = min(length, width)
        return Check("Plate-depth", depth, self.max_depth,
                     depth <= self.max_depth + TOLERANCE, unit="m")


PLATE = PlateRule()


@dataclass(frozen=True)
class SpacingReport:
    """Spacing between two facing blocks.

    `checks` are binding (legal + intent); `aspiration` is reported
    only and never affects `ok`.
    """

    massing_a: Massing
    massing_b: Massing
    available: float
    rule: DaylightRule
    checks: List[Check] = field(default_factory=list)
    aspiration: Optional[Check] = None

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def aspiration_ok(self) -> bool:
        return self.aspiration.ok if self.aspiration else True

    def __str__(self) -> str:
        a, b = self.massing_a, self.massing_b
        head = (f"spacing {a.label or 'A'} <-> {b.label or 'B'}: "
                f"{self.available:,.1f} m available")
        lines = [head] + ["  " + str(c) for c in self.checks]
        if self.aspiration is not None:
            mark = "MET " if self.aspiration.ok else "NOT MET"
            lines.append("  {:<14} {}  {:,.2f} m of {:,.2f} m ({}deg, reported only)".format(
                "Spacing-aspir.", mark, self.aspiration.value,
                self.aspiration.limit, int(self.rule.aspiration_angle_deg)))
        lines.append("  => " + ("DAYLIGHT OK" if self.ok else "DAYLIGHT VIOLATED"))
        return "\n".join(lines)


def check_spacing(massing_a: Massing, massing_b: Massing,
                  available: float,
                  rule: DaylightRule = DAYLIGHT) -> SpacingReport:
    """Check the gap between two facing blocks.

    `available` is the clear distance between the facing facades.
    The shading height is the taller block (worst case for the units
    at the base of the other). Pass/fail checks: legal floor, then
    the committed intent line. The aspiration line (45 degrees) is
    appended as a reported check but does NOT count toward `ok` -
    SpacingReport.ok reads only the binding checks.
    """
    legal = rule.legal_spacing(massing_a.floors, massing_b.floors)
    shading = max(massing_a.height, massing_b.height)
    intent = rule.intent_spacing(shading)
    aspiration = rule.aspiration_spacing(shading)
    checks = [
        Check("Spacing-legal", available, legal,
              available + TOLERANCE >= legal, unit="m", relation=">="),
        Check("Spacing-intent", available, intent,
              available + TOLERANCE >= intent, unit="m", relation=">="),
    ]
    aspiration_check = Check(
        "Spacing-aspir.", available, aspiration,
        available + TOLERANCE >= aspiration, unit="m", relation=">=")
    return SpacingReport(massing_a=massing_a, massing_b=massing_b,
                         available=available, rule=rule, checks=checks,
                         aspiration=aspiration_check)


# ---------------------------------------------------------------------------
# Podium + towers (Session 9): the built typology, representable
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Tower:
    """One residential tower above the podium."""

    length: float          # m, plate long side
    width: float           # m, plate short side (depth for PlateRule)
    floors: int            # floors above the podium
    floor_height: float    # m

    @property
    def footprint(self) -> float:
        return self.length * self.width

    @property
    def height(self) -> float:
        return self.floors * self.floor_height

    @property
    def gfa(self) -> float:
        return self.footprint * self.floors


@dataclass(frozen=True)
class PodiumMassing:
    """A shared low base carrying N towers - the Transform Fikirtepe
    C+D pattern: blocks joined through the lower floors (commercial +
    shared program, deep plates allowed), separating into slender
    residential towers above.

    V01 GFA counting: above-ground only, footprint x floors per part.
    """

    podium_footprint: float      # m2 (this is what TAKS sees)
    podium_floors: int
    podium_floor_height: float   # m (ticaret <= 6.5 per plan notes)
    towers: Tuple["Tower", ...]
    label: str = ""

    @property
    def podium_height(self) -> float:
        return self.podium_floors * self.podium_floor_height

    @property
    def height(self) -> float:
        tallest = max((t.height for t in self.towers), default=0.0)
        return self.podium_height + tallest

    @property
    def footprint(self) -> float:
        return self.podium_footprint

    @property
    def gfa(self) -> float:
        return (self.podium_footprint * self.podium_floors
                + sum(t.gfa for t in self.towers))

    def coverage(self, envelope: ZoningEnvelope) -> float:
        return self.podium_footprint / envelope.parcel_area

    def far(self, envelope: ZoningEnvelope) -> float:
        return self.gfa / envelope.parcel_area


@dataclass(frozen=True)
class PodiumReport:
    """All checks for a podium+towers massing."""

    massing: PodiumMassing
    envelope: ZoningEnvelope
    checks: List[Check] = field(default_factory=list)
    spacing: Optional[SpacingReport] = None

    @property
    def ok(self) -> bool:
        base = all(c.ok for c in self.checks)
        return base and (self.spacing.ok if self.spacing else True)

    def __str__(self) -> str:
        m = self.massing
        head = (f"{m.label or 'podium massing'}: podium {m.podium_footprint:,.0f} m2 "
                f"x {m.podium_floors} fl + {len(m.towers)} towers -> "
                f"GFA {m.gfa:,.0f} m2, H {m.height:.1f} m")
        lines = [head] + ["  " + str(c) for c in self.checks]
        if self.spacing is not None:
            lines += ["  " + l for l in str(self.spacing).split("\n")]
        lines.append("  => " + ("COMPLIANT" if self.ok else "NON-COMPLIANT"))
        return "\n".join(lines)


def check_podium(massing: PodiumMassing,
                 envelope: ZoningEnvelope,
                 tower_gap: Optional[float] = None,
                 daylight: DaylightRule = DAYLIGHT,
                 plate: PlateRule = PLATE) -> PodiumReport:
    """Full rule set for a podium+towers massing.

    TAKS sees the podium footprint. KAKS sees total above-ground GFA.
    Hmaks sees podium + tallest tower. PlateRule sees every tower
    (podium is exempt: commercial plates may run deep). If tower_gap
    is given and there are 2+ towers, the daylight spacing rule runs
    between the two tallest towers, with tower height measured from
    the podium roof (the shading a facing unit actually sees).
    """
    checks = [
        Check("TAKS", massing.podium_footprint, envelope.max_footprint,
              massing.podium_footprint <= envelope.max_footprint + TOLERANCE),
        Check("KAKS", massing.gfa, envelope.max_gfa,
              massing.gfa <= envelope.max_gfa + TOLERANCE),
        Check("Hmaks", massing.height, envelope.hmaks,
              massing.height <= envelope.hmaks + TOLERANCE, unit="m"),
    ]
    for i, t in enumerate(massing.towers):
        c = plate.check(t.length, t.width)
        checks.append(Check("Plate-T{}".format(i + 1), c.value, c.limit,
                            c.ok, unit="m"))
    spacing = None
    if tower_gap is not None and len(massing.towers) >= 2:
        pair = sorted(massing.towers, key=lambda t: -t.height)[:2]
        total_floors = [massing.podium_floors + t.floors for t in pair]
        a = Massing(pair[0].footprint, total_floors[0], pair[0].floor_height,
                    label=(massing.label or "podium") + " T1")
        b = Massing(pair[1].footprint, total_floors[1], pair[1].floor_height,
                    label=(massing.label or "podium") + " T2")
        # shading height override: what a facing unit sees is the tower
        # above the shared podium roof, so spacing uses tower height,
        # while the LEGAL side distance grows with total floor count.
        legal = daylight.legal_spacing(total_floors[0], total_floors[1])
        shading = max(t.height for t in pair)
        intent = daylight.intent_spacing(shading)
        aspiration = daylight.aspiration_spacing(shading)
        sp_checks = [
            Check("Spacing-legal", tower_gap, legal,
                  tower_gap + TOLERANCE >= legal, unit="m", relation=">="),
            Check("Spacing-intent", tower_gap, intent,
                  tower_gap + TOLERANCE >= intent, unit="m", relation=">="),
        ]
        asp = Check("Spacing-aspir.", tower_gap, aspiration,
                    tower_gap + TOLERANCE >= aspiration, unit="m", relation=">=")
        spacing = SpacingReport(massing_a=a, massing_b=b, available=tower_gap,
                                rule=daylight, checks=sp_checks, aspiration=asp)
    return PodiumReport(massing=massing, envelope=envelope,
                        checks=checks, spacing=spacing)


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
