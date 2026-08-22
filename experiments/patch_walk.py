#!/usr/bin/env python3
"""Cap how far a bots/econ builder will walk to take a mining job.

patch_reach caps the *belt run*, which is a titanium budget. This caps the
*detour*, which is a turn budget, and turns are what the siege actually
competes for. Capping belts alone scored 18-22% because a builder would still
walk back across the map to reach ore that was cheap in belts once it got there.

With a small cap the bot mines what is nearly free on the way and sieges the
rest of the time -- which is what the incumbent effectively does with its
three short build orders, and the behaviour every balance attempt so far has
failed to reproduce.

  python3 patch_walk.py <botdir> <max_walk>
"""
import sys

d, n = sys.argv[1], int(sys.argv[2])
p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")
old = "MAX_WALK = None"
assert s.count(old) == 1, "MAX_WALK anchor"
s = s.replace(old, "MAX_WALK = %d" % n, 1)
open(p, "w", newline="").write(s.replace("\n", nl))
print("MAX_WALK=%d -> %s" % (n, d))
