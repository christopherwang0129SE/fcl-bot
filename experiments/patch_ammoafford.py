#!/usr/bin/env python3
"""Convert the ammo we can afford, in whole shots, instead of all-or-nothing.

The core does:

    if ct.get_global_ammo() < self.ammo_needed:
        if ct.can_convert_ammo(self.ammo_needed):
            ct.convert_ammo(self.ammo_needed)

Two faults, both measured on v10 over 10 games (505 ammo-blocked sentinel turns):

  * it asks for the whole target rather than the shortfall, and can_convert_ammo
    is all-or-nothing, so with 10 Ti banked and a target of 20 it converts
    NOTHING -- while a sentinel sits unable to fire;
  * the median bank at a blocked turn is 10 Ti and **53% of blocked turns had at
    least 10 Ti available**, i.e. exactly one sentinel shot going unspent.

We are broke (median bank 10, only 6% of blocked turns hold 20+), so raising the
target cannot help -- there is nothing to convert. Converting what we CAN afford
can. A sentinel shot is 10 ammo for 10 Ti and 18 damage; the alternative use of
that 10 Ti is saving toward a sentinel at 58-105 Ti which also costs +20% scale
forever.

Note CLAUDE.md records a step-down variant losing (41.7% at target 20, 45.3% at
40). That was measured on the v4 incumbent before the conveyor fix, when several
maps mined literally zero -- a different economy. Rounding to whole shots is also
new: converting 7 ammo buys nothing, since a sentinel shot costs 10.

  python3 patch_ammoafford.py <botdir> [target]
"""
import sys

d = sys.argv[1]
target = int(sys.argv[2]) if len(sys.argv) > 2 else 20

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = """        if ct.get_global_ammo() < self.ammo_needed:
            if ct.can_convert_ammo(self.ammo_needed):
                ct.convert_ammo(self.ammo_needed)"""
new = """        shortfall = self.ammo_needed - ct.get_global_ammo()
        if shortfall > 0:
            # Buy the shortfall if we can, otherwise as many whole sentinel
            # shots as the bank covers. Asking for more than we hold converts
            # nothing at all, which is how 10 Ti sits idle beside a sentinel
            # that cannot fire.
            afford = min(shortfall, ct.get_global_resources())
            afford -= afford % GameConstants.SENTINEL_AMMO_COST
            if afford > 0 and ct.can_convert_ammo(afford):
                ct.convert_ammo(afford)"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

if target != 20:
    old_t = "        self.ammo_needed = 20"
    assert s.count(old_t) == 1
    s = s.replace(old_t, "        self.ammo_needed = %d" % target, 1)

if "GameConstants" not in s.split("from fcode import")[1].split("\n")[0]:
    s = s.replace("from fcode import Controller", "from fcode import GameConstants, Controller", 1)

open(p, "w", newline="").write(s.replace("\n", nl))
print("patched %s: affordable whole-shot conversion, target %d" % (d, target))
