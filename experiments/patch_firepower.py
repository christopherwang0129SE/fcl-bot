#!/usr/bin/env python3
"""Instrument sentinels: per turn, did it have a target and could it fire?

Rebuilt because the original lived in a scratchpad that is gone. Emits one
stderr line per sentinel turn that had a live target:

  FIRED    -- had a target and fired
  NOAMMO   -- had a target, could not fire, global ammo below a shot's cost
  RELOAD   -- had a target, could not fire, but ammo was available (cooldown)

Module globals are not shared between units here, so aggregate outside.

  python3 patch_firepower.py <botdir>
"""
import sys

d = sys.argv[1]
p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = """        if target:
            if ct.can_fire(target):
                ct.fire(target)"""
new = """        if target:
            if ct.can_fire(target):
                print("FIRED", file=sys.stderr)
                ct.fire(target)
            elif ct.get_global_ammo() < GameConstants.SENTINEL_AMMO_COST:
                print("NOAMMO", file=sys.stderr)
            else:
                print("RELOAD", file=sys.stderr)"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

if "import sys" not in s.split("\n")[0:8][0]:
    s = "import sys\n" + s
if "GameConstants" not in s.split("from fcode import")[1].split("\n")[0]:
    s = s.replace("from fcode import Controller", "from fcode import GameConstants, Controller", 1)

open(p, "w", newline="").write(s.replace("\n", nl))
print("instrumented", d)
