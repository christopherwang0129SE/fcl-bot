#!/usr/bin/env python3
"""Spawn fewer builder bots -- each one taxes every future purchase by 20%.

Docs: cost = floor(scale * base), and scale rises +20% per builder bot / gunner
/ sentinel, +5% per harvester, +1% per conveyor. So the 4th builder does not
just cost its own (already inflated) 30 Ti -- it permanently makes every
harvester, belt and turret 20% dearer for the rest of the match.

Measured evidence that this is the dominant term: 6 builders scored 22.7%,
12 builders 32.7%. Both were read as "economy changes failing"; they were
really cost-scale poisoning. This tests the other direction.
"""
import sys
n = int(sys.argv[2])
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")
s = s.replace("SLOT_GAME_DATA = 0",
              f"SLOT_GAME_DATA = 0\n\n"
              f"# Each builder bot adds +20% to the cost of everything we ever build.\n"
              f"MAX_BUILDERS = {n}", 1)
old = "        if self.bots_made < 4:"
assert s.count(old) == 1
s = s.replace(old, "        if self.bots_made < MAX_BUILDERS:", 1)
old = "        if ct.get_hp() < ct.get_max_hp() and self.bots_made < 6:"
assert s.count(old) == 1
s = s.replace(old, "        if ct.get_hp() < ct.get_max_hp() and self.bots_made < MAX_BUILDERS + 2:", 1)
open(p, "w", newline="").write(s)
print(f"patched {p} -> MAX_BUILDERS={n}")
