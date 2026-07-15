"""V01_SiteBrief.gh — VariantViewer component (Python 3), Session 6/8.

Displays any candidate from the variants.py grid as live geometry,
placed INSIDE the real setback polygon, with the full rule report.

Component (Python 3 Script) setup:
    inputs :  idx      (Item, int hint ok)   <- integer slider 0-71
              zone_crv (Item, Curve hint)    <- SetbackOffset output C
    outputs:  geo      (block masses, previewable)
              report   (text -> panel)

v3 (Session 8, pulled forward): rectangular blocks + no fallback.
    v2 tested square blocks against the real curve (correct) but kept a
    bounding-box fallback for anything that didn't fit centered — and a
    square is the wrong shape for this zone: a 3,900 m2 square is 62 m
    wide, the zone is ~53 m wide, so every big single-block variant hit
    the fallback and leaked outside the boundary.
    v3 places RECTANGLES, oriented to the zone's longest edge:
    - width found by search: start square, elongate along the axis
      until the rectangle fits (aspect capped at 4:1),
    - twins march outward along the axis to the real extreme positions,
    - the fallback is deleted. If nothing fits, the variant reports
      DOES NOT FIT ZONE and draws nothing. That is a verdict, not a bug.

    (v1 history: Curve.Offset erosion produced a disjoint fragment and
    ~6 m false gaps on this six-sided zone; direct containment testing
    replaced it. v2 history: square-only + bbox fallback, leaked.)
"""

import sys
import math

REPO = r"D:\GDrive\02_Businesses\ARC_Archicoder\10-Lab\parcel-logic"
if REPO not in sys.path:
    sys.path.append(REPO)

import importlib
import zoning
import variants
importlib.reload(zoning)
importlib.reload(variants)

import Rhino.Geometry as rg
import scriptcontext as sc

rows = variants.generate_grid()
i = max(0, min(int(idx), len(rows) - 1))
r = rows[i]
m = r.massing

TOL = sc.doc.ModelAbsoluteTolerance
WORLD_XY = rg.Plane.WorldXY
ASPECT_CAP = 4.0          # max length:width of a block
WIDTH_STEPS = 40          # search resolution for block width
MARCH_STEP = 0.25         # m, outward march for twin placement

# ---------------------------------------------------------------------------
# zone frame: origin at area centroid, X along the longest edge
# ---------------------------------------------------------------------------

amp = rg.AreaMassProperties.Compute(zone_crv)
centroid = amp.Centroid

ok, pline = zone_crv.TryGetPolyline()
if not ok:
    raise ValueError("zone_crv is not a polyline curve")
best_len, axis = -1.0, rg.Vector3d.XAxis
for seg_i in range(pline.SegmentCount):
    seg = pline.SegmentAt(seg_i)
    if seg.Length > best_len:
        best_len = seg.Length
        axis = seg.Direction
axis.Unitize()
perp = rg.Vector3d.CrossProduct(rg.Vector3d.ZAxis, axis)
perp.Unitize()


def inside(pt):
    return zone_crv.Contains(pt, WORLD_XY, TOL) == rg.PointContainment.Inside


def rect_fits(center, half_l, half_w):
    """All four corners AND edge midpoints of the rectangle inside."""
    pts = []
    for a in (-half_l, 0.0, half_l):
        for b in (-half_w, 0.0, half_w):
            if a == 0.0 and b == 0.0:
                continue
            pts.append(rg.Point3d(center + axis * a + perp * b))
    return all(inside(p) for p in pts)


def fit_rect(center, area):
    """Widest (most square) L x W rectangle of `area` that fits at
    `center`, elongating along the zone axis up to ASPECT_CAP.
    Returns (L, W) or None."""
    w_max = math.sqrt(area)                      # square
    w_min = math.sqrt(area / ASPECT_CAP)         # 4:1 slab
    for k in range(WIDTH_STEPS + 1):
        w = w_max - (w_max - w_min) * k / WIDTH_STEPS
        l = area / w
        if rect_fits(center, l / 2.0, w / 2.0):
            return (l, w)
    return None


def march_out(area, l, w, sign):
    """Furthest center along sign*axis from the centroid where the
    L x W rectangle still fits. Returns the center point."""
    t, last_good = 0.0, rg.Point3d(centroid)
    limit = best_len  # can't march further than the longest edge
    while t < limit:
        t += MARCH_STEP
        c = rg.Point3d(centroid + axis * (sign * t))
        if rect_fits(c, l / 2.0, w / 2.0):
            last_good = c
        else:
            break
    return last_good


def block_box(center, l, w, height):
    plane = rg.Plane(center, axis, perp)
    return rg.Box(plane,
                  rg.Interval(-l / 2.0, l / 2.0),
                  rg.Interval(-w / 2.0, w / 2.0),
                  rg.Interval(0.0, height))


# ---------------------------------------------------------------------------
# placement — no fallback: fits, or reports that it doesn't
# ---------------------------------------------------------------------------

geo = []
gap_drawn = None
fits_zone = False
placement_note = ""

if r.blocks == 1:
    dims = fit_rect(rg.Point3d(centroid), m.footprint)
    if dims:
        l, w = dims
        geo.append(block_box(rg.Point3d(centroid), l, w, m.height))
        fits_zone = True
        placement_note = "single block {:.0f} x {:.0f} m, in-polygon, zone axis".format(l, w)
    else:
        placement_note = "DOES NOT FIT ZONE (no rectangle up to 4:1 holds {:,.0f} m2)".format(m.footprint)
else:
    block_area = m.footprint / 2.0
    dims = fit_rect(rg.Point3d(centroid), block_area)
    if dims:
        l, w = dims
        p_pos = march_out(block_area, l, w, +1.0)
        p_neg = march_out(block_area, l, w, -1.0)
        gap_drawn = p_pos.DistanceTo(p_neg) - l
        if gap_drawn > 0.0:
            geo.append(block_box(p_pos, l, w, m.height))
            geo.append(block_box(p_neg, l, w, m.height))
            fits_zone = True
            placement_note = "twin blocks {:.0f} x {:.0f} m each, in-polygon, real gap".format(l, w)
        else:
            placement_note = ("DOES NOT FIT ZONE as twins (two {:.0f} x {:.0f} m blocks "
                              "overlap by {:.1f} m)".format(l, w, -gap_drawn))
            gap_drawn = None
    else:
        placement_note = "DOES NOT FIT ZONE (no twin rectangles up to 4:1 hold {:,.0f} m2 each)".format(block_area)

# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

lines = [r.label, str(r.zoning)]
if r.spacing is not None and gap_drawn is not None:
    real_spacing = zoning.check_spacing(
        zoning.Massing(m.footprint / 2.0, m.floors, m.floor_height, label=r.label + " block"),
        zoning.Massing(m.footprint / 2.0, m.floors, m.floor_height, label=r.label + " block"),
        available=max(gap_drawn, 0.0))
    lines.append(str(real_spacing))
    lines.append("  gap: {:.1f} m real (drawn) / {:.1f} m CSV estimate".format(
        gap_drawn, r.gap_available))
elif r.spacing is not None:
    lines.append(str(r.spacing))
lines.append("  placement: " + placement_note)

if not fits_zone:
    verdict = "DOES NOT FIT ZONE"
elif r.blocks == 2 and gap_drawn is not None:
    # legality and intent both judged on the REAL drawn gap
    by_rule = {c.rule: c.ok for c in real_spacing.checks}
    legal_real = r.zoning.ok and by_rule["Spacing-legal"]
    intent_real = legal_real and by_rule["Spacing-intent"]
    verdict = ("PROTECTS DAYLIGHT (real gap)" if intent_real
               else ("LEGAL ONLY (real gap)" if legal_real else "NOT LEGAL"))
else:
    verdict = ("PROTECTS DAYLIGHT" if r.ok_intent
               else ("LEGAL ONLY" if r.ok_legal else "NOT LEGAL"))
lines.append("  => " + verdict)
report = "\n".join(lines)
