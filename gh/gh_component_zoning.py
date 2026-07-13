"""V01_SiteBrief.gh — ZoningModule component (Python 3), Session 4+.

zoning.py as the single engine of the GH definition. The native math
chain from Session 3 is retired; this component computes the massing
and drives the geometry (Scale factor, extrusion height) directly.

Inputs (Item access):
    parcel_area  : Number param, tapu m2 (7813.31)
    kaks         : Number param (4.00)
    taks         : Number param (0.50)
    hmaks        : Number param (80)
    coverage     : slider (0.05-0.50)
    floor_h      : slider (2.8-4.0)
    setback_area : Area component output A (setback zone m2)

Outputs:
    footprint  : m2 -> panel
    floors     : int -> panel
    height     : m -> Unit Z factor + panel
    gfa        : m2 -> panel
    scale_f    : sqrt(footprint/setback_area) -> Scale.Factor
    compliant  : bool -> panel
    report     : text -> Module report panel
"""

import sys
import math

REPO = r"D:\GDrive\02_Businesses\ARC_Archicoder\10-Lab\parcel-logic"
if REPO not in sys.path:
    sys.path.append(REPO)

import importlib
import zoning
importlib.reload(zoning)  # pick up module edits without restarting Rhino

from zoning import ZoningEnvelope, massing_from_coverage, check

env = ZoningEnvelope(parcel_area=float(parcel_area), kaks=float(kaks),
                     taks=float(taks), hmaks=float(hmaks),
                     name="Merdivenkoy 3412/3")

m = massing_from_coverage(env, float(coverage), float(floor_h),
                          label="V01 coverage {:.2f}".format(float(coverage)))
r = check(m, env)

footprint = m.footprint
floors = m.floors
height = m.height
gfa = m.gfa
scale_f = math.sqrt(m.footprint / float(setback_area))
compliant = r.ok
report = str(r)
