#!/usr/bin/env python3
"""Cap how far bots/econ will run a belt trunk to reach new ore.

A builder's real cost is not the 3 Ti a belt costs, it is the turns: walking to
the site and laying one tile per action. Measured head-to-head against the
incumbent, econ and scouter2 built the *same* five harvesters by turn 72 on
midgard -- econ's extra economy only shows up in games long enough for it to
compound, and it had spent the whole game not besieging to get it.

Capping the reach makes the economy nearly free in time: builders take the ore
that is already next to the network, run out within ~30 turns, and then spend
the rest of the game on the siege like the incumbent does. It also keeps the
two catastrophic maps fixed, since those failed on encoding, not on distance.

  python3 patch_reach.py <botdir> <max_belts>
"""
import sys

d, n = sys.argv[1], int(sys.argv[2])
p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = "MAX_BELTS = 25"
assert s.count(old) == 1, "MAX_BELTS anchor"
s = s.replace(old, "MAX_BELTS = %d" % n, 1)
open(p, "w", newline="").write(s.replace("\n", nl))
print("MAX_BELTS=%d -> %s" % (n, d))
