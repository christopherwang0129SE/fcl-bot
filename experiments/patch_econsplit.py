#!/usr/bin/env python3
"""Set how many of bots/econ's builders prioritise economy over the siege.

The rewrite gave every builder economy-first behaviour, which on ore-rich maps
means almost nobody sieges: archipelago went from a 67-turn win to a 234-turn
win with 32 harvesters and 2 sentinels. That is the shape the turtle experiment
died in (36.7%), so the split is the thing to sweep, not the economy itself.

Builders are numbered in spawn order, 1..4 (5-6 only appear if the core takes
damage). Numbers 1-3 own a store slot each and can therefore publish ore claims
and share belts; number 4 cannot, so it is the natural first one to give to the
siege.

  python3 patch_econsplit.py <botdir> <n>          first <n> builders mine
  python3 patch_econsplit.py <botdir> <n> <round>  ...and all of them siege
                                                    from <round> onward
"""
import sys

d, n = sys.argv[1], int(sys.argv[2])
switch = int(sys.argv[3]) if len(sys.argv) > 3 else None

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = "ECON_BUILDERS = (1, 2, 3, 4, 5, 6)"
assert s.count(old) == 1, "ECON_BUILDERS anchor"
s = s.replace(old, "ECON_BUILDERS = %r" % (tuple(range(1, n + 1)),), 1)

if switch is not None:
    old = """        working = False
        if self.am_builder_number in ECON_BUILDERS:"""
    new = """        working = False
        if self.am_builder_number in ECON_BUILDERS and ct.get_current_round() < %d:""" % switch
    assert s.count(old) == 1, "switch anchor"
    s = s.replace(old, new, 1)

open(p, "w", newline="").write(s.replace("\n", nl))
print("econ builders=%r switch=%s -> %s" % (tuple(range(1, n + 1)), switch, d))
