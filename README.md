# parcel-logic

**Turkish zoning rules as executable code, tested against a real Istanbul parcel.**

Part of [Parcel Logic](https://archicoder.com), a constraint-to-form lab for computational massing.

![Coverage slider sweeping fat-slab to slim-tower with live compliance](docs/coverage-sweep.gif)

## The idea

Three numbers govern what can be built on a Turkish parcel:

| Rule | Meaning | This site |
|---|---|---|
| **KAKS** (emsal / FAR) | total floor area ceiling, as a multiple of parcel area | 4.00 |
| **TAKS** | footprint ceiling, as a fraction of parcel area | 0.50 |
| **Hmaks** | maximum building height | 80 m |

On the study parcel — **Merdivenköy 3412/3, Kadıköy, Istanbul, 7,813.31 m²** — those numbers allow **31,253 m² of legal floor area**. What they *don't* do is choose the building. An 8-floor fat slab, a 20-floor slim tower, and 25-floor twin towers are all equally legal:

```
A - fat slab:     3,907 m2 x  8 fl @ 4.0 m -> GFA 31,253 m2, H 32.0 m  => COMPLIANT
B - slim tower:   1,563 m2 x 20 fl @ 4.0 m -> GFA 31,253 m2, H 80.0 m  => COMPLIANT
C - twin towers:  1,250 m2 x 25 fl @ 3.2 m -> GFA 31,250 m2, H 80.0 m  => COMPLIANT
```

Option C matches what was actually built on this parcel (Transform Fikirtepe, blocks C+D). The rules wanted a tower — but they'd have accepted anything. What chooses is intent. This module makes that spectrum computable: encode the rules once, then let any massing report its own compliance.

```python
from zoning import SITE, Massing, check

report = check(Massing(footprint=1250, floors=25, floor_height=3.2), SITE)
print(report.ok)     # True
print(report)        # per-rule PASS/FAIL with real numbers
```

## What's here

- **`zoning.py`** — the module. `ZoningEnvelope` (parcel + rules), `Massing` (a candidate building), `check()` (TAKS/KAKS/Hmaks compliance), `massing_from_coverage()` and `sweep_coverage()` (the fat-slab ↔ slim-tower spectrum), `variants_to_csv()` (metrics export). Pure Python 3, standard library only.
- **`test_zoning.py`** — 16 tests pinned to the verified site numbers (appraisal report + official plan documents) and the built reality.

Run the demo and the tests:

```
python3 zoning.py
python3 test_zoning.py
```

## Grasshopper

The same module runs unchanged inside a Grasshopper Python 3 component. In the lab's `V01_SiteBrief.gh`, Rhino holds the cadastral fact (the parcel boundary pulled live from the TKGM parcel API), Grasshopper holds the rules, and sliders sweep coverage ratio and floor height with compliance checks updating live. Two independent methods — direct Rhino modeling and the GH rebuild — agree on every derived number.

## Provenance (why these numbers are trustworthy)

- Parcel area from the tapu (deed): 7,813.31 m².
- KAKS 4.00 / TAKS 0.50 / Hmaks 80 m from the 26.12.2017 1/1000 Fikirtepe plan — the build-era rules the existing towers were approved under. (The in-force 2023 reserve-area plan changed the regime; the lab carries that as narrative context and models the clean per-parcel 2017 basis.)
- Boundary geometry from the TKGM cadastral API, measured at 7,822.74 m² — 0.12% from the deed, explained by coordinate precision.

Every session behind this repo is logged and published at [archicoder.com](https://archicoder.com).

## License

MIT — see [LICENSE](LICENSE).
