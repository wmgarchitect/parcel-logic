# -*- coding: utf-8 -*-
"""typologies.py — a vocabulary of massing arrangements.

STATUS: EXPERIMENTAL / V02 preview. Not part of the shipped V01 result
(the 126-candidate grid explorer). Five arrangement families generate
and self-judge, but the parametric footprints still need an in-polygon
fit pass and the `terraced` family overshoots KAKS. Kept public for
transparency; V02 finishes and folds it into the explorer.

A vocabulary of massing arrangements (polish phase).

Session 6-10 gave the rules a design SPACE that was only three shapes:
one slab, twin slabs, podium+two-towers. A real feasibility study speaks
a LANGUAGE of arrangements. This module is that language: five families,
each a function that lays blocks out IN PLAN and declares the facing
pairs it creates, so the same daylight rule judges any of them.

The honest split, unchanged from the rest of the lab:
  - a typology returns Blocks (parametric rectangles) + the FacingPairs
    it deliberately creates, with the gap each pair opens. The gap is a
    design decision the typology makes, not a number to rediscover.
  - judge_scheme() runs the full rule set over N blocks and N pairs.
  - the Grasshopper viewer does real in-polygon placement and measures
    the drawn gaps; these parametric gaps rank candidates before Rhino.

Working frame: the setback zone's rectangle-equivalent, long axis = X,
centered at the origin (the viewer remaps to the real polygon).
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from zoning import (DAYLIGHT, PLATE, SITE, Check, DaylightRule, PlateRule,
                    YIELD, YieldModel, ZoningEnvelope, TOLERANCE)
from variants import SITE_ZONE, SetbackZone

__version__ = "0.1.0"
__all__ = [
    "Block", "FacingPair", "Scheme", "SchemeReport", "judge_scheme",
    "point_towers", "perimeter_courtyard", "staggered_bars",
    "terraced", "hybrid_bar_tower",
    "generate_all", "schemes_to_csv",
]

RES = "residential"
COM = "commercial"


# ---------------------------------------------------------------------------
# The building blocks of any arrangement
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Block:
    """One rectangular volume in plan. cx,cy = center; length along the
    block's own long axis, rotated rot_deg from the zone X axis; z0 =
    base height (0 at grade, podium_height for a tower on a plinth)."""

    label: str
    cx: float
    cy: float
    length: float
    width: float
    rot_deg: float
    floors: int
    floor_height: float
    program: str = RES
    z0: float = 0.0

    @property
    def footprint(self) -> float:
        return self.length * self.width

    @property
    def height(self) -> float:
        return self.floors * self.floor_height

    @property
    def top(self) -> float:
        return self.z0 + self.height

    @property
    def gfa(self) -> float:
        return self.footprint * self.floors

    @property
    def depth(self) -> float:
        """Plate depth = the shorter plan dimension (what daylight cares
        about for residential)."""
        return min(self.length, self.width)

    @property
    def at_grade(self) -> bool:
        return abs(self.z0) < 1e-6


@dataclass(frozen=True)
class FacingPair:
    """Two blocks whose facades face each other across a gap the typology
    opened. shading_height is what a unit at the base of the shorter one
    actually sees rising in front of it (measured from the shaded base)."""

    a: str
    b: str
    gap: float
    shading_height: float


# ---------------------------------------------------------------------------
# A named arrangement
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Scheme:
    name: str
    typology: str
    blocks: Tuple[Block, ...]
    pairs: Tuple[FacingPair, ...] = ()
    params: dict = field(default_factory=dict)

    @property
    def ground_footprint(self) -> float:
        """TAKS sees only what touches grade."""
        return sum(b.footprint for b in self.blocks if b.at_grade)

    @property
    def gfa(self) -> float:
        return sum(b.gfa for b in self.blocks)

    @property
    def height(self) -> float:
        return max((b.top for b in self.blocks), default=0.0)

    def coverage(self, env: ZoningEnvelope) -> float:
        return self.ground_footprint / env.parcel_area

    def far(self, env: ZoningEnvelope) -> float:
        return self.gfa / env.parcel_area


@dataclass(frozen=True)
class SchemeReport:
    scheme: Scheme
    envelope: ZoningEnvelope
    checks: List[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def __str__(self) -> str:
        s = self.scheme
        head = "{}  [{}]  {} blocks -> GFA {:,.0f} m2, H {:.1f} m, cov {:.0%}".format(
            s.name, s.typology, len(s.blocks), s.gfa, s.height, s.coverage(self.envelope))
        lines = [head] + ["  " + str(c) for c in self.checks]
        lines.append("  => " + ("COMPLIANT" if self.ok else "NON-COMPLIANT"))
        return "\n".join(lines)


def judge_scheme(scheme: Scheme, env: ZoningEnvelope = SITE,
                 daylight: DaylightRule = DAYLIGHT,
                 plate: PlateRule = PLATE) -> SchemeReport:
    """Full rule set over an arbitrary arrangement:
    TAKS on grade footprint, KAKS on total GFA, Hmaks on the tallest top,
    the plate rule on every residential block, and the daylight rule on
    every facing pair the typology declared (legal + intent)."""
    checks = [
        Check("TAKS", scheme.ground_footprint, env.max_footprint,
              scheme.ground_footprint <= env.max_footprint + TOLERANCE),
        Check("KAKS", scheme.gfa, env.max_gfa,
              scheme.gfa <= env.max_gfa + TOLERANCE),
        Check("Hmaks", scheme.height, env.hmaks,
              scheme.height <= env.hmaks + TOLERANCE, unit="m"),
    ]
    for b in scheme.blocks:
        if b.program == RES:
            pc = plate.check(b.length, b.width)
            checks.append(Check("Plate:" + b.label, pc.value, pc.limit, pc.ok, unit="m"))
    for pr in scheme.pairs:
        legal = daylight.side_min * 2 + daylight.side_per_floor * 0  # placeholder, refined below
        # legal spacing uses the two blocks' floor counts
        ba = next(b for b in scheme.blocks if b.label == pr.a)
        bb = next(b for b in scheme.blocks if b.label == pr.b)
        legal = daylight.legal_spacing(ba.floors, bb.floors)
        intent = daylight.intent_spacing(pr.shading_height)
        checks.append(Check("Gap-legal:{}|{}".format(pr.a, pr.b), pr.gap, legal,
                            pr.gap + TOLERANCE >= legal, unit="m", relation=">="))
        checks.append(Check("Gap-intent:{}|{}".format(pr.a, pr.b), pr.gap, intent,
                            pr.gap + TOLERANCE >= intent, unit="m", relation=">="))
    return SchemeReport(scheme=scheme, envelope=env, checks=checks)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _solve_floors(gfa_budget: float, footprint: float, fh: float,
                  height_budget: float, max_floors_cap: Optional[int] = None) -> int:
    """Most floors that fit both the remaining GFA and the height left."""
    by_gfa = int(gfa_budget // footprint) if footprint > 0 else 0
    by_h = int(height_budget // fh)
    f = min(by_gfa, by_h)
    if max_floors_cap is not None:
        f = min(f, max_floors_cap)
    return max(f, 0)


# ---------------------------------------------------------------------------
# 1 — POINT TOWERS on a podium
# ---------------------------------------------------------------------------

def point_towers(env: ZoningEnvelope = SITE, zone: SetbackZone = SITE_ZONE,
                 n: int = 2, podium_floors: int = 2, podium_cov: float = 0.40,
                 tower_len: float = 28.0, tower_fh: float = 2.8) -> Scheme:
    """N slender towers evenly spaced along the zone's long axis, on a
    shared commercial podium. The built C+D scheme, generalized to N."""
    L = zone.length
    tw = PLATE.max_depth
    podium_fp = podium_cov * env.parcel_area
    podium_gfa = podium_fp * podium_floors
    podium_h = podium_floors * 4.5
    plate_area = tower_len * tw
    remaining = env.max_gfa - podium_gfa
    per_tower_budget = remaining / n if n else 0
    floors = _solve_floors(per_tower_budget, plate_area, tower_fh,
                           env.hmaks - podium_h)
    # podium block sized to the BUDGETED footprint (honest TAKS/GFA)
    podium_len = min(L * 0.9, podium_fp / (zone.width * 0.5))
    podium_wid = podium_fp / podium_len
    blocks = [Block("podium", 0, 0, podium_len, podium_wid, 0,
                    podium_floors, 4.5, COM, 0.0)]
    # positions along X, centered
    span = L * 0.72
    xs = [(-span / 2 + span * k / (n - 1)) if n > 1 else 0.0 for k in range(n)]
    for k, x in enumerate(xs):
        blocks.append(Block("T%d" % (k + 1), x, 0, tower_len, tw, 0,
                            floors, tower_fh, RES, podium_h))
    pairs = []
    for k in range(n - 1):
        gap = (xs[k + 1] - xs[k]) - tower_len
        h = floors * tower_fh
        pairs.append(FacingPair("T%d" % (k + 1), "T%d" % (k + 2), gap, h))
    return Scheme("towers-x%d-p%d" % (n, podium_floors), "point-towers",
                  tuple(blocks), tuple(pairs),
                  {"n": n, "podium_floors": podium_floors, "tower_floors": floors})


# ---------------------------------------------------------------------------
# 2 — PERIMETER BLOCK with courtyard
# ---------------------------------------------------------------------------

def perimeter_courtyard(env: ZoningEnvelope = SITE, zone: SetbackZone = SITE_ZONE,
                        depth: float = 20.0, fh: float = 3.0) -> Scheme:
    """A ring building of `depth` around the zone perimeter, open court
    in the middle. Modeled as four bars; the two long inner faces form
    the daylight-critical pair across the courtyard."""
    L, W = zone.length, zone.width
    court_w = W - 2 * depth
    court_l = L - 2 * depth
    if court_w <= 0 or court_l <= 0:
        # too deep to leave a court; degenerate to a solid slab block
        ring_fp = L * W
    else:
        ring_fp = L * W - court_l * court_w
    floors = _solve_floors(env.max_gfa, ring_fp, fh, env.hmaks)
    # four bars (approx footprints; ring_fp is the true ground area)
    off = (W - depth) / 2.0
    offx = (L - depth) / 2.0
    blocks = [
        Block("N", 0, off, L, depth, 0, floors, fh, RES),
        Block("S", 0, -off, L, depth, 0, floors, fh, RES),
        Block("E", offx, 0, depth, max(W - 2 * depth, 1), 90, floors, fh, RES),
        Block("W", -offx, 0, depth, max(W - 2 * depth, 1), 90, floors, fh, RES),
    ]
    pairs = ()
    if court_w > 0:
        h = floors * fh
        pairs = (FacingPair("N", "S", court_w, h),)
    sc = Scheme("courtyard-d%d-f%d" % (int(depth), floors), "perimeter-courtyard",
                tuple(blocks), pairs,
                {"depth": depth, "floors": floors, "court_w": round(court_w, 1)})
    # override ground footprint via a single synthetic ring block would be
    # cleaner; here TAKS uses sum of bars which double-counts corners, so
    # we correct by a dedicated field:
    object.__setattr__(sc, "params", dict(sc.params, ring_footprint=round(ring_fp, 1)))
    return sc


# ---------------------------------------------------------------------------
# 3 — STAGGERED BARS
# ---------------------------------------------------------------------------

def staggered_bars(env: ZoningEnvelope = SITE, zone: SetbackZone = SITE_ZONE,
                   n: int = 3, depth: float = 18.0, fh: float = 3.0,
                   shift: float = 12.0) -> Scheme:
    """N parallel bars across the zone, spaced along the long axis, each
    shifted in Y so no bar sits directly behind its neighbor — the
    daylight fix the plain twins failed. Gap between adjacent bars is the
    facing pair; the shift means the shading is partial, credited as a
    reduced effective height."""
    L, W = zone.length, zone.width
    bar_len = W * 0.82
    total_depth = n * depth
    free = L - total_depth
    gap = free / (n + 1) if n else 0
    floors = _solve_floors(env.max_gfa, n * bar_len * depth, fh, env.hmaks)
    blocks, xs = [], []
    x = -L / 2 + gap + depth / 2
    for k in range(n):
        y = shift / 2.0 if k % 2 else -shift / 2.0
        blocks.append(Block("B%d" % (k + 1), x, y, depth, bar_len, 0,
                            floors, fh, RES))
        xs.append(x)
        x += depth + gap
    pairs = []
    h = floors * fh
    # stagger credit: the offset reduces the facing overlap, so effective
    # shading height scales by the un-shifted fraction (honest, simple).
    eff = h * max(0.0, 1.0 - (shift / bar_len))
    for k in range(n - 1):
        pairs.append(FacingPair("B%d" % (k + 1), "B%d" % (k + 2), gap, eff))
    return Scheme("staggered-x%d-d%d" % (n, int(depth)), "staggered-bars",
                  tuple(blocks), tuple(pairs),
                  {"n": n, "depth": depth, "floors": floors,
                   "gap": round(gap, 1), "shift": shift})


# ---------------------------------------------------------------------------
# 4 — TERRACED / STEPPED
# ---------------------------------------------------------------------------

def terraced(env: ZoningEnvelope = SITE, zone: SetbackZone = SITE_ZONE,
             base_cov: float = 0.40, steps: int = 4, fh: float = 3.0,
             step_ratio: float = 0.78) -> Scheme:
    """A single mass that steps back as it rises: `steps` tiers, each a
    fraction of the one below. No facing pair on-parcel (one mass), so
    its daylight story is the street stepback, not tower spacing — the
    'sunlight to the street' move. Judged on TAKS/KAKS/Hmaks/plate."""
    base_fp = base_cov * env.parcel_area
    # tier footprints shrink; distribute floors so total GFA nears KAKS
    tier_fps = [base_fp * (step_ratio ** k) for k in range(steps)]
    # floors per tier: even split of height budget, then trim to KAKS
    fl_per = max(1, int((env.hmaks / fh) / steps))
    blocks = []
    z = 0.0
    gfa = 0.0
    aspect_w = min(math.sqrt(base_fp), PLATE.max_depth * 1.6)
    for k, fp in enumerate(tier_fps):
        if gfa + fp * fl_per > env.max_gfa:
            fl_per = max(1, int((env.max_gfa - gfa) / fp))
        w = min(math.sqrt(fp), PLATE.max_depth)
        l = fp / w
        blocks.append(Block("tier%d" % (k + 1), 0, 0, l, w, 0, fl_per, fh, RES, z))
        z += fl_per * fh
        gfa += fp * fl_per
        if gfa >= env.max_gfa:
            break
    return Scheme("terraced-s%d-c%02d" % (steps, int(base_cov * 100)), "terraced",
                  tuple(blocks), (),
                  {"steps": len(blocks), "base_cov": base_cov})


# ---------------------------------------------------------------------------
# 5 — HYBRID: long low bar + one tower
# ---------------------------------------------------------------------------

def hybrid_bar_tower(env: ZoningEnvelope = SITE, zone: SetbackZone = SITE_ZONE,
                     bar_floors: int = 3, bar_cov: float = 0.42,
                     tower_len: float = 28.0, tower_fh: float = 2.8) -> Scheme:
    """A long low bar (commercial + low residential) with one slender
    tower rising off one end — height where the site allows it, mass
    where it doesn't. One tower means no on-parcel facing pair: a
    daylight-easy, yield-focused scheme, honestly labeled as such."""
    L = zone.length
    bar_fp = bar_cov * env.parcel_area
    bar_depth = min(bar_fp / (L * 0.88), PLATE.max_depth)
    bar_len = bar_fp / bar_depth
    bar_h = bar_floors * 4.0
    tw = PLATE.max_depth
    plate_area = tower_len * tw
    remaining = env.max_gfa - bar_fp * bar_floors
    tfloors = _solve_floors(remaining, plate_area, tower_fh, env.hmaks - bar_h)
    blocks = [
        Block("bar", 0, 0, bar_len, bar_depth, 0, bar_floors, 4.0, COM, 0.0),
        Block("tower", -bar_len / 2 + tower_len / 2, 0, tower_len, tw, 0,
              tfloors, tower_fh, RES, bar_h),
    ]
    return Scheme("hybrid-b%d-t%d" % (bar_floors, tfloors), "hybrid-bar-tower",
                  tuple(blocks), (),
                  {"bar_floors": bar_floors, "tower_floors": tfloors})


# ---------------------------------------------------------------------------
# the whole vocabulary
# ---------------------------------------------------------------------------

def generate_all(env: ZoningEnvelope = SITE) -> List[Scheme]:
    out: List[Scheme] = []
    for n in (2, 3, 4):
        for pf in (2, 3):
            out.append(point_towers(env, n=n, podium_floors=pf))
    for d in (16, 20, 22):
        out.append(perimeter_courtyard(env, depth=d))
    for n in (2, 3):
        for sh in (8.0, 16.0):
            out.append(staggered_bars(env, n=n, shift=sh))
    for c in (0.35, 0.45):
        for s in (3, 4):
            out.append(terraced(env, base_cov=c, steps=s))
    for bf in (2, 3):
        out.append(hybrid_bar_tower(env, bar_floors=bf))
    return out


def schemes_to_csv(schemes: Sequence[Scheme], path: Optional[str] = None) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["name", "typology", "blocks", "ground_fp_m2", "gfa_m2",
                "sellable_est_m2", "height_m", "coverage", "compliant"])
    for s in schemes:
        r = judge_scheme(s)
        w.writerow([s.name, s.typology, len(s.blocks),
                    "{:.0f}".format(s.ground_footprint), "{:.0f}".format(s.gfa),
                    "{:.0f}".format(YIELD.sellable(s.gfa)),
                    "{:.1f}".format(s.height), "{:.3f}".format(s.coverage(SITE)),
                    r.ok])
    text = buf.getvalue()
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


def _demo() -> None:  # pragma: no cover
    schemes = generate_all()
    print("vocabulary: %d schemes across 5 typologies" % len(schemes))
    ok = [s for s in schemes if judge_scheme(s).ok]
    print("compliant: %d" % len(ok))
    print()
    for s in schemes:
        r = judge_scheme(s)
        print("%-22s %-18s GFA %7.0f  H %5.1f  %s" % (
            s.name, s.typology, s.gfa, s.height,
            "OK" if r.ok else "no"))


if __name__ == "__main__":
    _demo()
