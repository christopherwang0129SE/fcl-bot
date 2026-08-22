#!/usr/bin/env python3
"""Raise the core's ammo buffer, for use with the economy rewrite only.

CLAUDE.md measured sentinels idle ~2/3 of the time with ammo the dominant
blocker (479 shots blocked), and concluded no buffer size could close it: 7
sentinels on a 3-round reload want ~23 ammo/turn, and feeding that needs ~9
harvesters where the old bot fielded 2-5. The rewrite fields 8-30, so the
shortfall the old measurements ran into is no longer the same shortfall -- this
is worth re-testing on top of it, and only on top of it.

Two traps from CLAUDE.md, both avoided here: can_convert_ammo() is
all-or-nothing, so ask for less rather than nothing when the full top-up is
unaffordable; and never size the request from ammo *burned*, because during
starvation nothing burns and the controller reads that as "no demand".

  python3 patch_ammo3.py <botdir> [target]
"""
import sys

d = sys.argv[1]
target = int(sys.argv[2]) if len(sys.argv) > 2 else 80

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = """        if ct.get_global_ammo() < self.ammo_needed:
            if ct.can_convert_ammo(self.ammo_needed):
                ct.convert_ammo(self.ammo_needed)"""
new = """        want = self.ammo_needed - ct.get_global_ammo()
        if want > 0:
            # All-or-nothing conversion: step down rather than convert nothing.
            for amount in (want, want // 2, want // 4, 10):
                if amount > 0 and ct.can_convert_ammo(amount):
                    ct.convert_ammo(amount)
                    break"""
assert s.count(old) == 1, "ammo anchor"
s = s.replace(old, new, 1)

old = "        self.ammo_needed = 20"
assert s.count(old) == 1, "ammo_needed anchor"
s = s.replace(old, "        self.ammo_needed = %d" % target, 1)

open(p, "w", newline="").write(s.replace("\n", nl))
print("ammo target=%d -> %s" % (target, d))
