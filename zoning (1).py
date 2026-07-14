"""zoning.py — Turkish zoning rules as pure Python.

Part of Parcel Logic, a constraint-to-form lab for computational massing.
Study parcel: Merdivenkoy 3412/3, Kadikoy, Istanbul (7,813.31 m2).
Build-era rules (26.12.2017 1/1000 plan): KAKS 4.00, TAKS 0.50, Hmaks 80 m.

No Rhino imports on purpose: the same file runs inside a Grasshopper
Python component, in a terminal, or in a test — rules are portable,
geometry is not.

Terms:
    KAKS  (FAR)      — total floor area / parcel area, a cap
    TAKS             — footprint / parcel area, a cap
    Hmaks            — maximum building height, a cap
"""

import math

# Tolerance for comparing areas/heights in m2/m. Computers store decimals
# imperfectly (3906.66 may be 3906.6600000001 internally), so legal caps
# are checked as "<= cap + EPS" instead of a bare "<=".
EPS = 1e-6


def max_footprint(parcel_area, taks):
    """Largest legal footprint in m2 (TAKS cap)."""
    return parcel_area * taks


def max_gfa(parcel_area, kaks):
    """Largest legal gross floor area in m2 (KAKS cap)."""
    return parcel_area * kaks


def floor_count(target_gfa, footprint):
    """Max whole floors whose total area stays within target_gfa.

    KAKS is a cap, so we round DOWN: 25.9 computed floors means the
    26th floor would bust the cap — you get 25.
    """
    return math.floor(target_gfa / footprint)


def building_height(floors, floor_height):
    """Total building height in m."""
    return floors * floor_height


def coverage_ratio(footprint, parcel_area):
    """Actual TAKS used by a design (0-1)."""
    return footprint / parcel_area


def check_compliance(parcel_area, footprint, floors, floor_height,
                     kaks, taks, hmaks):
    """Check one massing design against the three zoning caps.

    Returns a dict: each key is a rule, each value is True (pass)
    or False (fail). Caps are inclusive — using exactly 100% of an
    allowance is legal.
    """
    gfa = footprint * floors
    height = building_height(floors, floor_height)
    return {
        "TAKS (footprint)": footprint <= max_footprint(parcel_area, taks) + EPS,
        "KAKS (floor area)": gfa <= max_gfa(parcel_area, kaks) + EPS,
        "Hmaks (height)": height <= hmaks + EPS,
    }


def summary(parcel_area, footprint, floors, floor_height,
            kaks, taks, hmaks):
    """Full report for one design: metrics + compliance, as a dict."""
    checks = check_compliance(parcel_area, footprint, floors, floor_height,
                              kaks, taks, hmaks)
    return {
        "footprint_m2": footprint,
        "floors": floors,
        "height_m": building_height(floors, floor_height),
        "gfa_m2": footprint * floors,
        "coverage": coverage_ratio(footprint, parcel_area),
        "max_footprint_m2": max_footprint(parcel_area, taks),
        "max_gfa_m2": max_gfa(parcel_area, kaks),
        "compliant": all(checks.values()),
        "checks": checks,
    }


# Self-test: runs only when the file is executed directly
# (python zoning.py), NOT when imported by Grasshopper or another script.
if __name__ == "__main__":
    # Verified facts — Merdivenkoy 3412/3
    PARCEL = 7813.31
    KAKS, TAKS, HMAKS = 4.00, 0.50, 80.0

    print(f"Max footprint: {max_footprint(PARCEL, TAKS):,.2f} m2")
    print(f"Max GFA:       {max_gfa(PARCEL, KAKS):,.2f} m2")
    print()

    # The built reality: Transform Fikirtepe twin-tower scheme
    # (one tower: 1,250 m2 plate, 25 floors @ 3.2 m)
    report = summary(PARCEL, footprint=1250.0, floors=25, floor_height=3.2,
                     kaks=KAKS, taks=TAKS, hmaks=HMAKS)
    print("Twin-tower baseline (one tower):")
    for key, value in report.items():
        print(f"  {key}: {value}")
