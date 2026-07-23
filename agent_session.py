# -*- coding: utf-8 -*-
"""agent_session.py — the recorded agent run for Video 2.

Run once per scene on camera:  python agent_session.py 1   (proposal 1)
                               python agent_session.py all (whole run)

Each proposal prints its architectural REASONING, then the rules' verdict.
The proposals and results are the real ones from the Jul 18 dry run; this
file just makes them reproducible one command at a time, so the recording
is clean. Rules judge; nobody checks by hand.
"""

import sys
from zoning import (SITE, Tower, PodiumMassing, Massing, check,
                    check_podium, check_spacing, YIELD)


def line():
    print("=" * 68)


def p1():
    line(); print("PROPOSAL 1 - break the symmetry")
    print("Put all the height in one slender tower, lay the rest down as a bar.")
    towers = (Tower(26.0, 22.0, 22, 2.8), Tower(50.0, 22.0, 6, 2.8))
    pm = PodiumMassing(3125.32, 2, 4.5, towers, label="AGENT-1")
    print(check_podium(pm, SITE, tower_gap=87.0 - 76.0))


def p2():
    line(); print("PROPOSAL 2 - adapt: shorten the tower, stretch the bar")
    towers = (Tower(24.0, 22.0, 18, 2.8), Tower(46.0, 22.0, 8, 2.8))
    pm = PodiumMassing(3125.32, 2, 4.5, towers, label="AGENT-2")
    print(check_podium(pm, SITE, tower_gap=87.0 - 70.0))


def p3():
    line(); print("PROPOSAL 3 - three short towers, shorter shadows")
    towers = (Tower(24.0, 22.0, 12, 2.8),) * 3
    pm = PodiumMassing(3125.32, 2, 4.5, towers, label="AGENT-3")
    print(check_podium(pm, SITE, tower_gap=(87.0 - 72.0) / 2.0))


def p4():
    line(); print("PROPOSAL 4 - no podium, two low bars (legal building, illegal pair)")
    r = check(Massing(2 * 46.0 * 22.0, 10, 2.8, label="AGENT-4"), SITE)
    a = Massing(46.0 * 22.0, 10, 2.8, label="barA")
    b = Massing(46.0 * 22.0, 10, 2.8, label="barB")
    print(r); print(check_spacing(a, b, available=97.0 - 92.0))


def p5():
    line(); print("PROPOSAL 5 - the greedy one: take everything")
    towers = (Tower(40.0, 22.0, 15, 3.2), Tower(40.0, 22.0, 15, 3.2))
    pm = PodiumMassing(3906.66, 3, 4.5, towers, label="AGENT-5")
    print(check_podium(pm, SITE, tower_gap=90.0 - 80.0))
    print("  (TAKS fails by 5 mm of rounding - the same bug class from video 1)")


def p6():
    line(); print("PROPOSAL 6 - the lesson: the tallest tower prices the gap")
    towers = (Tower(24.0, 22.0, 14, 2.8), Tower(40.0, 22.0, 12, 2.8))
    pm = PodiumMassing(3125.32, 2, 4.5, towers, label="AGENT-6")
    print(check_podium(pm, SITE, tower_gap=87.0 - 64.0))


def p7():
    line(); print("PROPOSAL 7 - convergence: yield back, daylight kept")
    towers = (Tower(30.0, 22.0, 15, 2.8), Tower(30.0, 22.0, 15, 2.8))
    pm = PodiumMassing(3515.99, 3, 4.5, towers, label="AGENT-7")
    r = check_podium(pm, SITE, tower_gap=89.0 - 60.0)
    print(r)
    print("  ~%d m2 sellable - 97%% of the built towers, at 55 m instead of 80" %
          round(YIELD.sellable(pm.gfa)))


PROPS = {1: p1, 2: p2, 3: p3, 4: p4, 5: p5, 6: p6, 7: p7}

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg == "all":
        for k in sorted(PROPS):
            PROPS[k](); print()
    else:
        PROPS[int(arg)]()
