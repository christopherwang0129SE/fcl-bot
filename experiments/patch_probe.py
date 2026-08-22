#!/usr/bin/env python3
"""Instrument a bot to log every build it makes, one line of stderr each.

Gate 1 of the economy rewrite: before spending a 150-game A/B, check the
mechanism actually moved (harvesters by turn 80, belts per harvester).

Units do NOT share module globals here -- a counter in a module-level dict
reads back as zero from the core -- so each build event is printed where it
happens and aggregated outside by probe_stats.py.

Usage:  python3 patch_probe.py <botdir>
Emits:  BUILD <team> <round> <kind>
"""
import sys

d = sys.argv[1]
p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              "SLOT_GAME_DATA = 0\n\n"
              "import sys as _sys\n"
              "def _blog(ct, kind):\n"
              "    print('BUILD %s %d %s' % (ct.get_team(), ct.get_current_round(), kind),\n"
              "          file=_sys.stderr)\n", 1)

KINDS = (("ct.build_harvester(", "harvester"),
         ("ct.build_conveyor(", "conveyor"),
         ("ct.build_sentinel(", "sentinel"),
         ("ct.build_splitter(", "splitter"))
n = 0
out = []
for line in s.split("\n"):
    out.append(line)
    stripped = line.strip()
    if stripped.startswith("#"):
        continue
    for call, kind in KINDS:
        if call in line and "def " not in line:
            indent = line[:len(line) - len(line.lstrip())]
            out.append("%s_blog(ct, '%s')" % (indent, kind))
            n += 1
            break
s = "\n".join(out)
assert n >= 2, "found %d build sites" % n

open(p, "w", newline="").write(s.replace("\n", nl))
print("probed %s (%d build sites)" % (d, n))
