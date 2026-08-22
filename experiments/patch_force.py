#!/usr/bin/env python3
"""Set bots/econ's total builder count and how many of them mine.

Every balance attempt so far *traded* builders between economy and siege, and
lost roughly in proportion to how much siege it gave up. This sets the two
independently, so the siege can stay at the measured optimum of 4 while miners
are added on top.

That is worth a look specifically because the 4-builder optimum in CLAUDE.md
(2->38.7%, 3->44.0%, 4->baseline, 5->30.7%, 6->22.7%) was measured on the
incumbent's economy. A 5th builder there cost +20% cost scale forever and was
funded by nothing. Here it is funded by 2-3x the titanium, so the shape of that
curve is an open question rather than a settled one.

Miners are the lowest-numbered builders because only builders 1-3 own a store
slot, and the network sharing and ore claims ride in those slots.

  python3 patch_force.py <botdir> <total_builders> <n_miners>
"""
import sys

d, total, miners = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = "        if self.bots_made < 4:"
assert s.count(old) == 1, "spawn cap anchor"
s = s.replace(old, "        if self.bots_made < %d:" % total, 1)

old = "        elif ct.get_hp() < ct.get_max_hp() and self.bots_made < 6:"
assert s.count(old) == 1, "healer cap anchor"
s = s.replace(old, "        elif ct.get_hp() < ct.get_max_hp() and self.bots_made < %d:"
              % (total + 2), 1)

old = "ECON_BUILDERS = (1, 2, 3, 4, 5, 6)"
assert s.count(old) == 1, "ECON_BUILDERS anchor"
s = s.replace(old, "ECON_BUILDERS = %r" % (tuple(range(1, miners + 1)),), 1)

open(p, "w", newline="").write(s.replace("\n", nl))
print("%s: %d builders, %d mining, %d sieging" % (d, total, miners, total - miners))
