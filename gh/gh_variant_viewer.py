"""V01_SiteBrief.gh — VariantViewer component (Python 3), Session 6.

Displays any candidate from the variants.py grid as live geometry:
one or two block masses placed in the setback zone, plus the full
rule report for that candidate.

Component (Python 3 Script) setup:
    inputs :  idx      (Item, int hint ok)   <- integer slider 0-71
              zone_crv (Item, Curve hint)    <- SetbackOffset output C
    outputs:  geo      (block masses, previewable)
              report   (text -> panel)

Twin blocks are placed at the ends of the zone's long axis. The gap
drawn here is measured on the real polygon's bounding box; the CSV's
gap is the rectangle-equivalent estimate. Both are reported.
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

rows = variants.generate_grid()
i = max(0, min(int(idx), len(rows) - 1))
r = rows[i]
m = r.massing

bb = zone_crv.GetBoundingBox(True)
cx = (bb.Min.X + bb.Max.X) / 2.0
cy = (bb.Min.Y + bb.Max.Y) / 2.0
ext_x = bb.Max.X - bb.Min.X
ext_y = bb.Max.Y - bb.Min.Y
along_x = ext_x >= ext_y
long_ext = ext_x if along_x else ext_y


def box_at(px, py, side, height):
    plane = rg.Plane(rg.Point3d(px, py, 0.0),
                     rg.Vector3d.XAxis, rg.Vector3d.YAxis)
    iv = rg.Interval(-side / 2.0, side / 2.0)
    return rg.Box(plane, iv, iv, rg.Interval(0.0, height))


geo = []
gap_drawn = None
if r.blocks == 1:
    side = math.sqrt(m.footprint)
    geo.append(box_at(cx, cy, side, m.height))
else:
    side = math.sqrt(m.footprint / 2.0)
    shift = long_ext / 2.0 - side / 2.0
    dx, dy = (shift, 0.0) if along_x else (0.0, shift)
    geo.append(box_at(cx - dx, cy - dy, side, m.height))
    geo.append(box_at(cx + dx, cy + dy, side, m.height))
    gap_drawn = long_ext - 2.0 * side

lines = [r.label, str(r.zoning)]
if r.spacing is not None:
    lines.append(str(r.spacing))
    lines.append("  gap drawn (bbox): {:.1f} m / estimated: {:.1f} m".format(
        gap_drawn, r.gap_available))
lines.append("  => " + ("PROTECTS DAYLIGHT" if r.ok_intent
                        else ("LEGAL ONLY" if r.ok_legal else "NOT LEGAL")))
report = "\n".join(lines)
