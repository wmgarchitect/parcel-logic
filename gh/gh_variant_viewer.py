"""V01_SiteBrief.gh — VariantViewer component (Python 3), v5 (Session 10).

One slider walks the ENTIRE design space:
    idx 0-71    flat grid (variants.py): one or two slab blocks
    idx 72-125  podium grid (variants_podium.py): commercial base + twin towers

Placement is in-polygon against the real setback curve, plates are born
buildable (residential width capped at 22 m; podium exempt), gaps are
measured on the drawn geometry and re-judged. No fallback: what cannot
fit says DOES NOT FIT ZONE and draws nothing.

Component setup (unchanged from v3/v4):
    inputs :  idx (int slider 0-125), zone_crv (Curve) <- SetbackOffset C
    outputs:  geo, report
"""

import sys
import math

REPO = r"D:\GDrive\02_Businesses\ARC_Archicoder\10-Lab\parcel-logic"
if REPO not in sys.path:
    sys.path.append(REPO)

import importlib
import zoning
import variants
import variants_podium
importlib.reload(zoning)
importlib.reload(variants)
importlib.reload(variants_podium)

import Rhino.Geometry as rg
import scriptcontext as sc

flat_rows = variants.generate_grid()
pod_rows = variants_podium.generate_podium_grid()
TOTAL = len(flat_rows) + len(pod_rows)

i = max(0, min(int(idx), TOTAL - 1))

TOL = sc.doc.ModelAbsoluteTolerance
WORLD_XY = rg.Plane.WorldXY
WIDTH_STEPS = 40
MARCH_STEP = 0.25

# ---------------- zone frame ----------------
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
    pts = []
    for a in (-half_l, 0.0, half_l):
        for b in (-half_w, 0.0, half_w):
            if a == 0.0 and b == 0.0:
                continue
            pts.append(rg.Point3d(center + axis * a + perp * b))
    return all(inside(p) for p in pts)


def fit_rect(center, area, w_cap=None):
    """Widest L x W rectangle of `area` fitting at `center`. Width starts
    at min(sqrt(area), w_cap) and elongates along the axis to 6:1."""
    w_max = math.sqrt(area)
    if w_cap is not None:
        w_max = min(w_max, w_cap)
    w_min = math.sqrt(area / 6.0)
    if w_min > w_max:
        w_min = w_max / 2.0
    for k in range(WIDTH_STEPS + 1):
        w = w_max - (w_max - w_min) * k / WIDTH_STEPS
        if w <= 0:
            break
        l = area / w
        if rect_fits(center, l / 2.0, w / 2.0):
            return (l, w)
    return None


def march_out(l, w, sign):
    t, last_good = 0.0, rg.Point3d(centroid)
    while t < best_len:
        t += MARCH_STEP
        c = rg.Point3d(centroid + axis * (sign * t))
        if rect_fits(c, l / 2.0, w / 2.0):
            last_good = c
        else:
            break
    return last_good


def block_box(center, l, w, height, z0=0.0):
    plane = rg.Plane(rg.Point3d(center.X, center.Y, z0), axis, perp)
    return rg.Box(plane,
                  rg.Interval(-l / 2.0, l / 2.0),
                  rg.Interval(-w / 2.0, w / 2.0),
                  rg.Interval(0.0, height))


geo = []
lines = []
fits_zone = False

if i < len(flat_rows):
    # ---------------- flat grid (v4 behavior) ----------------
    r = flat_rows[i]
    m = r.massing
    gap_drawn = None
    if r.blocks == 1:
        dims = fit_rect(rg.Point3d(centroid), m.footprint,
                        w_cap=zoning.PLATE.max_depth)
        if dims:
            l, w = dims
            geo.append(block_box(centroid, l, w, m.height))
            fits_zone = True
            placement = "single block {:.0f} x {:.0f} m, in-polygon".format(l, w)
        else:
            placement = "DOES NOT FIT ZONE ({:,.0f} m2 as a <=22 m slab)".format(m.footprint)
    else:
        block_area = m.footprint / 2.0
        dims = fit_rect(rg.Point3d(centroid), block_area,
                        w_cap=zoning.PLATE.max_depth)
        if dims:
            l, w = dims
            p_pos = march_out(l, w, +1.0)
            p_neg = march_out(l, w, -1.0)
            gap_drawn = p_pos.DistanceTo(p_neg) - l
            if gap_drawn > 0.0:
                geo.append(block_box(p_pos, l, w, m.height))
                geo.append(block_box(p_neg, l, w, m.height))
                fits_zone = True
                placement = "twin blocks {:.0f} x {:.0f} m, in-polygon, real gap".format(l, w)
            else:
                placement = "DOES NOT FIT ZONE as twins (overlap {:.1f} m)".format(-gap_drawn)
                gap_drawn = None
        else:
            placement = "DOES NOT FIT ZONE (twin {:,.0f} m2 as <=22 m slabs)".format(block_area)

    lines = [r.label, str(r.zoning)]
    if gap_drawn is not None:
        blk = zoning.Massing(m.footprint / 2.0, m.floors, m.floor_height,
                             label=r.label + " block")
        sp = zoning.check_spacing(blk, blk, available=max(gap_drawn, 0.0))
        lines.append(str(sp))
        lines.append("  gap: {:.1f} m real / {:.1f} m CSV estimate".format(
            gap_drawn, r.gap_available))
        by_rule = {c.rule: c.ok for c in sp.checks}
        legal_real = r.zoning.ok and by_rule["Spacing-legal"]
        intent_real = legal_real and by_rule["Spacing-intent"]
    else:
        legal_real = r.zoning.ok and fits_zone
        intent_real = legal_real and (r.blocks == 1)
    if geo:
        pc = zoning.PLATE.check(l, w)
        lines.append("  Plate-depth   {}  {:.0f} x {:.0f} m".format(
            "PASS" if pc.ok else "FAIL", l, w))
    lines.append("  placement: " + placement)
    if not fits_zone:
        verdict = "DOES NOT FIT ZONE"
    else:
        verdict = ("PROTECTS DAYLIGHT (real gap)" if intent_real
                   else ("LEGAL ONLY (real gap)" if legal_real else "NOT LEGAL"))
    lines.append("  => " + verdict)

else:
    # ---------------- podium grid (new in v5) ----------------
    p = pod_rows[i - len(flat_rows)]
    pm = p.massing
    podium_h = pm.podium_height
    t0 = pm.towers[0]

    dims = fit_rect(rg.Point3d(centroid), pm.podium_footprint, w_cap=None)
    placement = ""
    gap_drawn = None
    if dims:
        pl, pw = dims
        if pw + TOL >= t0.width:
            # podium fits; towers march inside the PODIUM rectangle
            geo.append(block_box(centroid, pl, pw, podium_h))
            t_half = (pl - t0.length) / 2.0
            if t_half > 0:
                c_pos = rg.Point3d(centroid + axis * t_half)
                c_neg = rg.Point3d(centroid - axis * t_half)
                gap_drawn = 2.0 * t_half - t0.length
                if gap_drawn > 0.0:
                    geo.append(block_box(c_pos, t0.length, t0.width,
                                         t0.height, z0=podium_h))
                    geo.append(block_box(c_neg, t0.length, t0.width,
                                         t0.height, z0=podium_h))
                    fits_zone = True
                    placement = ("podium {:.0f} x {:.0f} m + twin towers {:.0f} x {:.0f} m "
                                 "on top, real gap".format(pl, pw, t0.length, t0.width))
                else:
                    geo = []
                    placement = "DOES NOT FIT: towers overlap on this podium ({:.1f} m)".format(-gap_drawn)
                    gap_drawn = None
            else:
                geo = []
                placement = "DOES NOT FIT: podium shorter than one tower plate"
        else:
            geo = []
            placement = "DOES NOT FIT: podium narrower than tower depth"
    else:
        placement = "DOES NOT FIT ZONE (podium {:,.0f} m2)".format(pm.podium_footprint)

    if fits_zone and gap_drawn is not None:
        rep = zoning.check_podium(pm, zoning.SITE, tower_gap=gap_drawn)
    else:
        rep = p.report
    lines = [p.label + "  [PODIUM TYPOLOGY]", str(rep)]
    if gap_drawn is not None:
        lines.append("  gap: {:.1f} m real (on podium) / {:.1f} m axis estimate".format(
            gap_drawn, p.gap_estimate))
    lines.append("  yield: {:,.0f} m2 emsal -> ~{:,.0f} m2 sellable".format(
        pm.gfa, zoning.YIELD.sellable(pm.gfa)))
    lines.append("  placement: " + placement)
    if not fits_zone:
        verdict = "DOES NOT FIT ZONE"
    else:
        base_ok = all(c.ok for c in rep.checks)
        sp_ok = rep.spacing.ok if rep.spacing else True
        legal_ok = base_ok and (all(
            c.ok for c in rep.spacing.checks if c.rule == "Spacing-legal")
            if rep.spacing else True)
        verdict = ("PROTECTS DAYLIGHT (real gap)" if base_ok and sp_ok
                   else ("LEGAL ONLY (real gap)" if legal_ok else "NOT LEGAL"))
    lines.append("  => " + verdict)

report = "\n".join(lines)
