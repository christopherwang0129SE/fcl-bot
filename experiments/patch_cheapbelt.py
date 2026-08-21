#!/usr/bin/env python3
"""Keep belts near 1 per harvester, because every belt inflates every price.

get_scale_percent() rises steeply with what a team owns -- 100% at round 0,
~212% by round 25, 340% by round 75 -- and it prices EVERYTHING, so a conveyor
that cost 3 early costs 10 later, and so does the next harvester.

Harvesters pay that back; belts never do. The replay of the #1 team shows the
consequence: Pantheon won with 40 harvesters and 41 belts (1.0 belts each),
Pivot lost with 23 and 63 (2.7 each), and our long-chain variants sat at 3-4.

So: allow ONE long run to bootstrap income when there is none (otherwise maps
where the core sits far from the ore field mine literally nothing), then clamp
hard so we only ever extend to ore that is nearly adjacent to the network we
already own.

Apply after patch_conveyor.py, which supplies the encoding fix this depends on.
"""
import sys

p = sys.argv[1] + "/mapclass.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = "MAX_CONVEYOR_CHAIN = 20"
new = """# One long run is allowed to bootstrap income from nothing; after that the
# marginal belt is inflating every future price, so only near-network ore.
MAX_CONVEYOR_CHAIN_BOOTSTRAP = 20
MAX_CONVEYOR_CHAIN = 4
BOOTSTRAP_HARVESTERS = 2"""
assert s.count(old) == 1, "cap constant anchor"
s = s.replace(old, new, 1)

old = "            if len(conveyor_path) > MAX_CONVEYOR_CHAIN: return False, easiest_build, Direction.NORTH, []"
new = """            cap = (MAX_CONVEYOR_CHAIN_BOOTSTRAP
                   if len(self.planned_ore) < BOOTSTRAP_HARVESTERS else MAX_CONVEYOR_CHAIN)
            if len(conveyor_path) > cap: return False, easiest_build, Direction.NORTH, []"""
assert s.count(old) == 1, "cap use anchor"
s = s.replace(old, new, 1)

open(p, "w", newline="").write(s.replace("\n", nl))
print(f"patched {p}")
